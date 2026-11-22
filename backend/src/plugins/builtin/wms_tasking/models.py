"""任务域。任务只管调度与领取，不改业务单据状态。"""
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from src.db import Base
from src.models.mixins import IDMixin, TimestampMixin

TASK_PENDING = "pending"
TASK_CLAIMED = "claimed"
TASK_DONE = "done"
TASK_CANCELLED = "cancelled"


class WmsTask(IDMixin, TimestampMixin, Base):
    __tablename__ = "wms_tasking_task"
    __table_args__ = (Index("ix_task_status_type", "status", "task_type"),)

    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    task_type: Mapped[str] = mapped_column(
        String(24), nullable=False, comment="transfer / count / putaway / pick / check"
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    ref_type: Mapped[str] = mapped_column(String(32), nullable=False)
    ref_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    target_location_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default=TASK_PENDING, nullable=False)
    claimed_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    claimed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    timeout_minutes: Mapped[int] = mapped_column(Integer, default=60, nullable=False)
    note: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
