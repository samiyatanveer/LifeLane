"""
dispatch — Ambulance Identity, Emergency Dispatch, and Verification Management.

This package implements:
- Ambulance registry and authentication (registered ambulances)
- Temporary verification pathways (unregistered ambulances)
- Three-tier verification states: DETECTED → VERIFIED → AUTHORIZED
- GPS tracking, staleness detection and deviation alerts
- Session management
- Emergency request lifecycle
- Notifications
- The top-level DispatchService orchestrator

SAFETY RULE: A detected siren NEVER grants a green signal alone.
             Only AUTHORIZED requests may trigger signal priority.
"""

