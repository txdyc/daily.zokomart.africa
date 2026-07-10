from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.security import get_current_admin
from app.services.config_service import get_config, mask_secret, set_config
from app.translate.translator import _translate_with_retry

router = APIRouter(dependencies=[Depends(get_current_admin)])

SAMPLE_TITLE = "Ghana's economy shows steady growth"
SAMPLE_PARAGRAPHS = ["The Ghanaian economy expanded in the second quarter, driven by exports."]


class ConfigUpdate(BaseModel):
    ai_base_url: str | None = None
    ai_api_key: str | None = None
    ai_model: str | None = None


def _config_view(db: Session) -> dict:
    return {
        "ai_base_url": get_config(db, "ai_base_url"),
        "ai_api_key_masked": mask_secret(get_config(db, "ai_api_key")),
        "ai_model": get_config(db, "ai_model"),
    }


@router.get("")
def read_config(db: Session = Depends(get_db)):
    return _config_view(db)


@router.put("")
def update_config(body: ConfigUpdate, db: Session = Depends(get_db)):
    for key, value in body.model_dump(exclude_unset=True, exclude_none=True).items():
        set_config(db, key, value)
    db.commit()
    return _config_view(db)


import json
import time


@router.post("/test-translation")
def test_translation(db: Session = Depends(get_db)):
    payload = json.dumps(
        {"title": SAMPLE_TITLE, "paragraphs": SAMPLE_PARAGRAPHS}, ensure_ascii=False
    )
    start = time.monotonic()
    try:
        data = _translate_with_retry(db, payload, expected=1)
        return {
            "ok": True,
            "title_zh": data["title_zh"],
            "paragraph_zh": data["paragraphs_zh"][0],
            "latency_ms": round((time.monotonic() - start) * 1000),
        }
    except Exception as e:
        return {"ok": False, "error": str(e)[:500]}
