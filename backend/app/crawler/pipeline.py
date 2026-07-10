import logging
import time

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.crawler.contracts import DiscoveryError, ExtractionFailed, FetchError
from app.crawler.discovery import discover
from app.crawler.extractor import extract
from app.crawler.fetcher import fetch_page_with_retry, fetch_text, fetch_text_rendered
from app.crawler.llm_extractor import extract_with_llm
from app.models import STATUS_PENDING_TRANSLATION, Article, CrawlRun, Site
from app.timeutil import to_naive_utc, utcnow_naive

logger = logging.getLogger(__name__)

ARTICLE_DELAY_SECONDS = 3
ERROR_MAX_CHARS = 2000
STATUS_MAX_CHARS = 500


def crawl_site(db: Session, site: Site, run: CrawlRun | None = None) -> CrawlRun:
    """Run the full discover→fetch→extract→store pipeline for one site.

    Never raises: all failures end up on the CrawlRun / Site status fields.
    """
    if run is None:
        run = CrawlRun(site_id=site.id, status="running")
        db.add(run)
        db.commit()

    failures: list[str] = []
    new_count = 0
    try:
        discovery_fetcher = (
            fetch_text if site.discovery_method == "rss" else fetch_text_rendered
        )
        candidates = discover(site, fetch_text=discovery_fetcher)
        run.articles_found = len(candidates)
        db.commit()
        fresh = [
            c
            for c in candidates
            if db.scalar(select(Article.id).where(Article.source_url == c.url)) is None
        ]
        for i, cand in enumerate(fresh):
            if i > 0 and ARTICLE_DELAY_SECONDS:
                time.sleep(ARTICLE_DELAY_SECONDS)
            try:
                page = fetch_page_with_retry(cand.url)
                try:
                    extracted = extract(page, site)
                except ExtractionFailed:
                    extracted = extract_with_llm(db, page.html)
                db.add(
                    Article(
                        site_id=site.id,
                        country_id=site.country_id,
                        source_url=cand.url,
                        source_language=site.language,
                        title=extracted.title,
                        paragraphs=extracted.paragraphs,
                        main_image_url=extracted.main_image_url,
                        published_at=to_naive_utc(
                            extracted.published_at or cand.published_at
                        ),
                        status=STATUS_PENDING_TRANSLATION,
                    )
                )
                db.commit()
                new_count += 1
            except Exception as e:  # per-article failure: skip, continue
                db.rollback()
                failures.append(f"{cand.url}: {e}")
                logger.warning("article failed for %s: %s", cand.url, e)
        run.status = "success"
        if failures:
            run.error = (
                f"{len(failures)} article(s) failed: " + "; ".join(failures)
            )[:ERROR_MAX_CHARS]
    except DiscoveryError as e:
        run.status = "failed"
        run.error = str(e)[:ERROR_MAX_CHARS]
    except Exception as e:  # unexpected: never propagate out of a crawl
        db.rollback()
        run.status = "failed"
        run.error = f"unexpected: {e}"[:ERROR_MAX_CHARS]
        logger.exception("unexpected crawl failure for site %s", site.name)

    run.articles_new = new_count
    run.finished_at = utcnow_naive()
    site.last_crawl_at = run.finished_at
    site.last_crawl_status = (
        f"success: {new_count} new"
        if run.status == "success"
        else f"failed: {run.error}"[:STATUS_MAX_CHARS]
    )
    db.commit()
    return run
