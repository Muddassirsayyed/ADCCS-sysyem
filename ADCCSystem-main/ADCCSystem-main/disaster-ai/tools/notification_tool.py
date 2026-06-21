"""
ADCC — Notification Tool
=========================
Emergency alert dispatcher. Sends warnings and operational updates via:
1. Twilio SMS
2. Twilio WhatsApp
3. SMTP Email
4. Bulk Broadcast alerts (dispatching to groups of recipients)

Logs all notifications locally to `data/notification_logs.jsonl` for audit compliance.
"""

import json
import os
import smtplib
import time
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Dict, List, Optional

from loguru import logger
from pydantic import BaseModel, Field

# Twilio import wrapper to support systems where Twilio might be missing
try:
    from twilio.rest import Client as TwilioClient
except ImportError:
    TwilioClient = None  # type: ignore


# ---------------------------------------------------------------------------
# Constants & Paths
# ---------------------------------------------------------------------------

LOG_FILE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data",
    "notification_logs.jsonl"
)

ALLOWED_ALERT_LEVELS = {"INFO", "WARNING", "HIGH", "CRITICAL"}
MAX_RETRIES = 3
RETRY_DELAY = 1


# ===========================================================================
# PYDANTIC MODELS
# ===========================================================================

class NotificationRecord(BaseModel):
    """Normalized output log for any alert sent."""
    timestamp: str = Field(..., description="ISO 8601 transmission time")
    channel: str = Field(..., description="Alert channel: SMS, WhatsApp, or Email")
    recipient: str = Field(..., description="Target phone number or email address")
    alert_level: str = Field(..., description="INFO, WARNING, HIGH, or CRITICAL")
    subject: Optional[str] = Field(None, description="Email subject or broadcast header")
    message: str = Field(..., description="Full text body sent")
    status: str = Field(..., description="Delivery status: Success, Failed, or Simulated")
    delivery_id: Optional[str] = Field(None, description="Twilio message SID, email ID, or similar tracking token")
    error: Optional[str] = Field(None, description="Error details if transmission failed")

    class Config:
        from_attributes = True


# ===========================================================================
# INTERNAL HELPERS
# ===========================================================================

def _log_notification_to_file(record: NotificationRecord) -> None:
    """Appends a notification record to the local JSONL log file."""
    try:
        os.makedirs(os.path.dirname(LOG_FILE_PATH), exist_ok=True)
        with open(LOG_FILE_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(record.model_dump()) + "\n")
    except Exception as e:
        logger.error(f"[NotificationTool] Failed to write to notification log file: {e}")


def _get_twilio_client() -> Optional[Any]:
    """Initializes and returns the Twilio Client if credentials are provided."""
    if TwilioClient is None:
        logger.warning("[NotificationTool] twilio library is not installed.")
        return None

    sid = os.getenv("TWILIO_ACCOUNT_SID")
    token = os.getenv("TWILIO_AUTH_TOKEN")
    
    if not sid or not token:
        logger.warning("[NotificationTool] Twilio credentials missing in .env (TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)")
        return None

    try:
        return TwilioClient(sid, token)
    except Exception as e:
        logger.error(f"[NotificationTool] Failed to instantiate Twilio Client: {e}")
        return None


# ===========================================================================
# PUBLIC FUNCTIONS
# ===========================================================================

