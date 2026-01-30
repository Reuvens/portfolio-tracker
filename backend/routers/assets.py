from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from ..models import Asset, User
from ..database import get_session

router = APIRouter(prefix="/assets", tags=["assets"])

@router.post("/", response_model=Asset)
def create_asset(asset: Asset, session: Session = Depends(get_session)):
    session.add(asset)
    session.commit()
    session.refresh(asset)
    return asset

@router.get("/", response_model=list[Asset])
def read_assets(user_id: int, session: Session = Depends(get_session)):
    statement = select(Asset).where(Asset.user_id == user_id)
    results = session.exec(statement).all()
    return results

@router.delete("/{asset_id}")
def delete_asset(asset_id: int, session: Session = Depends(get_session)):
    asset = session.get(Asset, asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    session.delete(asset)
    session.commit()
    return {"ok": True}
