"""波次路由：规则、生成、进度、中止。"""
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.deps import require_permission
from src.core.exceptions import NotFoundException, ValidationException, success_response
from src.db import get_db
from src.models import User
from src.plugins.builtin.wms_outbound import models as m
from src.plugins.builtin.wms_outbound.wave_service import (
    cancel_wave,
    create_wave,
    schedule_generation,
)
from src.plugins.builtin.wms_outbound.wave_seed import (
    SeedError,
    init_cells,
    scan_to_cell,
)

router = APIRouter(prefix="/wms-outbound", tags=["波次"])


# ── 波次规则 ──────────────────────────────────────────


class WaveRuleIn(BaseModel):
    code: str = Field(..., max_length=32)
    name: str
    cutoff_at: Optional[str] = Field(None, pattern=r"^\d{2}:\d{2}$")
    carrier_code: Optional[str] = None
    region_prefix: Optional[str] = None
    hot_only: bool = False
    hot_line_limit: int = 2
    max_orders: int = Field(200, ge=1, le=2000)


def _rule_dict(r: m.WmsWaveRule) -> dict:
    return {
        "id": r.id,
        "code": r.code,
        "name": r.name,
        "cutoff_at": r.cutoff_at,
        "carrier_code": r.carrier_code,
        "region_prefix": r.region_prefix,
        "hot_only": r.hot_only,
        "hot_line_limit": r.hot_line_limit,
        "max_orders": r.max_orders,
        "status": r.status,
    }


@router.get("/wave-rules", summary="波次规则列表")
async def list_wave_rules(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("wms_outbound:wave:list"))],
):
    rows = (
        await db.execute(select(m.WmsWaveRule).order_by(m.WmsWaveRule.id))
    ).scalars().all()
    return success_response(data=[_rule_dict(r) for r in rows])


@router.post("/wave-rules", summary="新建波次规则")
async def create_wave_rule(
    payload: WaveRuleIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("wms_outbound:wave:create"))],
):
    row = m.WmsWaveRule(**payload.model_dump())
    db.add(row)
    await db.commit()
    return success_response(data={"id": row.id, "code": row.code})


@router.put("/wave-rules/{rule_id}", summary="编辑波次规则")
async def update_wave_rule(
    rule_id: int,
    payload: WaveRuleIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("wms_outbound:wave:create"))],
):
    row = (
        await db.execute(select(m.WmsWaveRule).where(m.WmsWaveRule.id == rule_id))
    ).scalars().first()
    if row is None:
        raise NotFoundException("规则不存在")
    for k, v in payload.model_dump().items():
        setattr(row, k, v)
    await db.commit()
    return success_response(data={"id": row.id})


# ── 波次 ──────────────────────────────────────────────


def _wave_dict(w: m.WmsWave) -> dict:
    progress = (w.processed / w.total * 100) if w.total else 0
    return {
        "id": w.id,
        "code": w.code,
        "rule_id": w.rule_id,
        "status": w.status,
        "total": w.total,
        "processed": w.processed,
        "failed": w.failed,
        "progress": round(progress, 1),
        "fail_detail": w.fail_detail,
        "cancel_reason": w.cancel_reason,
        "started_at": w.started_at.isoformat() if w.started_at else None,
        "finished_at": w.finished_at.isoformat() if w.finished_at else None,
        "created_at": w.created_at.isoformat() if w.created_at else None,
    }


@router.get("/waves", summary="波次列表")
async def list_waves(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("wms_outbound:wave:list"))],
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
):
    cond = []
    if status:
        cond.append(m.WmsWave.status == status)
    base = select(m.WmsWave).where(*cond)
    total = (
        await db.execute(select(func.count()).select_from(base.subquery()))
    ).scalar() or 0
    rows = (
        await db.execute(
            base.order_by(m.WmsWave.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).scalars().all()
    return success_response(
        data={
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": [_wave_dict(w) for w in rows],
        }
    )


@router.get("/waves/{wave_id}", summary="波次进度")
async def get_wave(
    wave_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("wms_outbound:wave:list"))],
):
    w = (
        await db.execute(select(m.WmsWave).where(m.WmsWave.id == wave_id))
    ).scalars().first()
    if w is None:
        raise NotFoundException("波次不存在")
    return success_response(data=_wave_dict(w))


class WaveCreateIn(BaseModel):
    rule_id: Optional[int] = None


@router.post("/waves", summary="生成波次")
async def post_wave(
    payload: WaveCreateIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("wms_outbound:wave:create"))],
):
    """落一条 pending 立刻返回 id。后台任务在 commit 之后才挂起，
    否则它可能读不到刚创建的记录。"""
    try:
        wave = await create_wave(
            db, rule_id=payload.rule_id, operator_id=user.id
        )
    except ValueError as exc:
        raise ValidationException(str(exc)) from exc

    await db.commit()
    await schedule_generation(wave.id)
    return success_response(
        data={"id": wave.id, "code": wave.code, "status": wave.status, "total": wave.total}
    )


class WaveCancelIn(BaseModel):
    reason: Optional[str] = None


@router.post("/waves/{wave_id}/cancel", summary="中止波次")
async def cancel(
    wave_id: int,
    payload: WaveCancelIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("wms_outbound:wave:cancel"))],
):
    try:
        wave = await cancel_wave(
            db, wave_id=wave_id, reason=payload.reason, operator_id=user.id
        )
    except ValueError as exc:
        raise ValidationException(str(exc)) from exc
    await db.commit()
    return success_response(data=_wave_dict(wave))


# ── 播种墙分播 ─────────────────────────────────────────


@router.post("/waves/{wave_id}/cells", summary="生成播种墙格口")
async def post_cells(
    wave_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("wms_outbound:seed:execute"))],
):
    try:
        cells = await init_cells(db, wave_id=wave_id)
    except SeedError as exc:
        raise ValidationException(str(exc)) from exc
    await db.commit()
    return success_response(data={"created": len(cells)})


@router.get("/waves/{wave_id}/cells", summary="格口进度")
async def get_cells(
    wave_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("wms_outbound:seed:list"))],
):
    rows = (
        await db.execute(
            select(m.WmsSortCell)
            .where(m.WmsSortCell.wave_id == wave_id)
            .order_by(m.WmsSortCell.cell_no)
        )
    ).scalars().all()
    return success_response(
        data=[
            {
                "id": r.id,
                "cell_no": r.cell_no,
                "order_id": r.order_id,
                "status": r.status,
                "placed_qty": str(r.placed_qty),
                "required_qty": str(r.required_qty),
            }
            for r in rows
        ]
    )


class SeedScanIn(BaseModel):
    sku_id: int
    cell_no: Optional[str] = None


@router.post("/waves/{wave_id}/seed", summary="扫描分播")
async def post_seed(
    wave_id: int,
    payload: SeedScanIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("wms_outbound:seed:execute"))],
):
    try:
        cell = await scan_to_cell(
            db,
            wave_id=wave_id,
            sku_id=payload.sku_id,
            cell_no=payload.cell_no,
            operator_id=user.id,
        )
    except SeedError as exc:
        raise ValidationException(str(exc)) from exc
    await db.commit()
    return success_response(
        data={
            "cell_no": cell.cell_no,
            "order_id": cell.order_id,
            "placed_qty": str(cell.placed_qty),
            "required_qty": str(cell.required_qty),
            "status": cell.status,
        }
    )
