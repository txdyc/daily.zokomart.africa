from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import STATUS_PENDING_TRANSLATION, Article
from app.schemas import ArticleUpdate
from app.security import get_current_admin

router = APIRouter(dependencies=[Depends(get_current_admin)])


def _admin_view(a: Article) -> dict:
    return {
        "id": a.id,
        "site_id": a.site_id,
        "site_name": a.site.name,
        "country_code": a.country.code,
        "source_url": a.source_url,
        "source_language": a.source_language,
        "title": a.title,
        "title_zh": a.title_zh,
        "category": a.category,
        "main_image_url": a.main_image_url,
        "published_at": a.published_at.isoformat() if a.published_at else None,
        "paragraphs": a.paragraphs,
        "paragraphs_zh": a.paragraphs_zh,
        "status": a.status,
        "translation_error": a.translation_error,
        "is_banner": a.is_banner,
        "created_at": a.created_at.isoformat(),
    }


def _get_or_404(db: Session, article_id: int) -> Article:
    article = db.get(Article, article_id)
    if article is None:
        raise HTTPException(status_code=404, detail="Article not found")
    return article


@router.get("")
def list_articles(
    status: str | None = None,
    country: str | None = None,
    site_id: int | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    q = select(Article)
    if status:
        q = q.where(Article.status == status)
    if site_id:
        q = q.where(Article.site_id == site_id)
    if country:
        from app.models import Country

        q = q.join(Country, Article.country_id == Country.id).where(
            Country.code == country.upper()
        )
    total = db.scalar(select(func.count()).select_from(q.subquery()))
    rows = db.scalars(
        q.order_by(Article.id.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return {
        "items": [_admin_view(a) for a in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.patch("/{article_id}")
def update_article(article_id: int, body: ArticleUpdate, db: Session = Depends(get_db)):
    article = _get_or_404(db, article_id)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(article, field, value)
    db.commit()
    db.refresh(article)
    return _admin_view(article)


@router.post("/{article_id}/retranslate")
def retranslate_article(article_id: int, db: Session = Depends(get_db)):
    article = _get_or_404(db, article_id)
    article.status = STATUS_PENDING_TRANSLATION
    article.translation_error = None
    db.commit()
    db.refresh(article)
    return _admin_view(article)


@router.delete("/{article_id}", status_code=204)
def delete_article(article_id: int, db: Session = Depends(get_db)):
    db.delete(_get_or_404(db, article_id))
    db.commit()
