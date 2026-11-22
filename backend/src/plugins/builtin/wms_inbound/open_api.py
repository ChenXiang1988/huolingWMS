"""货主开放接口。

与后台接口分开前缀（``/open/v1``）与鉴权（``X-API-Key``）：
后台走 JWT 与权限码，货主系统走密钥与货主范围，两条链路不该混。

同一套业务逻辑在 ``service`` 里，这里只做鉴权注入与出参整形。
"""
from typing import Annotated, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import NotFoundException, ValidationException, success_response
from src.db import get_db
from src.plugins.builtin.wms_inbound import models as m
from src.plugins.builtin.wms_inbound.service import StockError, create_asn
from src.plugins.builtin.wms_master_data.auth import require_api_key

router = APIRouter(prefix="/asns", tags=["开放接口 · 入库"])


class OpenAsnLineIn(BaseModel):
    sku_id: int
    expect_qty: float = Field(..., gt=0)
    remark: Optional[str] = None


class OpenAsnIn(BaseModel):
    owner_doc_no: str = Field(..., max_length=64, description="货主侧单号，用于去重")
    supplier_id: Optional[int] = None
    expect_arrive_at: Optional[str] = None
    remark: Optional[str] = None
    lines: list[OpenAsnLineIn] = Field(..., min_length=1)


@router.post("", summary="推送入库预报")
async def push_asn(
    payload: OpenAsnIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    owner_id: Annotated[int, Depends(require_api_key)],
):
    """货主系统推预报。``owner_id`` 由密钥决定，不读请求体——
    否则一把密钥就能替别的货主建单。
    """
    try:
        asn = await create_asn(
            db,
            owner_id=owner_id,
            owner_doc_no=payload.owner_doc_no,
            lines=[
                {
                    "sku_id": ln.sku_id,
                    "expect_qty": ln.expect_qty,
                    "remark": ln.remark,
                }
                for ln in payload.lines
            ],
            source="api",
            supplier_id=payload.supplier_id,
            remark=payload.remark,
            confirm=True,
        )
    except StockError as exc:
        raise ValidationException(str(exc)) from exc

    await db.commit()
    return success_response(data={"code": asn.code, "status": asn.status})


@router.get("/{code}", summary="按预报号查询")
async def get_asn(
    code: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    owner_id: Annotated[int, Depends(require_api_key)],
):
    asn = (
        await db.execute(
            select(m.WmsAsn).where(
                m.WmsAsn.code == code, m.WmsAsn.owner_id == owner_id
            )
        )
    ).scalars().first()
    if asn is None:
        # 别的货主的单号也走这条分支，不区分"不存在"与"不属于你"
        raise NotFoundException("预报不存在")

    lines = (
        await db.execute(select(m.WmsAsnLine).where(m.WmsAsnLine.asn_id == asn.id))
    ).scalars().all()

    return success_response(
        data={
            "code": asn.code,
            "owner_doc_no": asn.owner_doc_no,
            "status": asn.status,
            "lines": [
                {
                    "sku_id": ln.sku_id,
                    "expect_qty": str(ln.expect_qty),
                }
                for ln in lines
            ],
        }
    )
