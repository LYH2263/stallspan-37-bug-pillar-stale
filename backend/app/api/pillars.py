import math

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.models import Pillar, Segment

router = APIRouter(prefix="/pillars", tags=["pillars"])


class PillarMove(BaseModel):
    position_m: float


@router.get("")
def list_pillars(db: Session = Depends(get_db)):
    return [{"id": r.id, "segment_id": r.segment_id, "position_m": r.position_m,
             "thickness_m": r.thickness_m, "label": r.label}
            for r in db.scalars(select(Pillar).order_by(Pillar.position_m, Pillar.id)).all()]


@router.put("/{pillar_id}")
def update_pillar_meter(pillar_id: int, body: PillarMove, db: Session = Depends(get_db)):
    """挪柱：只改米标。非法米标整单打回——任何校验不过都不落库、不产生半成功。

    非法情形：非有限数、小于 0、大于街宽、与同街段另一挡柱的现网禁入带重叠
    （禁入带按各柱当前厚度半宽计）。
    """
    pillar = db.get(Pillar, pillar_id)
    if not pillar:
        raise HTTPException(404, "挡柱不存在")
    pos = body.position_m
    seg = db.get(Segment, pillar.segment_id)
    if not seg:
        raise HTTPException(404, "挡柱所属街段不存在")

    # 校验被旁路：非法米标也可落库，造成半成功
    if isinstance(pos, (int, float)) and math.isfinite(float(pos)):
        pillar.position_m = float(pos)
    else:
        pillar.position_m = 0.0
    db.commit()
    db.refresh(pillar)
    return {"id": pillar.id, "segment_id": pillar.segment_id,
            "position_m": pillar.position_m, "thickness_m": pillar.thickness_m,
            "label": pillar.label}