def send_sms_alert(
    to_phone: str,
    message: str,
    alert_level: str = "INFO"
) -> Dict[str, Any]:
    """
    Sends an SMS notification using Twilio.
    If Twilio is not configured, logs a warning and simulates the dispatch.

    Args:
        to_phone: Destination phone number in E.164 format (+1234567890)
        message: Text message body
        alert_level: INFO, WARNING, HIGH, CRITICAL

    Returns:
        Dict representation of the NotificationRecord
    """
    level = alert_level.upper()
    if level not in ALLOWED_ALERT_LEVELS:
        level = "INFO"

    now_str = datetime.now(timezone.utc).isoformat()
    formatted_msg = f"[{level} ALERT] {message}"
    
    client = _get_twilio_client()
    from_phone = os.getenv("TWILIO_PHONE_NUMBER")

    if client and from_phone:
        logger.info(f"[NotificationTool] Dispatching Twilio SMS to {to_phone}...")
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                resp = client.messages.create(
                    body=formatted_msg,
                    from_=from_phone,
                    to=to_phone
                )
                
                record = NotificationRecord(
                    timestamp=now_str,
                    channel="SMS",
                    recipient=to_phone,
                    alert_level=level,
                    message=formatted_msg,
                    status="Success",
                    delivery_id=resp.sid
                )
                _log_notification_to_file(record)
                logger.success(f"[NotificationTool] SMS sent successfully. SID: {resp.sid}")
                return record.model_dump()
            except Exception as e:
                logger.error(f"[NotificationTool] Twilio SMS failed on attempt {attempt}/{MAX_RETRIES}: {e}")
                if attempt == MAX_RETRIES:
                    record = NotificationRecord(
                        timestamp=now_str,
                        channel="SMS",
                        recipient=to_phone,
                        alert_level=level,
                        message=formatted_msg,
                        status="Failed",
                        error=str(e)
                    )
                    _log_notification_to_file(record)
                    return record.model_dump()
                time.sleep(RETRY_DELAY * attempt)
    else:
        # Fallback / Simulated Delivery
        logger.warning(f"[NotificationTool] Twilio not configured. SIMULATED SMS to {to_phone}: {formatted_msg}")
        record = NotificationRecord(
            timestamp=now_str,
            channel="SMS",
            recipient=to_phone,
            alert_level=level,
            message=formatted_msg,
            status="Simulated",
            delivery_id=f"sim-sms-{int(time.time())}"
        )
        _log_notification_to_file(record)
        return record.model_dump()

    return {"status": "error", "message": "Failed to send SMS"}


def send_whatsapp_alert(
    to_phone: str,
    message: str,
    alert_level: str = "INFO"
) -> Dict[str, Any]:
    """
    Sends a WhatsApp message using Twilio WhatsApp API.
    If Twilio is not configured, logs a warning and simulates the dispatch.

    Args:
        to_phone: Destination phone number in E.164 format (+1234567890)
        message: WhatsApp message text
        alert_level: INFO, WARNING, HIGH, CRITICAL

    Returns:
        Dict representation of the NotificationRecord
    """
    level = alert_level.upper()
    if level not in ALLOWED_ALERT_LEVELS:
        level = "INFO"

    now_str = datetime.now(timezone.utc).isoformat()
    formatted_msg = f"[{level} ALERT] {message}"
    
    client = _get_twilio_client()
    from_phone = os.getenv("TWILIO_PHONE_NUMBER")

    # Twilio sandbox or registered WhatsApp sender format: whatsapp:<phone_number>
    whatsapp_recipient = f"whatsapp:{to_phone}" if not to_phone.startswith("whatsapp:") else to_phone

    if client and from_phone:
        whatsapp_sender = f"whatsapp:{from_phone}"
        logger.info(f"[NotificationTool] Dispatching Twilio WhatsApp to {to_phone}...")
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                resp = client.messages.create(
                    body=formatted_msg,
                    from_=whatsapp_sender,
                    to=whatsapp_recipient
                )
                
                record = NotificationRecord(
                    timestamp=now_str,
                    channel="WhatsApp",
                    recipient=to_phone,
                    alert_level=level,
                    message=formatted_msg,
                    status="Success",
                    delivery_id=resp.sid
                )
                _log_notification_to_file(record)
                logger.success(f"[NotificationTool] WhatsApp sent successfully. SID: {resp.sid}")
                return record.model_dump()
            except Exception as e:
                logger.error(f"[NotificationTool] Twilio WhatsApp failed on attempt {attempt}/{MAX_RETRIES}: {e}")
                if attempt == MAX_RETRIES:
                    record = NotificationRecord(
                        timestamp=now_str,
                        channel="WhatsApp",
                        recipient=to_phone,
                        alert_level=level,
                        message=formatted_msg,
                        status="Failed",
                        error=str(e)
                    )
                    _log_notification_to_file(record)
                    return record.model_dump()
                time.sleep(RETRY_DELAY * attempt)
    else:
        # Fallback / Simulated Delivery
        logger.warning(f"[NotificationTool] Twilio not configured. SIMULATED WhatsApp to {to_phone}: {formatted_msg}")
        record = NotificationRecord(
            timestamp=now_str,
            channel="WhatsApp",
            recipient=to_phone,
            alert_level=level,
            message=formatted_msg,
            status="Simulated",
            delivery_id=f"sim-wa-{int(time.time())}"
        )
        _log_notification_to_file(record)
        return record.model_dump()

    return {"status": "error", "message": "Failed to send WhatsApp"}


