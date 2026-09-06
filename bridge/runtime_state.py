"""runtime_state.py：运行时状态模块，存活于插件热重载。

通过将关键状态存储在 sys.modules 中的合成模块里，
确保插件重载时 BridgeManager 等实例不会丢失。
"""

from __future__ import annotations

import sys
import types
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from . import BridgeManager

_MODULE_NAME = "_astrbot_minecraft_bridge_runtime"


def _get_runtime_module() -> types.ModuleType:
    """获取或创建运行时状态模块。"""
    mod = sys.modules.get(_MODULE_NAME)
    if mod is None:
        mod = types.ModuleType(_MODULE_NAME)
        mod.__doc__ = "Minecraft Bridge 运行时状态（热重载存活）"
        mod.bridge_manager = None
        mod.adapter_instances = {}
        sys.modules[_MODULE_NAME] = mod
    return mod


def get_bridge_manager():
    """获取运行时 BridgeManager（可能为 None）。"""
    return _get_runtime_module().bridge_manager


def set_bridge_manager(manager: "BridgeManager") -> None:
    """存储 BridgeManager 到运行时模块。"""
    _get_runtime_module().bridge_manager = manager


def get_adapter_instance(adapter_id: str):
    """获取已注册的适配器实例（热重载后仍可访问）。"""
    return _get_runtime_module().adapter_instances.get(adapter_id)


def set_adapter_instance(adapter_id: str, instance) -> None:
    """存储适配器实例。"""
    _get_runtime_module().adapter_instances[adapter_id] = instance


def remove_adapter_instance(adapter_id: str) -> None:
    """移除适配器实例。"""
    _get_runtime_module().adapter_instances.pop(adapter_id, None)
