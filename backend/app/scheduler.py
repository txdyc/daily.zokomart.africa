import logging

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import select

logger = logging.getLogger(__name__)


def crawl_tier(tier: int) -> None:
    from app.crawler.pipeline import crawl_site
    from app.db import SessionLocal
    from app.models import Site

    with SessionLocal() as db:
        sites = db.scalars(
            select(Site).where(Site.tier == tier, Site.enabled.is_(True)).order_by(Site.id)
        ).all()
        logger.info("tier %d crawl: %d site(s)", tier, len(sites))
        for site in sites:
            try:
                crawl_site(db, site)
            except Exception:
                logger.exception("crawl_site escaped for %s", site.name)


def translation_job() -> None:
    from app.db import SessionLocal
    from app.translate.translator import run_translation_sweep

    with SessionLocal() as db:
        processed = run_translation_sweep(db)
        if processed:
            logger.info("translation sweep processed %d article(s)", processed)


def build_scheduler() -> BackgroundScheduler:
    sched = BackgroundScheduler()
    common = {"max_instances": 1, "coalesce": True}
    sched.add_job(crawl_tier, "interval", hours=1, args=[1], id="crawl-tier-1", **common)
    sched.add_job(crawl_tier, "interval", hours=6, args=[2], id="crawl-tier-2", **common)
    sched.add_job(crawl_tier, "interval", days=1, args=[3], id="crawl-tier-3", **common)
    sched.add_job(translation_job, "interval", minutes=5, id="translation-sweep", **common)
    return sched
