import pytest

import app.translate.translator as tr
from app.models import AppConfig, Article, Country, Site
from app.translate.client import AIError


@pytest.fixture()
def article(db_session):
    gh = Country(code="GH", name_en="Ghana", name_zh="加纳", flag_emoji="🇬🇭")
    site = Site(country=gh, name="MyJoyOnline", base_url="https://www.myjoyonline.com",
                language="en", discovery_method="rss")
    a = Article(site=site, country=gh, source_url="https://x/1", source_language="en",
                title="Economy grows", paragraphs=["Para one text.", "Para two text."],
                status="pending_translation")
    db_session.add(a)
    db_session.add(AppConfig(key="ai_api_key", value="sk-test"))
    db_session.commit()
    return a


GOOD = {"title_zh": "经济增长", "paragraphs_zh": ["第一段。", "第二段。"], "category": "business"}


def test_translate_success_publishes(monkeypatch, db_session, article):
    monkeypatch.setattr(tr, "chat_json", lambda db, s, u: dict(GOOD))
    tr.translate_article(db_session, article)
    assert article.status == "published"
    assert article.title_zh == "经济增长"
    assert article.paragraphs_zh == ["第一段。", "第二段。"]
    assert article.category == "business"
    assert article.translation_error is None


def test_count_mismatch_retries_then_succeeds(monkeypatch, db_session, article):
    responses = [
        {"title_zh": "经济增长", "paragraphs_zh": ["只有一段。"], "category": "business"},
        dict(GOOD),
    ]
    monkeypatch.setattr(tr, "chat_json", lambda db, s, u: responses.pop(0))
    tr.translate_article(db_session, article)
    assert article.status == "published"


def test_count_mismatch_twice_fails(monkeypatch, db_session, article):
    bad = {"title_zh": "经济增长", "paragraphs_zh": ["只有一段。"], "category": "business"}
    monkeypatch.setattr(tr, "chat_json", lambda db, s, u: dict(bad))
    tr.translate_article(db_session, article)
    assert article.status == "translation_failed"
    assert "mismatch" in article.translation_error


def test_unknown_category_coerced_to_society(monkeypatch, db_session, article):
    data = dict(GOOD, category="astrology")
    monkeypatch.setattr(tr, "chat_json", lambda db, s, u: dict(data))
    tr.translate_article(db_session, article)
    assert article.category == "society"


def test_api_error_marks_failed(monkeypatch, db_session, article):
    def boom(db, s, u):
        raise AIError("500 from provider")

    monkeypatch.setattr(tr, "chat_json", boom)
    tr.translate_article(db_session, article)
    assert article.status == "translation_failed"
    assert "500 from provider" in article.translation_error


def test_sweep_without_key_leaves_articles_pending(monkeypatch, db_session, article):
    db_session.query(AppConfig).filter_by(key="ai_api_key").update({"value": ""})
    db_session.commit()
    assert tr.run_translation_sweep(db_session) == 0
    assert article.status == "pending_translation"


def test_sweep_translates_batch(monkeypatch, db_session, article):
    monkeypatch.setattr(tr, "chat_json", lambda db, s, u: dict(GOOD))
    assert tr.run_translation_sweep(db_session) == 1
    assert article.status == "published"
