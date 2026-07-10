from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import STATUS_PUBLISHED, Article, Country

router = APIRouter()


def _card(a: Article) -> dict:
    return {
        "id": a.id,
        "title": a.title,
        "title_zh": a.title_zh,
        "main_image_url": a.main_image_url,
        "published_at": a.published_at.isoformat() if a.published_at else None,
        "category": a.category,
        "country": {
            "code": a.country.code,
            "name_en": a.country.name_en,
            "name_zh": a.country.name_zh,
            "flag_emoji": a.country.flag_emoji,
        },
    }


@router.get("/articles")
def list_articles(
    country: str | None = None,
    category: str | None = None,
    search: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    db: Session = Depends(get_db),
):
    q = select(Article).join(Country, Article.country_id == Country.id).where(
        Article.status == STATUS_PUBLISHED
    )
    if country:
        q = q.where(Country.code == country.upper())
    if category:
        q = q.where(Article.category == category)
    if search:
        like = f"%{search}%"
        q = q.where(or_(Article.title.like(like), Article.title_zh.like(like)))

    total = db.scalar(select(func.count()).select_from(q.subquery()))
    rows = db.scalars(
        q.order_by(Article.published_at.desc(), Article.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return {"items": [_card(a) for a in rows], "total": total, "page": page, "page_size": page_size}


@router.get("/articles/banner")
def banner_articles(db: Session = Depends(get_db)):
    flagged = list(
        db.scalars(
            select(Article)
            .where(Article.status == STATUS_PUBLISHED, Article.is_banner.is_(True))
            .order_by(Article.published_at.desc(), Article.id.desc())
            .limit(5)
        )
    )
    if len(flagged) < 5:
        taken = [a.id for a in flagged] or [0]
        fill = db.scalars(
            select(Article)
            .where(Article.status == STATUS_PUBLISHED, Article.id.not_in(taken))
            .order_by(Article.published_at.desc(), Article.id.desc())
            .limit(5 - len(flagged))
        )
        flagged.extend(fill)
    return [_card(a) for a in flagged]


@router.get("/articles/{article_id}")
def article_detail(article_id: int, db: Session = Depends(get_db)):
    a = db.get(Article, article_id)
    if a is None or a.status != STATUS_PUBLISHED:
        raise HTTPException(status_code=404, detail="Article not found")
    d = _card(a)
    d.update(
        {
            "source_language": a.source_language,
            "paragraphs": a.paragraphs,
            "paragraphs_zh": a.paragraphs_zh,
            "site": {"name": a.site.name, "url": a.source_url},
        }
    )
    return d
