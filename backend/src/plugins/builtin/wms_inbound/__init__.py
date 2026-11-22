"""入库插件包。

插件管理器 import 本包后，在命名空间里查找 ``PluginInterface`` 的子类，
因此这里必须把插件类导出到模块顶层。
"""
from src.plugins.builtin.wms_inbound.plugin import WmsInboundPlugin

__all__ = ["WmsInboundPlugin"]
