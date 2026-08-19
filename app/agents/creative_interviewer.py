import json
from app.agents.base import BaseAgent
from app.core.database import db
from app.core.logger import logger
from app.core.prompt_config import get_prompt
from app.core.prompt_renderer import render_prompt
from app.core.json_utils import parse_llm_json

# 访谈主题清单（按优先级）。权重用于计算覆盖度。
INTERVIEW_TOPICS = [
    {"key": "core_pleasure", "label": "核心爽点", "weight": 0.15},
    {"key": "hero_situation", "label": "主角开局", "weight": 0.15},
    {"key": "gold_finger", "label": "金手指本质", "weight": 0.15},
    {"key": "gold_finger_cost", "label": "金手指代价", "weight": 0.10},
    {"key": "world_rule", "label": "世界规则", "weight": 0.15},
    {"key": "villain_bond", "label": "反派羁绊", "weight": 0.10},
    {"key": "vol1_conflict", "label": "第一卷冲突", "weight": 0.10},
    {"key": "long_term", "label": "长篇空间", "weight": 0.10},
]


class CreativeInterviewerAgent(BaseAgent):
    """把用户模糊创意逐步提炼为结构化创作约束。不写小说，只问问题、给选项、收答案。"""

    def __init__(self):
        super().__init__(
            role_prompt="你是网文创作导师，负责把用户的模糊创意提炼成结构化创作约束。",
            stage_key="interview",
        )

    # ------------------------------------------------------------------
    # 状态读取辅助
    # ------------------------------------------------------------------
    @staticmethod
    def _answered_topics(session_data: dict) -> set:
        """返回已作答的主题 key 集合"""
        constraints = session_data.get("collected_constraints", {}) or {}
        return {k for k, v in constraints.items() if v}

    @staticmethod
    def _next_topic(session_data: dict):
        """按优先级返回下一个未作答主题，全部答完返回 None"""
        answered = CreativeInterviewerAgent._answered_topics(session_data)
        for t in INTERVIEW_TOPICS:
            if t["key"] not in answered:
                return t
        return None

    @staticmethod
    def _coverage(session_data: dict) -> float:
        """计算已收集约束的覆盖度（0~1）"""
        answered = CreativeInterviewerAgent._answered_topics(session_data)
        total = sum(t["weight"] for t in INTERVIEW_TOPICS)
        got = sum(t["weight"] for t in INTERVIEW_TOPICS if t["key"] in answered)
        return round(got / total, 2) if total else 0.0

    # ------------------------------------------------------------------
    # 核心流程
    # ------------------------------------------------------------------
    async def astart_session(self, raw_idea: str, style: str = "") -> dict:
        """创建会话并生成第一个问题"""
        import uuid
        session_id = f"ivw_{uuid.uuid4().hex[:12]}"
        db.create_interview_session(
            session_id=session_id,
            user_id="",
            raw_idea=raw_idea,
            style=style or "男频-热血玄幻",
        )
        question = await self._generate_question(session_id, raw_idea, style or "男频-热血玄幻")
        return {
            "session_id": session_id,
            "question": question,
            "progress": 0.0,
        }

    async def anext_question(self, session_id: str, question_id: str,
                             option_value: str = "", free_input: str = "") -> dict:
        """处理用户回答，返回下一个问题（答完返回 question=None）"""
        session_data = db.get_interview_session(session_id)
        if not session_data:
            raise ValueError(f"访谈会话不存在: {session_id}")
        if session_data.get("status") == "completed":
            return {"question": None, "progress": 1.0, "completed": True}

        raw_idea = session_data.get("raw_idea", "")
        style = session_data.get("style", "")

        # 记录回答
        constraints = session_data.get("collected_constraints", {}) or {}
        history = session_data.get("question_history", []) or []
        answer_text = free_input.strip() if free_input.strip() else option_value.strip()
        if answer_text:
            topic_key = self._resolve_topic_key(question_id, session_data)
            constraints[topic_key] = answer_text
            history.append({
                "question_id": question_id,
                "topic": self._topic_label(topic_key),
                "answer": answer_text,
            })
        db.update_interview_session(
            session_id,
            collected_constraints=constraints,
            question_history=history,
        )

        # 判断是否还有下一题
        next_topic = self._next_topic(
            {"collected_constraints": constraints}
        )
        if next_topic is None:
            db.update_interview_session(session_id, status="completed", current_topic="")
            return {"question": None, "progress": 1.0, "completed": True}

        question = await self._generate_question(
            session_id, raw_idea, style,
            constraints=constraints, history=history, topic=next_topic,
        )
        return {
            "question": question,
            "progress": self._coverage({"collected_constraints": constraints}),
            "completed": False,
        }

    async def askip(self, session_id: str) -> dict:
        """跳过当前题，返回下一题"""
        session_data = db.get_interview_session(session_id)
        if not session_data:
            raise ValueError(f"访谈会话不存在: {session_id}")

        constraints = session_data.get("collected_constraints", {}) or {}
        next_topic = self._next_topic({"collected_constraints": constraints})
        if next_topic is None:
            db.update_interview_session(session_id, status="completed", current_topic="")
            return {"question": None, "progress": 1.0, "completed": True}

        question = await self._generate_question(
            session_id, session_data.get("raw_idea", ""), session_data.get("style", ""),
            constraints=constraints,
            history=session_data.get("question_history", []) or [],
            topic=next_topic,
        )
        return {
            "question": question,
            "progress": self._coverage({"collected_constraints": constraints}),
            "completed": False,
        }

    async def abuild_constraints(self, session_id: str) -> dict:
        """访谈结束（或提前结束）时返回结构化约束"""
        session_data = db.get_interview_session(session_id)
        if not session_data:
            raise ValueError(f"访谈会话不存在: {session_id}")
        db.update_interview_session(session_id, status="completed")
        return {
            "session_id": session_id,
            "constraints": session_data.get("collected_constraints", {}) or {},
            "raw_idea": session_data.get("raw_idea", ""),
            "style": session_data.get("style", ""),
            "coverage": self._coverage(session_data),
        }

    @staticmethod
    def _topic_label(topic_key: str) -> str:
        """根据 key 返回主题显示名"""
        for t in INTERVIEW_TOPICS:
            if t["key"] == topic_key:
                return t["label"]
        return topic_key

    @staticmethod
    def _resolve_topic_key(question_id: str, session_data: dict) -> str:
        """精确解析问题对应的主题 key（避免 startswith 前缀误匹配，如 gold_finger vs gold_finger_cost）"""
        # question_id 格式: {topic_key}_q
        if question_id.endswith("_q"):
            candidate = question_id[:-2]
            for t in INTERVIEW_TOPICS:
                if t["key"] == candidate:
                    return candidate
        # 兜底：取 current_topic 中记录的 key
        current = session_data.get("current_topic", "")
        for t in INTERVIEW_TOPICS:
            if t["key"] in current:
                return t["key"]
        # 最终兜底：截取 question_id 前缀
        return question_id.split("_q")[0] or question_id

    # ------------------------------------------------------------------
    # LLM 生成问题
    # ------------------------------------------------------------------
    async def _generate_question(self, session_id: str, raw_idea: str, style: str,
                                 constraints: dict = None, history: list = None,
                                 topic: dict = None) -> dict:
        """生成一道访谈问题（选择题 + 1 个自由输入）"""
        cfg = get_prompt("interview")
        constraints = constraints or {}
        history = history or []
        topic = topic or INTERVIEW_TOPICS[0]

        # 已作答主题黑名单，防止 LLM 重复提问覆盖已收集约束
        answered = self._answered_topics({"collected_constraints": constraints})
        answered_labels = [self._topic_label(k) for k in answered if self._topic_label(k) != k]

        prompt = render_prompt(cfg.get("template", ""), {
            "raw_idea": raw_idea,
            "style": style,
            "collected_constraints": json.dumps(constraints, ensure_ascii=False, indent=2) or "（暂无）",
            "question_history": json.dumps(history, ensure_ascii=False, indent=2) or "（暂无）",
            "current_topic": f"{topic['label']} ({topic['key']})",
            "answered_topics": "、".join(answered_labels) or "（无，全部主题均未作答）",
        })

        response = await self._acall_with_stage(prompt, stage_override="interview", json_mode=True)
        parsed = self._parse_question(response)

        # 强制附加自由输入选项
        parsed.setdefault("options", [])
        parsed["options"].append({
            "label": "我自己描述",
            "value": "__free_input__",
            "implication": "由用户自由填写，AI 将结合该描述继续访谈",
            "potential_score": None,
        })
        parsed["topic"] = topic["key"]
        parsed["question_id"] = f"{topic['key']}_q"
        return parsed

    def _parse_question(self, response) -> dict:
        """解析 LLM 返回的问题 JSON，失败时返回兜底问题"""
        if isinstance(response, dict):
            parsed = response
        elif isinstance(response, str):
            parsed = parse_llm_json(response, default=None)
        else:
            parsed = None

        if not isinstance(parsed, dict) or "question" not in parsed:
            logger.warning(f"[Interview] 问题解析失败，使用兜底问题 | 原始: {str(response)[:200]}")
            return {
                "question": "你希望这个故事的哪个方面继续细化？",
                "rationale": "默认追问",
                "options": [
                    {"label": "A. 主角能力", "value": "ability", "implication": "明确主角的能力来源与限制", "potential_score": 4},
                    {"label": "B. 世界背景", "value": "world", "implication": "明确世界的规则与势力分布", "potential_score": 4},
                    {"label": "C. 反派设定", "value": "villain", "implication": "明确反派与主角的关系", "potential_score": 4},
                ],
            }
        if "options" not in parsed or not parsed["options"]:
            parsed["options"] = [
                {"label": "A. 继续细化", "value": "refine", "implication": "保持当前方向", "potential_score": 3},
                {"label": "B. 换个角度", "value": "pivot", "implication": "调整创作方向", "potential_score": 3},
            ]
        return parsed
