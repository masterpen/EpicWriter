import json
from app.agents.base import BaseAgent
from app.core.logger import logger
from app.core.prompt_config import get_prompt
from app.core.prompt_renderer import render_prompt
from app.core.json_utils import parse_llm_json


class MultiDraftBuilderAgent(BaseAgent):
    """基于访谈约束生成多套差异化核心设定方案，供用户比较选择。"""

    def __init__(self):
        super().__init__(
            role_prompt="你是网文世界观架构师，擅长基于同一批约束给出多条差异化创作路线。",
            stage_key="multi_draft",
        )

    async def agenerate_variants(self, constraints: dict, style: str = "", n: int = 3) -> list:
        """生成 n 套差异化核心设定方案（A/B/C...）"""
        cfg = get_prompt("multi_draft")
        prompt = render_prompt(cfg.get("template", ""), {
            "constraints": json.dumps(constraints, ensure_ascii=False, indent=2) or "（无约束，请基于通用爽文套路生成）",
            "style": style or "男频-热血玄幻",
            "n": str(n),
        })

        response = await self._acall_with_stage(prompt, stage_override="multi_draft", json_mode=True)
        variants = self._parse_variants(response)
        if not variants:
            raise RuntimeError(
                "多方案生成失败：LLM 未返回有效的方案列表。"
                f"原始返回(前200字): {str(response)[:200]}"
            )
        # 只保留 n 套，规范化 label
        variants = variants[:n]
        labels = ["A", "B", "C", "D", "E"]
        for i, v in enumerate(variants):
            v["label"] = labels[i] if i < len(labels) else labels[-1]
        return variants

    def _parse_variants(self, response) -> list:
        """解析 LLM 返回的方案列表"""
        if isinstance(response, dict):
            parsed = response
        elif isinstance(response, str):
            parsed = parse_llm_json(response, default=None)
        else:
            parsed = None

        if isinstance(parsed, dict) and isinstance(parsed.get("variants"), list):
            return [v for v in parsed["variants"] if isinstance(v, dict)]
        if isinstance(parsed, list):
            return [v for v in parsed if isinstance(v, dict)]
        logger.warning(f"[MultiDraft] 方案解析失败，使用兜底 | 原始: {str(response)[:200]}")
        return self._default_variants()

    def _default_variants(self) -> list:
        """兜底方案（LLM 异常时保证 UI 不崩）"""
        return [
            {
                "label": "A",
                "seed": "主角被家族废掉天赋后，凭借隐藏的金手指重新崛起，逆袭复仇。",
                "core_setting": {
                    "hero_backstory": "昔日天才，天赋被废后遭家族抛弃。",
                    "gold_finger": "隐藏系统，代价是每次使用都暴露自身存在。",
                    "world_rule": "修炼天赋决定阶层地位。",
                    "villain_relation": "废掉主角天赋的幕后黑手正是最终反派。",
                    "vol1_conflict": "被逐出家族后卷入宗门试炼，夺回尊严。",
                },
                "strengths": ["逆袭爽感强", "冲突明确"],
                "risks": ["天赋被废属高频母题，需额外差异点"],
            },
            {
                "label": "B",
                "seed": "主角主动封印自己的力量，隐藏身份行走世间，逐步揭开阴谋。",
                "core_setting": {
                    "hero_backstory": "为保护身边人主动封印力量。",
                    "gold_finger": "封印解除条件绑定主角的道德选择。",
                    "world_rule": "力量越强越容易被更高存在注视。",
                    "villain_relation": "反派是主角旧识，掌握其封印秘密。",
                    "vol1_conflict": "封印松动引发第一次危机。",
                },
                "strengths": ["悬疑感强", "长线空间大"],
                "risks": ["前期压抑，需要爽点补偿"],
            },
            {
                "label": "C",
                "seed": "整个世界以为主角已死，主角隐姓埋名归来，掌握众人不知的情报优势。",
                "core_setting": {
                    "hero_backstory": "假死脱身，以新身份归来。",
                    "gold_finger": "知晓世间无人知晓的秘密（信息差金手指）。",
                    "world_rule": "情报即权力。",
                    "villain_relation": "反派是促成主角'死亡'的推手。",
                    "vol1_conflict": "在暗中布局，逐步揭穿当年的真相。",
                },
                "strengths": ["信息差爽点独特", "反转潜力高"],
                "risks": ["开头复杂，需要引导读者"],
            },
        ]
