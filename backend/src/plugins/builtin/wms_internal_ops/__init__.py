"""库内作业插件包。P4 只承载补货，P5 扩移库、盘点、留样台账。"""
from src.plugins.builtin.wms_internal_ops.plugin import WmsInternalOpsPlugin

__all__ = ["WmsInternalOpsPlugin"]
