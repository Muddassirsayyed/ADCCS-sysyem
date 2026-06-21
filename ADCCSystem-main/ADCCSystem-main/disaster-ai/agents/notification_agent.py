"""
ADCC — Notification Agent
==========================
Standalone agent that dispatches emergency alerts and operational updates
via SMS, WhatsApp, and email using the existing notification_tool.py.

Previously this functionality was embedded inside other agents. This file
extracts it into a first-class agent that the Supervisor can invoke independently.

Responsibilities:
    ✅ Compose situation-aware alert messages from DisasterState
    ✅ Dispatch SMS alerts to emergency contacts via Twilio
    ✅ Dispatch WhatsApp alerts via Twilio WhatsApp API
    ✅ Log all notifications to data/notification_logs.jsonl
    ✅ Mark notification_sent = True in state when done
    ✅ Support both real Twilio and simulated dispatch (when credentials missing)

NOT responsible for:
    ❌ Severity analysis    → severity_agent.py
    ❌ Route planning       → route_planning_agent.py
    ❌ Resource allocation  → allocation_agent.py

Position in Graph (supervisor-driven):
    supervisor → notification_agent → supervisor
"""

import os
import time
from datetime import datetime, timezone
from typing import Optional

from loguru import logger

from workflows.state import (
    DisasterState,
    StateUpdate,
    update_state_metadata,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

AGENT_NAME = "notification_agent"

# Emergency broadcast recipients — loaded from env or defaults for demo
DEFAULT_EMERGENCY_CONTACTS = [
    os.getenv("EMERGENCY_CONTACT_1", "+919999999999"),
]

# Alert message templates per severity
ALERT_TEMPLATES = {
    "Critical": (
        "🚨 CRITICAL DISASTER ALERT — ADCC\n"
        "Disaster: {disaster_title}\n"
        "Severity: CRITICAL | Confidence: {confidence}%\n"
        "Affected Area: {location}\n"
        "Resources Deployed: {resources_deployed}\n"
        "Shelters Active: {shelters_active}\n"
        "Evacuation: MANDATORY — Follow designated routes.\n"
        "NDRF & Emergency Services are responding.\n"
        "Stay tuned to official channels."
    ),
    "High": (
        "⚠️ HIGH SEVERITY ALERT — ADCC\n"
        "Disaster: {disaster_title}\n"
        "Severity: HIGH | Confidence: {confidence}%\n"
        "Affected Area: {location}\n"
        "Resources Deployed: {resources_deployed}\n"
        "Shelters Available: {shelters_active}\n"
        "Please follow evacuation advisories and avoid flood zones."
    ),
    "Medium": (
        "ℹ️ DISASTER WARNING — ADCC\n"
        "Disaster: {disaster_title}\n"
        "Severity: MEDIUM | Confidence: {confidence}%\n"
        "Affected Area: {location}\n"
        "Stay alert. Monitoring situation closely."
    ),
    "Low": (
        "📋 ADVISORY — ADCC\n"
        "Situation: {disaster_title}\n"
        "Severity: LOW | Confidence: {confidence}%\n"
        "Area: {location}\n"
        "No immediate action required. Stay informed."
    ),
}


# ===========================================================================
# INTERNAL HELPERS
# ===========================================================================

def _build_alert_message(state: DisasterState) -> tuple[str, str]:
    """
    Constructs the alert message text and level from DisasterState.

    Returns:
        tuple[str, str]: (message_text, alert_level)
    """
    severity_level = state.get("severity_level", "Low")
    confidence_score = state.get("confidence_score", 0.0)
    confidence_pct = int(round(confidence_score * 100)) if confidence_score <= 1.0 else int(confidence_score)

    # Get best disaster title from events
    disaster_title = "Active Disaster Event"
    disaster_events = state.get("disaster_events") or []
    if disaster_events:
        disaster_title = disaster_events[0].get("title", disaster_title)
    else:
        eq_events = state.get("earthquake_events") or []
        if eq_events:
            disaster_title = eq_events[0].get("place", disaster_title)

    # Location from weather or events
    location = "Affected Region"
    weather = state.get("weather_data")
    if weather:
        location = weather.get("location_label") or f"{weather.get('latitude', '')}, {weather.get('longitude', '')}"
    elif disaster_events:
        location = disaster_events[0].get("country", location)

    # Resource info
    alloc_plan = state.get("allocation_plan") or {}
    resources_deployed = alloc_plan.get("total_resources_deployed", 0)

    shelter_plan = state.get("shelter_plan") or {}
    shelters_active = len(shelter_plan.get("assigned_shelters") or [])

    template = ALERT_TEMPLATES.get(severity_level, ALERT_TEMPLATES["Low"])
    message = template.format(
        disaster_title=disaster_title,
        confidence=confidence_pct,
        location=location,
        resources_deployed=resources_deployed,
        shelters_active=shelters_active,
    )

    # Map severity to alert_tool level
    level_map = {
        "Critical": "CRITICAL",
        "High":     "HIGH",
        "Medium":   "WARNING",
        "Low":      "INFO",
    }
    alert_level = level_map.get(severity_level, "INFO")

    return message, alert_level


def _get_recipients(state: DisasterState) -> list[str]:
    """
    Returns the list of phone numbers to notify.
    Uses env vars for real contacts, or DEFAULT_EMERGENCY_CONTACTS for demo.
    """
    contacts_env = os.getenv("EMERGENCY_CONTACTS", "")
    if contacts_env:
        # Comma-separated list from env
        return [c.strip() for c in contacts_env.split(",") if c.strip()]
    return DEFAULT_EMERGENCY_CONTACTS


# ===========================================================================
# MAIN AGENT ENTRY POINT
# ===========================================================================

def run_notification(state: DisasterState) -> DisasterState:
    """
    Main Notification Agent entry point. Called by the LangGraph notification_node.

    Steps:
    1. Build situation-aware alert message from current DisasterState
    2. Dispatch SMS via Twilio (or simulated if credentials missing)
    3. Dispatch WhatsApp via Twilio (or simulated)
    4. Mark notification_sent = True in state
    5. Append notification summary to recommendations

    Args:
        state: Current DisasterState

    Returns:
        Updated DisasterState with notification_sent=True and dispatch records
    """
    from agents.supervisor_agent import mark_agent_completed

    t_start = time.time()
    logger.info("[NotificationAgent] ─── Starting emergency notification dispatch ───")

    # ── Guard: already notified ──────────────────────────────────────────────
    if state.get("notification_sent"):
        logger.info("[NotificationAgent] Notifications already sent. Skipping duplicate dispatch.")
        return mark_agent_completed(
            update_state_metadata(state, AGENT_NAME),
            AGENT_NAME
        )

    state = update_state_metadata(state, AGENT_NAME)

    # ── Build message ─────────────────────────────────────────────────────────
    message, alert_level = _build_alert_message(state)
    recipients = _get_recipients(state)
    severity_level = state.get("severity_level", "Low")
    dispatch_records: list[dict] = []

    logger.info(f"[NotificationAgent] Dispatching '{alert_level}' alert to {len(recipients)} recipient(s).")

    # ── Dispatch via notification_tool ───────────────────────────────────────
    try:
        from tools.notification_tool import send_sms_alert, send_whatsapp_alert

        for phone in recipients:
            # SMS
            sms_record = send_sms_alert(
                to_phone=phone,
                message=message,
                alert_level=alert_level,
            )
            dispatch_records.append(sms_record)
            logger.info(f"[NotificationAgent] SMS → {phone}: {sms_record.get('status')}")

            # WhatsApp (for High/Critical severity only, to avoid spam)
            if severity_level in ("High", "Critical"):
                wa_record = send_whatsapp_alert(
                    to_phone=phone,
                    message=message,
                    alert_level=alert_level,
                )
                dispatch_records.append(wa_record)
                logger.info(f"[NotificationAgent] WhatsApp → {phone}: {wa_record.get('status')}")

    except Exception as e:
        logger.error(f"[NotificationAgent] Dispatch failed: {e}")
        state = update_state_metadata(state, AGENT_NAME, error=str(e))

    # ── Build summary recommendation ─────────────────────────────────────────
    success_count = sum(1 for r in dispatch_records if r.get("status") in ("Success", "Simulated"))
    fail_count    = len(dispatch_records) - success_count
    elapsed       = round(time.time() - t_start, 2)

    summary_rec = (
        f"[NotificationAgent] {success_count} alert(s) dispatched "
        f"({'CRITICAL' if severity_level == 'Critical' else severity_level} level) "
        f"via SMS/WhatsApp. {fail_count} failed. ({elapsed}s)"
    )

    existing_recs = list(state.get("recommendations") or [])
    existing_recs.append(summary_rec)

    logger.success(f"[NotificationAgent] Done. {success_count}/{len(dispatch_records)} dispatched in {elapsed}s.")

    updated: DisasterState = {
        **state,
        "notification_sent":  True,
        "recommendations":    existing_recs,
    }

    return mark_agent_completed(
        update_state_metadata(updated, AGENT_NAME, data_source="Twilio"),
        AGENT_NAME,
    )
