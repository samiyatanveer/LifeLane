"""
test_dispatch_service.py — Integration tests for DispatchService.

Covers:
- Registered ambulance: detect → auth → submit → GPS → passage
- Unregistered ambulance: detect → temp verify → submit → passage
- Verification timeout
- GPS staleness notification
- Duplicate request rejection (Decision 5A)
- Hospital unavailable acceptance (Decision 4A)
- DETECTED siren never grants priority without authorization
"""
import pytest
from lifelane_engine.dispatch.dispatch_service import (
    DuplicateRequestError,
    DispatchService,
    build_default_dispatch_service,
)
from lifelane_engine.dispatch.gps_tracker import GpsSource, GpsUpdate
from lifelane_engine.dispatch.notifier import NotificationEvent
from lifelane_engine.dispatch.registry import MockRegistry
from lifelane_engine.dispatch.temp_verification import (
    DEFAULT_VALID_OPERATOR_TOKENS,
    TempVerificationRequest,
)
from lifelane_engine.dispatch.verification_state import VerificationLevel

T0 = 200_000.0


def _ds() -> DispatchService:
    return build_default_dispatch_service(
        verification_timeout_s=60.0,
        request_expiry_s=300.0,
    )


class TestDetection:
    def test_detection_sets_detected_level(self):
        ds = _ds()
        record = ds.process_detection(
            approach="north", junction_id="J1", ambulance_id="LL-001", now=T0
        )
        assert record.verification_level == VerificationLevel.DETECTED

    def test_detection_sends_unverified_alert(self):
        ds = _ds()
        ds.process_detection("north", "J1", "LL-001", now=T0)
        notes = ds._notifier.get_by_event_type(NotificationEvent.UNVERIFIED_SIREN_ALERT)
        assert len(notes) == 1

    def test_detected_alone_never_authorizes(self):
        """SAFETY: DETECTED state must NOT grant signal priority."""
        ds = _ds()
        record = ds.process_detection("north", "J1", "LL-001", now=T0)
        assert record.can_authorize() is False


class TestRegisteredWorkflow:
    def test_full_registered_workflow(self):
        ds = _ds()
        # 1. Authenticate
        result = ds.authenticate_registered(
            "DEV-001", MockRegistry.mock_credential("DEV-001"), now=T0
        )
        assert result.success is True

        # 2. Submit request
        em_req = ds.submit_registered_request(
            ambulance_id="LL-001",
            session_id=ds._session_manager.get_active_session("LL-001", now=T0).session_id,
            origin="J1",
            hospital_id="H1",
            approach="north",
            junction_id="J1",
            now=T0,
        )
        assert em_req is not None
        assert em_req.is_authorized is True
        assert em_req.is_registered is True

    def test_invalid_session_rejected(self):
        ds = _ds()
        with pytest.raises(ValueError, match="invalid or expired"):
            ds.submit_registered_request(
                ambulance_id="LL-001",
                session_id="bad-session",
                origin="J1",
                hospital_id="H1",
                approach="north",
                junction_id="J1",
                now=T0,
            )

    def test_duplicate_request_rejected(self):
        """Decision 5A: second request raises DuplicateRequestError."""
        ds = _ds()
        result = ds.authenticate_registered(
            "DEV-001", MockRegistry.mock_credential("DEV-001"), now=T0
        )
        session = ds._session_manager.get_active_session("LL-001", now=T0)
        ds.submit_registered_request(
            "LL-001", session.session_id, "J1", "H1", "north", "J1", now=T0
        )
        with pytest.raises(DuplicateRequestError):
            ds.submit_registered_request(
                "LL-001", session.session_id, "J1", "H1", "north", "J1", now=T0 + 1
            )

    def test_auth_failure_sends_notification(self):
        ds = _ds()
        ds.authenticate_registered("DEV-001", "wrong-cred", now=T0)
        notes = ds._notifier.get_by_event_type(NotificationEvent.AUTH_FAILURE)
        assert len(notes) == 1

    def test_junction_etas_populated(self):
        ds = _ds()
        ds.authenticate_registered("DEV-001", MockRegistry.mock_credential("DEV-001"), now=T0)
        sess = ds._session_manager.get_active_session("LL-001", now=T0)
        em_req = ds.submit_registered_request(
            "LL-001", sess.session_id, "J1", "H1", "north", "J1", now=T0
        )
        assert len(em_req.junction_etas) > 0


