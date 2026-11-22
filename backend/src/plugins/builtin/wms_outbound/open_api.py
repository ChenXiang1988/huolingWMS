"""出库开放接口。货主系统推单与查进度。

与入库同一个鉴权：``X-API-Key``，``owner_id`` 由密钥决定，不读请求体。
"""
from decimal import Decimal
from typing import Annotated, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import NotFoundException, ValidationException, success_response
from src.db import get_db
from src.plugins.builtin.wms_master_data.auth import require_api_key
from src.plugins.builtin.wms_outbound import models as m
from src.plugins.builtin.wms_outbound.service import OutboundError, create_order

router = APIRouter(prefix="/orders", tags=["开放接口 · 出库"])


class OpenOrderLineIn(BaseModel):
    sku_id: int
    qty: Decimal = Field(..., gt=0)
    lot_id: Optional[int] = None


class OpenOrderIn(BaseModel):
    owner_doc_no: str = Field(..., max_length=64, description="货主侧单号，用于去重")
    order_type: str = Field("C", pattern="^(B|C)$")
    receiver: Optional[str] = None
    receiver_phone: Optional[str] = None
    receiver_address: Optional[str] = None
    carrier_code: Optional[str] = None
    lines: list[OpenOrderLineIn] = Field(..., min_length=1)


@router.post("", summary="推送出库订单")
async def push_order(
    payload: OpenOrderIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    owner_id: Annotated[int, Depends(require_api_key)],
):
    try:
        order = await create_order(
            db,
            owner_id=owner_id,
            owner_doc_no=payload.owner_doc_no,
            lines=[ln.model_dump() for ln in payload.lines],
            order_type=payload.order_type,
            source="api",
            receiver=payload.receiver,
            receiver_phone=payload.receiver_phone,
            receiver_address=payload.receiver_address,
            carrier_code=payload.carrier_code,
        )
    except OutboundError as exc:
        raise ValidationException(str(exc)) from exc

    await db.commit()
    return success_response(data={"code": order.code, "status": order.status})


@router.get("/{code}", summary="按订单号查询")
async def get_order(
    code: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    owner_id: Annotated[int, Depends(require_api_key)],
):
    order = (
        await db.execute(
            select(m.WmsOrder).where(
                m.WmsOrder.code == code, m.WmsOrder.owner_id == owner_id
            )
        )
    ).scalars().first()
    if order is None:
        raise NotFoundException("订单不存在")

    lines = (
        await db.execute(
            select(m.WmsOrderLine).where(m.WmsOrderLine.order_id == order.id)
        )
    ).scalars().all()

    shipment = (
        await db.execute(
            select(m.WmsShipment).where(m.WmsShipment.order_id == order.id)
        )
    ).scalars().first()

    return success_response(
        data={
            "code": order.code,
            "owner_doc_no": order.owner_doc_no,
            "status": order.status,
            "tracking_no": shipment.tracking_no if shipment else None,
            "lines": [
                {
                    "sku_id": ln.sku_id,
                    "qty": str(ln.qty),
                    "allocated_qty": str(ln.allocated_qty),
                }
                for ln in lines
            ],
        }
    )
