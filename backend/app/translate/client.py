import json

import httpx
from sqlalchemy.orm import Session

from app.services.config_service import get_config

REQUEST_TIMEOUT_SECONDS = 120.0


class AIConfigMissing(Exception):
    pass


class AIError(Exception):
    pass


def chat_json(db: Session, system: str, user: str) -> dict:
    """One JSON-mode chat completion against the admin-configured OpenAI-compatible API.

    Config is read fresh from app_config on every call so admin changes apply
    without a restart.
    """
    base_url = get_config(db, "ai_base_url")
    api_key = get_config(db, "ai_api_key")
    model = get_config(db, "ai_model")
    if not api_key:
        raise AIConfigMissing("AI API key not configured")
    try:
        resp = httpx.post(
            f"{base_url.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": model,
                "temperature": 0.2,
                "response_format": {"type": "json_object"},
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            },
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]
        return json.loads(content)
    except (httpx.HTTPError, KeyError, IndexError, json.JSONDecodeError) as e:
        raise AIError(f"AI request failed: {e}") from e
