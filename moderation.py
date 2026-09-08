"""三层内容审核：L1 违禁词 → L2 GroupGuardian 词库 → L3 AI 审核。"""

from __future__ import annotations

import logging
import os
import sqlite3
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from astrbot.api.star import Context

logger = logging.getLogger(__name__)

# 内置敏感词（触发腾讯风控的基础词）
_BUILTIN_BLOCKED = [
    "加我微信", "加我QQ", "加我好友", "免费领", "点击链接",
    "扫码领取", "兼职赚钱", "日赚", "月入", "加V",
    "约炮", "色情", "裸聊", "成人视频",
]

_DEFAULT_AI_PROMPT = """你是一个内容安全审核员。判断以下 Minecraft 游戏消息是否适合推送到 QQ 群。

判断标准：
- 涉及色情、暴力、政治敏感、人身攻击的内容 → 不安全
- 正常的游戏聊天、交易、打招呼 → 安仅返回一个 JSON：{"safe": true/false}，不要其他内容。

消息内容："""


class ContentModerator:
    """三层内容审核器。"""

    def __init__(self, config: dict, context: Context) -> None:
        self.config = config
        self.context = context
        self._guardian_keywords: list[str] | None = None

    def check(self, message: str) -> tuple[bool, str]:
        """检查消息是否安全。返回 (是否放行, 拦截原因)。"""
        if not self.config.get("qq_content_filter", True):
            return True, ""

        msg_lower = message.lower()

        # L1: 内置敏感词 + 自定义违禁词
        blocked = self.config.get("qq_blocked_words", [])
        all_words = _BUILTIN_BLOCKED + blocked
        for word in all_words:
            if word.lower() in msg_lower:
                return False, f"命中违禁词: {word}"

        # L2: GroupGuardian 词库
        if self.config.get("use_guardian_lexicon", False):
            reason = self._check_guardian_lexicon(message)
            if reason:
                return False, reason

        return True, ""

    async def ai_check(self, message: str) -> tuple[bool, str]:
        """L3: AI 审核。返回 (是否放行, 拦截原因)。"""
        if not self.config.get("enable_ai_moderation", False):
            return True, ""

        prompt = self.config.get("llm_moderation_prompt", "") or _DEFAULT_AI_PROMPT
        full_prompt = f"{prompt}\n\n{message}"

        provider_id = self.config.get("llm_moderation_provider", "") or None

        try:
            from astrbot.api.provider import ProviderRequest
            req = ProviderRequest(
                prompt=full_prompt,
                system_prompt="你是内容安全审核员，只返回 JSON。",
            )
            if provider_id:
                req.provider_id = provider_id
            resp = await self.context.llm_chat(req)
            text = resp.completion_text.strip()

            # 解析 JSON 响应
            if '"safe": false' in text or '"safe":false' in text:
                return False, "AI 判定不安全"
            return True, ""
        except Exception as e:
            logger.warning(f"[MC 审核] AI 审核异常，放行: {e}")
            return True, ""

    def _check_guardian_lexicon(self, message: str) -> str:
        """从 GroupGuardian 的 lexicon.db 查询违禁词。"""
        if self._guardian_keywords is None:
            self._guardian_keywords = self._load_guardian_keywords()

        msg_lower = message.lower()
        for kw in self._guardian_keywords:
            if kw.lower() in msg_lower:
                return f"命中 GroupGuardian 词库: {kw}"
        return ""

    def _load_guardian_keywords(self) -> list[str]:
        """加载 GroupGuardian 的 lexicon.db 关键词。"""
        # 查找 lexicon.db：优先插件目录，其次数据目录
        plugin_dir = Path(__file__).parent.parent
        candidates = [
            plugin_dir.parent / "astrbot_plugin_group_guardian" / "lexicon.db",
            plugin_dir.parent / "astrbot_plugin_group_guardian" / "data" / "lexicon.db",
        ]

        for db_path in candidates:
            if db_path.exists():
                try:
                    conn = sqlite3.connect(str(db_path))
                    cursor = conn.execute("SELECT keyword FROM lexicon_keywords")
                    keywords = [row[0] for row in cursor.fetchall()]
                    conn.close()
                    logger.info(f"[MC 审核] 从 GroupGuardian 加载 {len(keywords)} 条词库")
                    return keywords
                except Exception as e:
                    logger.warning(f"[MC 审核] 加载 GroupGuardian 词库失败: {e}")

        logger.warning("[MC 审核] 未找到 GroupGuardian 的 lexicon.db")
        return []
