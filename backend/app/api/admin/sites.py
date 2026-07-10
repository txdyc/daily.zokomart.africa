from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Article, Country, Site
from app.schemas import SiteIn, SiteOut
from app.security import get_current_admin

router = APIRouter(dependencies=[Depends(get_current_admin)])


def _get_or_404(db: Session, site_id: int) -> Site:
    site = db.get(Site, site_id)
    if site is None:
        raise HTTPException(status_code=404, detail="Site not found")
    return site


@router.get("", response_model=list[SiteOut])
def list_sites(db: Session = Depends(get_db)):
    return db.query(Site).order_by(Site.tier, Site.name).all()


@router.post("", response_model=SiteOut, status_code=201)
def create_site(body: SiteIn, db: Session = Depends(get_db)):
    if db.get(Country, body.country_id) is None:
        raise HTTPException(status_code=422, detail=f"country_id {body.country_id} does not exist")
    if db.query(Site.id).filter_by(base_url=body.base_url).first() is not None:
        raise HTTPException(status_code=409, detail=f"Site with base_url {body.base_url} already exists")
    site = Site(**body.model_dump())
    db.add(site)
    db.commit()
    db.refresh(site)
    return site


@router.put("/{site_id}", response_model=SiteOut)
def update_site(site_id: int, body: SiteIn, db: Session = Depends(get_db)):
    site = _get_or_404(db, site_id)
    if db.get(Country, body.country_id) is None:
        raise HTTPException(status_code=422, detail=f"country_id {body.country_id} does not exist")
    for field, value in body.model_dump().items():
        setattr(site, field, value)
    db.commit()
    db.refresh(site)
    return site


@router.delete("/{site_id}", status_code=204)
def delete_site(site_id: int, db: Session = Depends(get_db)):
    site = _get_or_404(db, site_id)
    if db.query(Article.id).filter_by(site_id=site_id).first() is not None:
        raise HTTPException(
            status_code=409,
            detail="Site still has articles; delete those first",
        )
    db.delete(site)
    db.commit()