class TestUnregisteredWorkflow:
    def test_dispatch_operator_path(self):
        ds = _ds()
        ds.process_detection("south", "J1", "UNKNOWN", now=T0)
        temp_req = TempVerificationRequest(
            verification_method="DISPATCH_OPERATOR",
            operator_token=DEFAULT_VALID_OPERATOR_TOKENS[0],
            gps_latitude=33.720,
            gps_longitude=73.040,
            hospital_id="H1",
            announced_registration="UNREG-001",
        )
        verified = ds.submit_temp_verification(temp_req, now=T0)
        assert verified.is_verified() is True

        em_req = ds.submit_unregistered_request(
            temp_id=verified.temp_id,
            approach="south",
            junction_id="J1",
            now=T0,
        )
        assert em_req.is_authorized is True
        assert em_req.is_registered is False

    def test_failed_verification_blocks_request(self):
        ds = _ds()
        temp_req = TempVerificationRequest(
            verification_method="DISPATCH_OPERATOR",
            operator_token="INVALID-TOKEN",
            hospital_id="H1",
        )
        verified = ds.submit_temp_verification(temp_req, now=T0)
        assert not verified.is_verified()
        with pytest.raises(ValueError):
            ds.submit_unregistered_request(
                temp_id=verified.temp_id, approach="north", junction_id="J1", now=T0
            )


class TestPassageAndExpiry:
    def test_passage_confirmation_completes_request(self):
        ds = _ds()
        ds.authenticate_registered("DEV-001", MockRegistry.mock_credential("DEV-001"), now=T0)
        sess = ds._session_manager.get_active_session("LL-001", now=T0)
        ds.submit_registered_request("LL-001", sess.session_id, "J1", "H1", "north", "J1", now=T0)
        ok = ds.confirm_passage("LL-001", "J1", now=T0 + 30)
        assert ok is True
        assert ds.get_active_request("LL-001") is None

    def test_verification_timeout_expires_record(self):
        ds = build_default_dispatch_service(verification_timeout_s=60.0)
        ds.process_detection("north", "J1", "UNKNOWN-AMB", now=T0)
        expired = ds.check_verification_timeouts(now=T0 + 61)
        assert "UNKNOWN-AMB" in expired

    def test_request_expiry(self):
        ds = build_default_dispatch_service(request_expiry_s=10.0)
        ds.authenticate_registered("DEV-001", MockRegistry.mock_credential("DEV-001"), now=T0)
        sess = ds._session_manager.get_active_session("LL-001", now=T0)
        ds.submit_registered_request("LL-001", sess.session_id, "J1", "H1", "north", "J1", now=T0)
        expired = ds.check_request_expirations(now=T0 + 15)
        assert "LL-001" in expired


class TestGpsStaleness:
    def test_gps_stale_notification(self):
        ds = _ds()
        # Provide a GPS update then wait beyond threshold
        update = GpsUpdate(
            ambulance_id="LL-001",
            latitude=33.720,
            longitude=73.040,
            speed_ms=10.0,
            heading_deg=90.0,
            timestamp=T0,
            source=GpsSource.DEVICE,
        )
        ds.process_gps_update("LL-001", update, now=T0)
        stale = ds.check_gps_staleness("LL-001", now=T0 + 20)  # threshold default 10s
        assert stale is True
        notes = ds._notifier.get_by_event_type(NotificationEvent.GPS_STALE)
        assert len(notes) >= 1