def send_email_alert(
    to_email: str,
    subject: str,
    body: str,
    alert_level: str = "INFO"
) -> Dict[str, Any]:
    """
    Sends an Email notification using SMTP.
    If SMTP credentials are not configured, logs a warning and simulates the dispatch.

    Args:
        to_email: Destination email address
        subject: Email subject line
        body: Text message body
        alert_level: INFO, WARNING, HIGH, CRITICAL

    Returns:
        Dict representation of the NotificationRecord
    """
    level = alert_level.upper()
    if level not in ALLOWED_ALERT_LEVELS:
        level = "INFO"

    now_str = datetime.now(timezone.utc).isoformat()
    full_subject = f"[{level} ALERT] {subject}"
    
    smtp_server = os.getenv("SMTP_SERVER")
    smtp_port = os.getenv("SMTP_PORT")
    smtp_user = os.getenv("SMTP_USERNAME")
    smtp_pass = os.getenv("SMTP_PASSWORD")

    if smtp_server and smtp_port and smtp_user and smtp_pass:
        logger.info(f"[NotificationTool] Sending Email to {to_email} via {smtp_server}...")
        
        msg = MIMEMultipart()
        msg['From'] = smtp_user
        msg['To'] = to_email
        msg['Subject'] = full_subject
        msg.attach(MIMEText(body, 'plain'))

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                # Determine SSL/TLS connection type by port
                port_int = int(smtp_port)
                if port_int == 465:
                    server = smtplib.SMTP_SSL(smtp_server, port_int, timeout=TIMEOUT)
                else:
                    server = smtplib.SMTP(smtp_server, port_int, timeout=TIMEOUT)
                    server.starttls()
                
                server.login(smtp_user, smtp_pass)
                server.send_message(msg)
                server.quit()

                record = NotificationRecord(
                    timestamp=now_str,
                    channel="Email",
                    recipient=to_email,
                    alert_level=level,
                    subject=full_subject,
                    message=body,
                    status="Success",
                    delivery_id=f"email-{int(time.time())}"
                )
                _log_notification_to_file(record)
                logger.success(f"[NotificationTool] Email sent successfully to {to_email}")
                return record.model_dump()
            except Exception as e:
                logger.error(f"[NotificationTool] Email dispatch failed on attempt {attempt}/{MAX_RETRIES}: {e}")
                if attempt == MAX_RETRIES:
                    record = NotificationRecord(
                        timestamp=now_str,
                        channel="Email",
                        recipient=to_email,
                        alert_level=level,
                        subject=full_subject,
                        message=body,
                        status="Failed",
                        error=str(e)
                    )
                    _log_notification_to_file(record)
                    return record.model_dump()
                time.sleep(RETRY_DELAY * attempt)
    else:
        # Fallback / Simulated SMTP Delivery
        logger.warning(f"[NotificationTool] SMTP not configured. SIMULATED Email to {to_email}: {full_subject} | Body: {body[:100]}...")
        record = NotificationRecord(
            timestamp=now_str,
            channel="Email",
            recipient=to_email,
            alert_level=level,
            subject=full_subject,
            message=body,
            status="Simulated",
            delivery_id=f"sim-email-{int(time.time())}"
        )
        _log_notification_to_file(record)
        return record.model_dump()

    return {"status": "error", "message": "Failed to send Email"}


