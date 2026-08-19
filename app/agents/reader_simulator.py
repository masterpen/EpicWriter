"""
读者模拟器 (Reader Simulator)

在 Reviewer 之后运行：不再问"这章写得对不对"，而是问
"一个真实的网文读者读完这章，会不会点下一章"。

同时产出 ReaderState 的增量更新（新谜团/新债务/信息差变化/钩子记录），
由归档节点落库，供下一章的 Planner 使用。
"""
import asyncio
import json

from app.agents.base import BaseAgent
from app.core.json_utils import parse_llm_json
from app.core.logger import logger
from app.core.prompt_config import get_prompt
from app.core.prompt_renderer import render_prompt
from app.core.reader_state import render_for_reader_sim


class ReaderSimulatorAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            "你是一个网文老读者（老书虫），追过上百本长篇网文，口味挑剔，"
            "弃书果断。你的唯一任务是诚实地回答：读完这一章，你会不会点下一章？",
            stage_key="reader_sim",
        )

    async def asimulate(self, draft: str, reader_state: dict, chapter_num: int) -> dict:
        """模拟读者反应。

        Returns:
            {
                "will_continue": 1-10,
                "continue_reason": str,
                "drop_risk_points": [str],
                "hook_quality": 1-10,
                "attention": 0-100,
                "feedback_for_writer": str,   # 可读性不达标时的修改意见
                # —— 以下为 ReaderState 增量 ——
                "new_questions": [...], "resolved_questions": [...],
                "new_debts": [...], "paid_debts": [...],
                "new_known_facts": [...], "new_suspected_facts": [...],
                "anticipation": str, "info_gap": {...}, "last_hook": str,
            }
        """
        reader_profile = render_for_reader_sim(reader_state)

        cfg = get_prompt("reader_sim")
        prompt = render_prompt(cfg.get("template", ""), {
            "chapter_num": str(chapter_num),
            "reader_profile": reader_profile,
            "draft": str(draft)[:4000],
        })

        response = await self.acall(prompt, json_mode=True)

        default = {
            "will_continue": 6,
            "continue_reason": "解析失败，默认中性",
            "drop_risk_points": [],
            "hook_quality": 5,
            "attention": reader_state.get("attention", 60),
            "feedback_for_writer": "",
        }
        result = parse_llm_json(response, default=None)
        if not isinstance(result, dict):
            logger.warning(f"[ReaderSim] JSON 解析失败，使用默认值 (chap={chapter_num})")
            return default

        # 数值字段钳制
        for key, lo, hi in (("will_continue", 1, 10), ("hook_quality", 1, 10), ("attention", 0, 100)):
            try:
                result[key] = max(lo, min(hi, int(result.get(key, default[key]))))
            except (TypeError, ValueError):
                result[key] = default[key]

        return result
