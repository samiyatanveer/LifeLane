"""
dispatch_service.py — LifeLane top-level dispatch orchestrator.

DispatchService coordinates:
    - Siren detection events → DETECTED verification records
    - Registered ambulance authentication and session management
    - Unregistered ambulance temporary verification
    - Emergency request submission and lifecycle
    - GPS tracking, staleness detection and deviation alerts
    - Route-aware authorization via the signal safety controller
    - Passage confirmation and recovery
    - Notifications

SAFETY RULES:
    1. DETECTED siren alone NEVER grants a green signal.
    2. Only AUTHORIZED requests may trigger signal priority.
    3. No conflicting movements may receive simultaneous green.
    4. Duplicate active requests (same ambulance) are rejected (Decision 5A).
    5. Registered and temp-verified ambulances receive equal priority (3A).
    6. If hospital unavailable: accept request + notify operator (4A).
"""
from __future__ import annotations

import logging
import time
from typing import Callable, Dict, List, Optional, Set

from lifelane_engine.ambulance.request import (
    AmbulanceRequest,
    RequestStatus,
    make_mock_request,
)
from lifelane_engine.ambulance.route_planner import RoutePlanner
from lifelane_engine.dispatch.authenticator import AmbulanceAuthenticator, AuthResult
from lifelane_engine.dispatch.emergency_request import EmergencyRequest
from lifelane_engine.dispatch.gps_tracker import GpsSource, GpsTracker, GpsUpdate
from lifelane_engine.dispatch.notifier import MockNotifier, NotificationEvent
from lifelane_engine.dispatch.registry import AmbulanceRegistry
from lifelane_engine.dispatch.session_manager import (
    DuplicateSessionError,
    Session,
    SessionManager,
)
from lifelane_engine.dispatch.temp_verification import (
    TempVerificationRequest,
    TempVerifier,
    TempVerificationOutcome,
)
from lifelane_engine.dispatch.verification_state import (
    VerificationConfidence,
    VerificationLevel,
    VerificationMethod,
    VerificationRecord,
)
from lifelane_engine.traffic.signal_controller import JunctionSignalController

logger = logging.getLogger(__name__)


class DuplicateRequestError(Exception):
    """Raised when an ambulance submits a second active request (Decision 5A)."""