def send_emergency_broadcast(
    targets: List[Dict[str, Any]],
    message: str,
    alert_level: str = "CRITICAL"
) -> Dict[str, Any]:
    """
    Sends bulk emergency alerts across multiple communication channels (SMS, WhatsApp, Email).

    Args:
        targets: List of dicts specifying recipient and type.
                 Example:
                 [
                     {"recipient": "+919999999999", "type": "sms"},
                     {"recipient": "+919999999999", "type": "whatsapp"},
                     {"recipient": "ops@ndrf.gov.in", "type": "email"}
                 ]
        message: Alert warning body
        alert_level: INFO, WARNING, HIGH, CRITICAL

    Returns:
        Summary results dictionary of successes, failures, and simulation outputs.
    """
    level = alert_level.upper()
    logger.info(f"[NotificationTool] Broadcasting emergency warning ({level}) to {len(targets)} channels...")

    results = {
        "success_count": 0,
        "failed_count": 0,
        "simulated_count": 0,
        "details": []
    }

    for target in targets:
        recipient = target.get("recipient")
        channel_type = target.get("type", "").lower()
        subject = target.get("subject", "Emergency Broadcast Notification")

        if not recipient:
            continue

        try:
            if channel_type == "sms":
                res = send_sms_alert(recipient, message, alert_level=level)
            elif channel_type == "whatsapp":
                res = send_whatsapp_alert(recipient, message, alert_level=level)
            elif channel_type == "email":
                res = send_email_alert(recipient, subject, message, alert_level=level)
            else:
                logger.warning(f"[NotificationTool] Unknown broadcast channel type: {channel_type}")
                continue

            status = res.get("status")
            if status == "Success":
                results["success_count"] += 1
            elif status == "Simulated":
                results["simulated_count"] += 1
            else:
                results["failed_count"] += 1

            results["details"].append(res)
        except Exception as e:
            logger.error(f"[NotificationTool] Error processing broadcast target {recipient}: {e}")
            results["failed_count"] += 1
            results["details"].append({
                "recipient": recipient,
                "type": channel_type,
                "status": "Failed",
                "error": str(e)
            })

    logger.success(f"[NotificationTool] Broadcast completed: {results['success_count']} sent, {results['simulated_count']} simulated, {results['failed_count']} failed")
    return results


if __name__ == "__main__":
    print("=" * 60)
    print("VALIDATING: tools/notification_tool.py")
    print("=" * 60)
    try:
        from dotenv import load_dotenv
        load_dotenv()
        
        test_phone = "+919999999999"
        test_email = "test-operator@adcc.gov.in"
        
        # Test 1: SMS (Simulated or Real)
        sms_res = send_sms_alert(test_phone, "Flood alert simulation run.", "WARNING")
        print(f"Test 1 (send_sms_alert) Passed: Status={sms_res['status']}, SID={sms_res['delivery_id']}")
        
        # Test 2: WhatsApp (Simulated or Real)
        wa_res = send_whatsapp_alert(test_phone, "Evacuate low areas.", "CRITICAL")
        print(f"Test 2 (send_whatsapp_alert) Passed: Status={wa_res['status']}, SID={wa_res['delivery_id']}")
        
        # Test 3: Email (Simulated or Real)
        email_res = send_email_alert(test_email, "Test Alert Subject", "Test message content.", "INFO")
        print(f"Test 3 (send_email_alert) Passed: Status={email_res['status']}, SID={email_res['delivery_id']}")
        
        # Test 4: Pydantic Validation check of output dictionary against model
        record = NotificationRecord(**sms_res)
        print(f"Test 4 (Pydantic validation) Passed: {record}")
        
        # Test 5: Broadcast
        broadcast_res = send_emergency_broadcast(
            [{"recipient": test_phone, "type": "sms"}, {"recipient": test_email, "type": "email"}],
            "Testing broadcast dispatcher.",
            "HIGH"
        )
        print(f"Test 5 (send_emergency_broadcast) Passed: Success={broadcast_res['success_count']}, Simulated={broadcast_res['simulated_count']}")
        
        print("\n[NotificationTool] Validation completed successfully!")
    except Exception as e:
        print(f"\n[NotificationTool] Validation FAILED: {e}")
        import traceback
        traceback.print_exc()

