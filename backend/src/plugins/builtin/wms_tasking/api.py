"""任务域接口。作业端与后台共用。"""
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.deps import require_permission
from src.core.exceptions import ValidationException, success_response
from src.db import get_db
from src.models import User
from src.plugins.builtin.wms_tasking import models as m
from src.plugins.builtin.wms_tasking.service import (
    TaskError,
    claim_task,
    create_task,
    generate_from_sources,
    recycle_timeout,
    submit_task,
)

router = APIRouter(prefix="/wms-tasking", tags=["任务"])


def _dict(r: m.WmsTask) -> dict:
    return {
        "id": r.id, "code": r.code, "task_type": r.task_type,
        "title": r.title, "ref_type": r.ref_type, "ref_id": r.ref_id,
        "target_location_id": r.target_location_id,
        "status": r.status, "claimed_by": r.claimed_by,
        "claimed_at": r.claimed_at.isoformat() if r.claimed_at else None,
        "submitted_at": r.submitted_at.isoformat() if r.submitted_at else None,
        "note": r.note,
    }


@router.get("/tasks", summary="任务列表")
async def list_tasks(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("wms_tasking:task:list"))],
    status: Optional[str] = Query(None),
    task_type: Optional[str] = Query(None),
    mine: bool = Query(False),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
):
    cond = []
    if status:
        cond.append(m.WmsTask.status == status)
    if task_type:
        cond.append(m.WmsTask.task_type == task_type)
    if mine:
        cond.append(m.WmsTask.claimed_by == user.id)
    base = select(m.WmsTask).where(*cond)
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar() or 0
    rows = (
        await db.execute(base.order_by(m.WmsTask.id.desc())
                         .offset((page - 1) * page_size).limit(page_size))
    ).scalars().all()
    return success_response(data={
        "total": total, "page": page, "page_size": page_size,
        "items": [_dict(r) for r in rows],
    })


@router.post("/tasks/generate", summary="从待办业务生成任务")
async def post_generate(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("wms_tasking:task:create"))],
):
    n = await generate_from_sources(db)
    await db.commit()
    return success_response(data={"created": n})


class TaskCreateIn(BaseModel):
    task_type: str
    ref_type: str
    ref_id: int
    title: str
    target_location_id: Optional[int] = None
    timeout_minutes: int = 60


@router.post("/tasks", summary="新建任务")
async def post_task(
    payload: TaskCreateIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("wms_tasking:task:create"))],
):
    row = await create_task(db, **payload.model_dump())
    await db.commit()
    return success_response(data=_dict(row))


@router.post("/tasks/{task_id}/claim", summary="领取任务")
async def post_claim(
    task_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("wms_tasking:task:claim"))],
):
    try:
        row = await claim_task(db, task_id=task_id, user_id=user.id)
    except TaskError as exc:
        raise ValidationException(str(exc)) from exc
    await db.commit()
    return success_response(data=_dict(row))


class TaskSubmitIn(BaseModel):
    note: Optional[str] = None


@router.post("/tasks/{task_id}/submit", summary="提交任务")
async def post_submit(
    task_id: int,
    payload: TaskSubmitIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("wms_tasking:task:submit"))],
):
    try:
        row = await submit_task(db, task_id=task_id, user_id=user.id, note=payload.note)
    except TaskError as exc:
        raise ValidationException(str(exc)) from exc
    await db.commit()
    return success_response(data=_dict(row))


@router.post("/tasks/recycle", summary="回收超时任务")
async def post_recycle(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("wms_tasking:task:create"))],
):
    n = await recycle_timeout(db)
    await db.commit()
    return success_response(data={"recycled": n})