class DispatchService:
    """Top-level orchestrator for ambulance dispatch and signal coordination.

    Args:
        registry:              AmbulanceRegistry of registered ambulances.
        authenticator:         AmbulanceAuthenticator for device credentials.
        session_manager:       SessionManager for authenticated sessions.
        gps_tracker_factory:   Callable[str] → GpsTracker (one per ambulance).
        temp_verifier:         TempVerifier for unregistered ambulance pathways.
        notifier:              MockNotifier for operator notifications.
        route_planner:         RoutePlanner with mock or SUMO network loaded.
        signal_controllers:    Dict[junction_id → JunctionSignalController].
        verification_timeout_s: Seconds before a DETECTED/VERIFIED record expires.
        request_expiry_s:      Default emergency request TTL (seconds).
    """

    def __init__(
        self,
        registry: AmbulanceRegistry,
        authenticator: AmbulanceAuthenticator,
        session_manager: SessionManager,
        gps_tracker_factory: Callable[[str], GpsTracker],
        temp_verifier: TempVerifier,
        notifier: MockNotifier,
        route_planner: RoutePlanner,
        signal_controllers: Optional[Dict[str, JunctionSignalController]] = None,
        verification_timeout_s: float = 60.0,
        request_expiry_s: float = 300.0,
    ) -> None:
        self._registry = registry
        self._authenticator = authenticator
        self._session_manager = session_manager
        self._gps_tracker_factory = gps_tracker_factory
        self._temp_verifier = temp_verifier
        self._notifier = notifier
        self._route_planner = route_planner
        self._signal_controllers: Dict[str, JunctionSignalController] = (
            signal_controllers or {}
        )
        self._verification_timeout_s = verification_timeout_s
        self._request_expiry_s = request_expiry_s

        # State
        self._verification_records: Dict[str, VerificationRecord] = {}  # ambulance_id → record
        self._active_requests: Dict[str, EmergencyRequest] = {}          # ambulance_id → request
        self._gps_trackers: Dict[str, GpsTracker] = {}                   # ambulance_id → tracker
        self._temp_requests: Dict[str, TempVerificationRequest] = {}     # temp_id → req

    # ==================================================================
    # Detection
    # ==================================================================

    def process_detection(
        self,
        approach: str,
        junction_id: str,
        ambulance_id: str,
        now: Optional[float] = None,
    ) -> VerificationRecord:
        """Record a siren detection event.

        Creates or updates a VerificationRecord at DETECTED level.
        Does NOT grant signal priority.

        Args:
            approach:     Detected approach direction ("north", "east", etc.).
            junction_id:  Junction where detection occurred.
            ambulance_id: Identifying label (may be "UNKNOWN" for unregistered).
            now:          Override epoch time.

        Returns:
            The VerificationRecord at DETECTED level.
        """
        if now is None:
            now = time.time()

        is_registered = self._registry.lookup_by_lifelane_id(ambulance_id) is not None
        expires_at = now + self._verification_timeout_s

        record = VerificationRecord(
            ambulance_id=ambulance_id,
            is_registered=is_registered,
            verification_level=VerificationLevel.DETECTED,
            approach=approach,
            junction_id=junction_id,
            detection_timestamp=now,
            expires_at=expires_at,
        )
        self._verification_records[ambulance_id] = record
        logger.info(
            "[dispatch] DETECTED amb=%s junction=%s approach=%s",
            ambulance_id, junction_id, approach,
        )
        self._notifier.notify(
            ambulance_id=ambulance_id,
            event_type=NotificationEvent.UNVERIFIED_SIREN_ALERT,
            message=f"Siren detected at {junction_id} from {approach}. "
                    "Awaiting verification before any priority.",
        )
        return record

    # ==================================================================
    # Registered ambulance workflow
    # ==================================================================

    def authenticate_registered(
        self,
        device_id: str,
        credential: str,
        now: Optional[float] = None,
    ) -> AuthResult:
        """Authenticate a registered ambulance device.

        On success, a session is created for the ambulance.
        On failure, AUTH_FAILURE notification is sent.

        Args:
            device_id:  Device ID presented by the ambulance.
            credential: Plaintext credential (hashed internally).
            now:        Override epoch time.

        Returns:
            AuthResult (check .success).
        """
        if now is None:
            now = time.time()

        result = self._authenticator.authenticate(device_id, credential)

        if not result.success:
            self._notifier.notify(
                ambulance_id=result.ambulance_id or device_id,
                event_type=NotificationEvent.AUTH_FAILURE,
                message=f"Authentication failed: {result.reason}",
            )
            logger.warning("[dispatch] Auth failed device=%s: %s", device_id, result.reason)
            return result

        # Create session (may raise DuplicateSessionError if one already exists)
        try:
            self._session_manager.create_session(
                ambulance_id=result.ambulance_id, device_id=device_id, now=now
            )
        except DuplicateSessionError as exc:
            logger.warning("[dispatch] Duplicate session for %s: %s", result.ambulance_id, exc)
            # Allow it — just return success; session already valid

        logger.info("[dispatch] Authenticated ambulance_id=%s", result.ambulance_id)
        return result

    def submit_registered_request(
        self,
        ambulance_id: str,
        session_id: str,
        origin: str,
        hospital_id: str,
        approach: str,
        junction_id: str,
        now: Optional[float] = None,
    ) -> EmergencyRequest:
        """Submit an emergency request for a registered ambulance.

        Decision 5A: Rejects duplicate active request.
        Decision 4A: Accepts even if hospital is unavailable (notifies operator).

        Args:
            ambulance_id: LifeLane ID.
            session_id:   Valid session token.
            origin:       Starting node (e.g. "J1").
            hospital_id:  Target hospital.
            approach:     Approach direction at junction_id.
            junction_id:  Requesting junction.
            now:          Override epoch time.

        Returns:
            EmergencyRequest.

        Raises:
            DuplicateRequestError: if ambulance already has an active request.
            ValueError: if session invalid, route not found, or hospital unknown.
        """
        if now is None:
            now = time.time()

        # --- Session check ---
        if not self._session_manager.validate_session(session_id, now=now):
            raise ValueError(f"Session {session_id!r} is invalid or expired")

        # --- Duplicate check (Decision 5A) ---
        self._check_no_duplicate(ambulance_id)

        # --- Route planning ---
        hospital = self._route_planner.get_hospital(hospital_id)
        destination_node = hospital.node if hospital else hospital_id

        route_result = self._route_planner.find_route(origin, destination_node)
        if route_result is None:
            raise ValueError(
                f"No route found from {origin!r} to hospital {hospital_id!r}"
            )
        edge_ids, node_ids, cost = route_result

        # --- Hospital availability (Decision 4A) ---
        if hospital is None or not hospital.available:
            self._notifier.notify(
                ambulance_id=ambulance_id,
                event_type=NotificationEvent.REQUEST_ACCEPTED,
                message=f"Hospital {hospital_id!r} unavailable or unknown. "
                        "Proceeding with request anyway.",
            )
            logger.warning(
                "[dispatch] Hospital %s unavailable; proceeding per Decision 4A", hospital_id
            )

        # --- Build base request ---
        base_req = AmbulanceRequest(
            ambulance_id=ambulance_id,
            origin_edge=origin,
            destination_edge=destination_node,
            hospital_id=hospital_id,
            approach=approach,
            junction_id=junction_id,
            route=edge_ids if edge_ids else [origin],
            emergency_mode="lights_and_sirens",
            authorization_token=session_id,
            expiry_s=self._request_expiry_s,
            created_at=now,
        )
        base_req.authorize(now=now)

        # --- Wrap in EmergencyRequest ---
        em_req = EmergencyRequest(
            base_request=base_req,
            is_registered=True,
            verification_level=VerificationLevel.AUTHORIZED,
            verification_method=VerificationMethod.REGISTERED_DEVICE,
            verification_confidence=VerificationConfidence.HIGH,
            gps_source="DEVICE",
            created_at=now,
        )

        # Seed junction ETAs (naive; replaced in Phase 5)
        em_req.update_junction_etas(
            current_speed_ms=13.9,
            route_junctions=node_ids,
            now=now,
        )

        self._active_requests[ambulance_id] = em_req

        # Update verification record
        record = self._verification_records.get(ambulance_id)
        if record is not None:
            record.verification_level = VerificationLevel.AUTHORIZED
            record.verification_method = VerificationMethod.REGISTERED_DEVICE
            record.verification_confidence = VerificationConfidence.HIGH
            record.verified_at = now

        self._notifier.notify(
            ambulance_id=ambulance_id,
            event_type=NotificationEvent.REQUEST_ACCEPTED,
            request_id=base_req.request_id,
            message=f"Emergency request accepted. Route: {node_ids}. "
                    f"ETAs: {em_req.junction_etas}",
        )
        logger.info(
            "[dispatch] Registered request accepted: amb=%s req=%s hospital=%s",
            ambulance_id, base_req.request_id, hospital_id,
        )
        return em_req

    # ==================================================================
    # Unregistered ambulance workflow
    # ==================================================================

    def submit_temp_verification(
        self,
        temp_req: TempVerificationRequest,
        now: Optional[float] = None,
    ) -> TempVerificationRequest:
        """Run temporary verification for an unregistered ambulance.

        Stores the result. Caller should then call submit_unregistered_request
        if verification succeeded.

        Args:
            temp_req: Populated TempVerificationRequest.
            now:      Override epoch time.

        Returns:
            The same TempVerificationRequest with result fields populated.
        """
        if now is None:
            now = time.time()

        self._temp_verifier.verify(temp_req, now=now)
        self._temp_requests[temp_req.temp_id] = temp_req

        if temp_req.is_verified():
            self._notifier.notify(
                ambulance_id=temp_req.announced_registration or temp_req.temp_id,
                event_type=NotificationEvent.TEMP_VERIFICATION_SUCCESS,
                message=f"Temp verification successful via {temp_req.verification_method} "
                        f"(confidence={temp_req.confidence.name})",
            )
        else:
            self._notifier.notify(
                ambulance_id=temp_req.announced_registration or temp_req.temp_id,
                event_type=NotificationEvent.TEMP_VERIFICATION_FAILED,
                message=f"Temp verification failed: {temp_req.failure_reason}",
            )
        return temp_req

    def submit_unregistered_request(
        self,
        temp_id: str,
        approach: str,
        junction_id: str,
        now: Optional[float] = None,
    ) -> EmergencyRequest:
        """Submit an emergency request based on a successful temp verification.

        Decision 3A: Equal priority to registered requests.
        Decision 5A: Rejects duplicate active request.
        Decision 4A: Accepts even if hospital unavailable.

        Args:
            temp_id:     ID returned from submit_temp_verification.
            approach:    Approach direction.
            junction_id: Junction where priority is requested.
            now:         Override epoch time.

        Returns:
            EmergencyRequest.

        Raises:
            ValueError: if temp_id not found, verification failed, or route not found.
            DuplicateRequestError: if ambulance already has an active request.
        """
        if now is None:
            now = time.time()

        temp_req = self._temp_requests.get(temp_id)
        if temp_req is None:
            raise ValueError(f"temp_id {temp_id!r} not found")

        if not temp_req.is_verified():
            raise ValueError(
                f"Temp verification for {temp_id!r} did not succeed: "
                f"{temp_req.failure_reason}"
            )

        ambulance_id = temp_req.announced_registration or temp_req.temp_id

        # --- Duplicate check (Decision 5A) ---
        self._check_no_duplicate(ambulance_id)

        # --- Route planning ---
        hospital_id = temp_req.hospital_id
        hospital = self._route_planner.get_hospital(hospital_id)
        origin = "J1"  # Default origin for unregistered; use GPS if available

        if temp_req.gps_latitude is not None:
            origin = self._nearest_node_for_gps(temp_req.gps_latitude, temp_req.gps_longitude)

        destination_node = hospital.node if hospital else hospital_id
        route_result = self._route_planner.find_route(origin, destination_node)
        if route_result is None:
            raise ValueError(
                f"No route found from {origin!r} to hospital {hospital_id!r}"
            )
        edge_ids, node_ids, _ = route_result

        # --- Hospital availability (Decision 4A) ---
        if hospital is None or not hospital.available:
            self._notifier.notify(
                ambulance_id=ambulance_id,
                event_type=NotificationEvent.REQUEST_ACCEPTED,
                message=f"Hospital {hospital_id!r} unavailable; proceeding (Decision 4A).",
            )

        # --- Build base request ---
        base_req = AmbulanceRequest(
            ambulance_id=ambulance_id,
            origin_edge=origin,
            destination_edge=destination_node,
            hospital_id=hospital_id,
            approach=approach,
            junction_id=junction_id,
            route=edge_ids if edge_ids else [origin],
            emergency_mode="lights_and_sirens",
            authorization_token=temp_id,
            expiry_s=self._request_expiry_s,
            created_at=now,
        )
        # Temp-verified requests go to AUTHORIZED state (Decision 3A — equal priority)
        base_req.authorize(now=now)

        confidence_map = {
            "HIGH": VerificationConfidence.HIGH,
            "MEDIUM": VerificationConfidence.MEDIUM,
            "LOW": VerificationConfidence.LOW,
        }
        em_req = EmergencyRequest(
            base_request=base_req,
            is_registered=False,
            verification_level=VerificationLevel.AUTHORIZED,
            verification_method=temp_req.method_enum,
            verification_confidence=confidence_map.get(
                temp_req.confidence.name, VerificationConfidence.LOW
            ),
            gps_source=temp_req.gps_source,
            created_at=now,
        )
        em_req.update_junction_etas(
            current_speed_ms=13.9,
            route_junctions=node_ids,
            now=now,
        )

        self._active_requests[ambulance_id] = em_req
        self._notifier.notify(
            ambulance_id=ambulance_id,
            event_type=NotificationEvent.REQUEST_ACCEPTED,
            request_id=base_req.request_id,
            message=f"Unregistered request accepted via {temp_req.verification_method}. "
                    f"Route: {node_ids}",
        )
        logger.info(
            "[dispatch] Unregistered request accepted: amb=%s req=%s",
            ambulance_id, base_req.request_id,
        )
        return em_req

    # ==================================================================
    # GPS tracking
    # ==================================================================

    def process_gps_update(
        self,
        ambulance_id: str,
        gps: GpsUpdate,
        now: Optional[float] = None,
    ) -> bool:
        """Accept a GPS update, detect staleness or deviation.

        Returns True if update accepted without staleness/deviation issues.
        """
        if now is None:
            now = time.time()

        tracker = self._get_or_create_tracker(ambulance_id)
        tracker.update(gps)

        # Check deviation
        if tracker.check_deviation():
            self._notifier.notify(
                ambulance_id=ambulance_id,
                event_type=NotificationEvent.GPS_DEVIATION,
                message="Route deviation detected. Corridor may need recalculation.",
            )
            return False

        # Update junction ETAs if request is active
        em_req = self._active_requests.get(ambulance_id)
        if em_req is not None and gps.speed_ms > 0:
            em_req.update_junction_etas(
                current_speed_ms=gps.speed_ms,
                route_junctions=list(em_req.junction_etas.keys()),
                now=now,
            )
        return True

    def check_gps_staleness(
        self, ambulance_id: str, now: Optional[float] = None
    ) -> bool:
        """Return True if GPS is stale for this ambulance and notify operator."""
        if now is None:
            now = time.time()
        tracker = self._gps_trackers.get(ambulance_id)
        if tracker is None:
            return True  # Never received GPS → stale
        if tracker.is_stale(now=now):
            self._notifier.notify(
                ambulance_id=ambulance_id,
                event_type=NotificationEvent.GPS_STALE,
                message="GPS updates have stopped. Position may be inaccurate.",
            )
            return True
        return False

    # ==================================================================
    # Passage confirmation
    # ==================================================================

    def confirm_passage(
        self,
        ambulance_id: str,
        junction_id: str,
        now: Optional[float] = None,
    ) -> bool:
        """Confirm that the ambulance has cleared a junction.

        Returns True if an active request existed and was completed.
        """
        if now is None:
            now = time.time()
        em_req = self._active_requests.get(ambulance_id)
        if em_req is None:
            logger.warning(
                "[dispatch] confirm_passage: no active request for %s", ambulance_id
            )
            return False

        em_req.base_request.complete()
        self._active_requests.pop(ambulance_id, None)
        self._notifier.notify(
            ambulance_id=ambulance_id,
            event_type=NotificationEvent.PASSAGE_CONFIRMED,
            request_id=em_req.request_id,
            message=f"Ambulance {ambulance_id} confirmed passage at {junction_id}.",
        )
        logger.info(
            "[dispatch] Passage confirmed: amb=%s junction=%s req=%s",
            ambulance_id, junction_id, em_req.request_id,
        )
        return True

    # ==================================================================
    # Timeout and expiry sweeps
    # ==================================================================

    def check_verification_timeouts(self, now: Optional[float] = None) -> List[str]:
        """Expire stale verification records. Returns list of expired ambulance IDs."""
        if now is None:
            now = time.time()
        expired: List[str] = []
        for amb_id, record in list(self._verification_records.items()):
            if record.is_expired(now):
                del self._verification_records[amb_id]
                expired.append(amb_id)
                self._notifier.notify(
                    ambulance_id=amb_id,
                    event_type=NotificationEvent.VERIFICATION_TIMEOUT,
                    message="Verification window expired. No priority granted.",
                )
                logger.warning("[dispatch] Verification timeout for %s", amb_id)
        return expired

    def check_request_expirations(self, now: Optional[float] = None) -> List[str]:
        """Expire stale emergency requests. Returns list of expired ambulance IDs."""
        if now is None:
            now = time.time()
        expired: List[str] = []
        for amb_id, em_req in list(self._active_requests.items()):
            if em_req.base_request.is_expired(now):
                em_req.base_request.expire()
                del self._active_requests[amb_id]
                expired.append(amb_id)
                self._notifier.notify(
                    ambulance_id=amb_id,
                    event_type=NotificationEvent.REQUEST_EXPIRED,
                    request_id=em_req.request_id,
                    message="Emergency request expired without passage confirmation.",
                )
                logger.warning("[dispatch] Request expired: amb=%s", amb_id)
        return expired

    # ==================================================================
    # Accessors
    # ==================================================================

    def get_active_request(self, ambulance_id: str) -> Optional[EmergencyRequest]:
        """Return the active EmergencyRequest for an ambulance, or None."""
        return self._active_requests.get(ambulance_id)

    def get_verification_record(self, ambulance_id: str) -> Optional[VerificationRecord]:
        """Return the current VerificationRecord for an ambulance, or None."""
        return self._verification_records.get(ambulance_id)

    def get_tracker(self, ambulance_id: str) -> Optional[GpsTracker]:
        """Return the GPS tracker for an ambulance, or None."""
        return self._gps_trackers.get(ambulance_id)

    # ==================================================================
    # Internal helpers
    # ==================================================================

    def _check_no_duplicate(self, ambulance_id: str) -> None:
        """Raise DuplicateRequestError if ambulance already has an active request."""
        existing = self._active_requests.get(ambulance_id)
        if existing is not None and existing.status in (
            RequestStatus.PENDING,
            RequestStatus.AUTHORIZED,
            RequestStatus.ACTIVE,
        ):
            raise DuplicateRequestError(
                f"Ambulance {ambulance_id!r} already has an active request "
                f"{existing.request_id!r}"
            )

    def _get_or_create_tracker(self, ambulance_id: str) -> GpsTracker:
        """Get existing GPS tracker or create a new one."""
        if ambulance_id not in self._gps_trackers:
            self._gps_trackers[ambulance_id] = self._gps_tracker_factory(ambulance_id)
        return self._gps_trackers[ambulance_id]

    def _nearest_node_for_gps(self, lat: float, lon: float) -> str:
        """Return the nearest mock grid node to a given GPS position."""
        from lifelane_engine.dispatch.gps_tracker import (
            NODE_POSITIONS,
            _M_PER_DEG_LAT,
            _M_PER_DEG_LON,
        )
        import math

        best_node = "J1"
        best_dist = float("inf")
        for node_id, (nlat, nlon) in NODE_POSITIONS.items():
            dlat = (lat - nlat) * _M_PER_DEG_LAT
            dlon = (lon - nlon) * _M_PER_DEG_LON
            dist = math.sqrt(dlat ** 2 + dlon ** 2)
            if dist < best_dist:
                best_dist = dist
                best_node = node_id
        return best_node


# ---------------------------------------------------------------------------
# Factory helper for test / POC
# ---------------------------------------------------------------------------

def build_default_dispatch_service(
    verification_timeout_s: float = 60.0,
    request_expiry_s: float = 300.0,
) -> DispatchService:
    """Build a fully wired DispatchService using mock components.

    Suitable for the Phase 2 POC and unit tests.
    """
    from lifelane_engine.dispatch.registry import MockRegistry

    registry = MockRegistry.build_default()
    authenticator = AmbulanceAuthenticator(registry)
    session_manager = SessionManager()
    temp_verifier = TempVerifier()
    notifier = MockNotifier()
    route_planner = RoutePlanner()
    route_planner.build_mock_grid()

    return DispatchService(
        registry=registry,
        authenticator=authenticator,
        session_manager=session_manager,
        gps_tracker_factory=lambda amb_id: GpsTracker(amb_id),
        temp_verifier=temp_verifier,
        notifier=notifier,
        route_planner=route_planner,
        signal_controllers={},
        verification_timeout_s=verification_timeout_s,
        request_expiry_s=request_expiry_s,
    )

