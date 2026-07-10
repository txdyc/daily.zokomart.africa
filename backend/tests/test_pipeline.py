import pytest

import app.crawler.pipeline as pl
from app.crawler.contracts import (
    CandidateArticle,
    DiscoveryError,
    ExtractedArticle,
    ExtractionFailed,
    FetchedPage,
)
from app.models import Article, Country, CrawlRun, Site


@pytest.fixture(autouse=True)
def no_delay(monkeypatch):
    monkeypatch.setattr(pl, "ARTICLE_DELAY_SECONDS", 0)


@pytest.fixture()
def site(db_session):
    gh = Country(code="GH", name_en="Ghana", name_zh="加纳", flag_emoji="🇬🇭")
    s = Site(country=gh, name="MyJoyOnline", base_url="https://www.myjoyonline.com",
             language="en", discovery_method="rss", feed_url="https://x/feed")
    db_session.add(s)
    db_session.commit()
    return s


GOOD_EXTRACT = ExtractedArticle(
    title="A story", paragraphs=["One paragraph.", "Two paragraphs."],
    main_image_url="https://cdn/x.jpg",
)


def test_crawl_site_stores_new_articles(monkeypatch, db_session, site):
    monkeypatch.setattr(pl, "discover", lambda s, fetch_text: [
        CandidateArticle(url="https://x/a1"), CandidateArticle(url="https://x/a2"),
    ])
    monkeypatch.setattr(pl, "fetch_page_with_retry", lambda url: FetchedPage(url=url, html="<html>"))
    monkeypatch.setattr(pl, "extract", lambda page, s: GOOD_EXTRACT)

    run = pl.crawl_site(db_session, site)
    assert run.status == "success"
    assert run.articles_found == 2
    assert run.articles_new == 2
    assert db_session.query(Article).count() == 2
    stored = db_session.query(Article).first()
    assert stored.status == "pending_translation"
    assert stored.source_language == "en"
    assert site.last_crawl_status == "success: 2 new"
    assert site.last_crawl_at is not None


def test_crawl_site_dedupes_existing_urls(monkeypatch, db_session, site):
    db_session.add(Article(site_id=site.id, country_id=site.country_id,
                           source_url="https://x/a1", source_language="en",
                           title="old", paragraphs=["p"]))
    db_session.commit()
    monkeypatch.setattr(pl, "discover", lambda s, fetch_text: [
        CandidateArticle(url="https://x/a1"), CandidateArticle(url="https://x/a2"),
    ])
    monkeypatch.setattr(pl, "fetch_page_with_retry", lambda url: FetchedPage(url=url, html="<html>"))
    monkeypatch.setattr(pl, "extract", lambda page, s: GOOD_EXTRACT)

    run = pl.crawl_site(db_session, site)
    assert run.articles_found == 2
    assert run.articles_new == 1


def test_one_bad_article_does_not_abort_run(monkeypatch, db_session, site):
    monkeypatch.setattr(pl, "discover", lambda s, fetch_text: [
        CandidateArticle(url="https://x/bad"), CandidateArticle(url="https://x/good"),
    ])

    def fetch(url):
        if url.endswith("bad"):
            raise pl.FetchError("timeout twice")
        return FetchedPage(url=url, html="<html>")

    monkeypatch.setattr(pl, "fetch_page_with_retry", fetch)
    monkeypatch.setattr(pl, "extract", lambda page, s: GOOD_EXTRACT)

    run = pl.crawl_site(db_session, site)
    assert run.status == "success"
    assert run.articles_found == 2
    assert run.articles_new == 1
    assert "https://x/bad" in run.error


def test_extraction_failure_falls_back_to_llm(monkeypatch, db_session, site):
    monkeypatch.setattr(pl, "discover", lambda s, fetch_text: [CandidateArticle(url="https://x/a1")])
    monkeypatch.setattr(pl, "fetch_page_with_retry", lambda url: FetchedPage(url=url, html="<html>"))

    def failing_extract(page, s):
        raise ExtractionFailed("thin page")

    monkeypatch.setattr(pl, "extract", failing_extract)
    monkeypatch.setattr(pl, "extract_with_llm", lambda db, html: GOOD_EXTRACT)

    run = pl.crawl_site(db_session, site)
    assert run.articles_new == 1


def test_discovery_error_fails_run(monkeypatch, db_session, site):
    def boom(s, fetch_text):
        raise DiscoveryError("feed 404")

    monkeypatch.setattr(pl, "discover", boom)
    run = pl.crawl_site(db_session, site)
    assert run.status == "failed"
    assert "feed 404" in run.error
    assert site.last_crawl_status.startswith("failed:")


def test_crawl_site_reuses_provided_run(monkeypatch, db_session, site):
    monkeypatch.setattr(pl, "discover", lambda s, fetch_text: [])
    pre = CrawlRun(site_id=site.id, status="running")
    db_session.add(pre)
    db_session.commit()
    run = pl.crawl_site(db_session, site, run=pre)
    assert run.id == pre.id
    assert db_session.query(CrawlRun).count() == 1
