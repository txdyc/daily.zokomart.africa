import json

import pytest

import app.translate.client as client_mod
from app.crawler.llm_extractor import extract_with_llm
from app.models import AppConfig
from app.translate.client import AIConfigMissing, AIError, chat_json


@pytest.fixture()
def ai_config(db_session):
    db_session.add_all([
        AppConfig(key="ai_base_url", value="https://api.test/v1"),
        AppConfig(key="ai_api_key", value="sk-test"),
        AppConfig(key="ai_model", value="test-model"),
    ])
    db_session.commit()


class FakeResponse:
    def __init__(self, content):
        self._content = content

    def raise_for_status(self):
        pass

    def json(self):
        return {"choices": [{"message": {"content": self._content}}]}


def test_chat_json_posts_and_parses(monkeypatch, db_session, ai_config):
    captured = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["model"] = json["model"]
        return FakeResponse('{"answer": 42}')

    monkeypatch.setattr(client_mod.httpx, "post", fake_post)
    assert chat_json(db_session, "sys", "user") == {"answer": 42}
    assert captured["url"] == "https://api.test/v1/chat/completions"
    assert captured["model"] == "test-model"


def test_chat_json_missing_key_raises(db_session):
    with pytest.raises(AIConfigMissing):
        chat_json(db_session, "sys", "user")


def test_chat_json_bad_json_raises_ai_error(monkeypatch, db_session, ai_config):
    monkeypatch.setattr(
        client_mod.httpx, "post",
        lambda url, headers=None, json=None, timeout=None: FakeResponse("not json"),
    )
    with pytest.raises(AIError):
        chat_json(db_session, "sys", "user")


def test_extract_with_llm_parses_article(monkeypatch, db_session, ai_config):
    payload = {
        "title": "Extracted title",
        "paragraphs": ["First paragraph text.", "  ", "Second paragraph text."],
        "image_url": "https://cdn.example/x.jpg",
        "published_at": "2026-07-09T08:00:00Z",
    }
    monkeypatch.setattr(
        client_mod.httpx, "post",
        lambda url, headers=None, json=None, timeout=None: FakeResponse(
            __import__("json").dumps(payload)
        ),
    )
    got = extract_with_llm(db_session, "<html><script>x</script><p>body</p></html>")
    assert got.title == "Extracted title"
    assert got.paragraphs == ["First paragraph text.", "Second paragraph text."]
    assert got.main_image_url == "https://cdn.example/x.jpg"
    assert got.published_at is not None
