"""SMS provider abstraction. Provider chosen via app_config key lg_sms_provider:
"mock" (default: log only, always succeeds) or "arkesel" (https://developers.arkesel.com).
Never raises — failures are recorded in SmsLog and reported as False."""

import httpx
from sqlalchemy.orm import Session

from app.logistics.models import SmsLog
from app.services.config_service import get_config

ARKESEL_URL = "https://sms.arkesel.com/api/v2/sms/send"


def send_sms(db: Session, phone: str, body: str, kind: str = "generic") -> bool:
    provider = get_config(db, "lg_sms_provider", "mock")
    status, response = "sent", ""
    if provider == "arkesel":
        try:
            resp = httpx.post(
                ARKESEL_URL,
                headers={"api-key": get_config(db, "lg_sms_api_key", "")},
                json={
                    "sender": get_config(db, "lg_sms_sender_id", "ZokoDaily"),
                    "message": body,
                    "recipients": [phone],
                },
                timeout=15,
            )
            response = resp.text[:500]
            if resp.status_code >= 400:
                status = "failed"
        except Exception as exc:  # network errors must never break the caller
            status, response = "failed", str(exc)[:500]
    db.add(SmsLog(phone=phone, kind=kind, body=body, provider=provider,
                  status=status, response=response))
    db.commit()
    return status == "sent"
