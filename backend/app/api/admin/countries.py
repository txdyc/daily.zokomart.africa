from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Article, Country, Site
from app.schemas import CountryIn, CountryOut
from app.security import get_current_admin

router = APIRouter(dependencies=[Depends(get_current_admin)])


def _get_or_404(db: Session, country_id: int) -> Country:
    country = db.get(Country, country_id)
    if country is None:
        raise HTTPException(status_code=404, detail="Country not found")
    return country


@router.get("", response_model=list[CountryOut])
def list_countries(db: Session = Depends(get_db)):
    return db.query(Country).order_by(Country.tier, Country.code).all()


@router.post("", response_model=CountryOut, status_code=201)
def create_country(body: CountryIn, db: Session = Depends(get_db)):
    if db.query(Country).filter_by(code=body.code).first() is not None:
        raise HTTPException(status_code=409, detail=f"Country code {body.code} already exists")
    country = Country(**body.model_dump())
    db.add(country)
    db.commit()
    db.refresh(country)
    return country


@router.put("/{country_id}", response_model=CountryOut)
def update_country(country_id: int, body: CountryIn, db: Session = Depends(get_db)):
    country = _get_or_404(db, country_id)
    for field, value in body.model_dump().items():
        setattr(country, field, value)
    db.commit()
    db.refresh(country)
    return country


@router.delete("/{country_id}", status_code=204)
def delete_country(country_id: int, db: Session = Depends(get_db)):
    country = _get_or_404(db, country_id)
    has_children = (
        db.query(Site.id).filter_by(country_id=country_id).first() is not None
        or db.query(Article.id).filter_by(country_id=country_id).first() is not None
    )
    if has_children:
        raise HTTPException(
            status_code=409,
            detail="Country still has sites or articles; delete those first",
        )
    db.delete(country)
    db.commit()
