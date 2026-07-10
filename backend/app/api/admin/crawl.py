import threading

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import CrawlRun, Site
from app.security import get_current_admin

router = APIRouter(dependencies=[Depends(get_current_admin)])


def start_crawl_thread(site_id: int, run_id: int) -> None:
    """Run one site crawl in a daemon thread with its own DB session."""

    def _work() -> None:
        from app.crawler.pipeline import crawl_site
        from app.db import SessionLocal

        with SessionLocal() as db:
            site = db.get(Site, site_id)
            run = db.get(CrawlRun, run_id)
            if site is not None and run is not None:
                crawl_site(db, site, run=run)

    threading.Thread(target=_work, daemon=True).start()


def _run_view(r: CrawlRun) -> dict:
    return {
        "id": r.id,
        "site_id": r.site_id,
        "site_name": r.site.name,
        "started_at": r.started_at.isoformat() if r.started_at else None,
        "finished_at": r.finished_at.isoformat() if r.finished_at else None,
        "status": r.status,
        "articles_found": r.articles_found,
        "articles_new": r.articles_new,
        "error": r.error,
    }


@router.get("/crawl-runs")
def list_crawl_runs(
    site_id: int | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    q = select(CrawlRun)
    if site_id:
        q = q.where(CrawlRun.site_id == site_id)
    total = db.scalar(select(func.count()).select_from(q.subquery()))
    rows = db.scalars(
        q.order_by(CrawlRun.id.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return {
        "items": [_run_view(r) for r in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.post("/sites/{site_id}/crawl", status_code=202)
def trigger_crawl(site_id: int, db: Session = Depends(get_db)):
    site = db.get(Site, site_id)
    if site is None:
        raise HTTPException(status_code=404, detail="Site not found")
    already = db.scalar(
        select(CrawlRun.id).where(CrawlRun.site_id == site_id, CrawlRun.status == "running")
    )
    if already:
        raise HTTPException(status_code=409, detail="A crawl is already running for this site")
    run = CrawlRun(site_id=site_id, status="running")
    db.add(run)
    db.commit()
    start_crawl_thread(site_id, run.id)
    return {"crawl_run_id": run.id}
