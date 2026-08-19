"""
读者认知状态 (Reader State)

现有系统维护的是"世界状态一致性"（角色/实体/力量等级），
本模块维护的是"读者认知状态一致性"——读者知道什么、怀疑什么、
期待什么、被欠了什么。它是 Suspense Engine 的核心数据源。

状态结构：
- known_facts:      读者已确知的事实
- suspected_facts:  读者怀疑但未证实的线索
- mysteries:        未解之谜 [{question, introduced, weight}]
- emotional_debts:  情绪债务 [{debt, introduced, urgency}] —— 欠读者的爽点/清算
- anticipation:     当前读者最期待看到的事
- info_gap:         信息差 {reader_over_hero, reader_over_villain}
- last_hook:        上一章结尾钩子
- attention:        读者注意力水平 0-100（由 ReaderSimulator 反馈）

持久化：复用 db.set_system_config / get_system_config（Neo4j KV 存储），
key 为 reader_state_{book_id}，与 volume_conclusion_{n} 同一机制。
"""
import json
from typing import Any, Dict, List

from app.core.logger import logger

_STATE_KEY_PREFIX = "reader_state_"


def _get_db():
    """惰性导入 db 单例，避免模块导入时就触发 Neo4j 连接（便于测试与工具复用）"""
    from app.core.database import db
    return db

# 情绪债务/谜团的"催债"阈值：欠了超过 N 章就在 prompt 中加重提醒
_DEBT_AGE_WARN = 8
_MYSTERY_AGE_WARN = 15


def default_reader_state() -> Dict[str, Any]:
    """新书/无历史时的空读者状态"""
    return {
        "known_facts": [],
        "suspected_facts": [],
        "mysteries": [],
        "emotional_debts": [],
        "anticipation": "",
        "info_gap": {"reader_over_hero": "", "reader_over_villain": ""},
        "last_hook": "",
        "attention": 60,
    }


def get_reader_state(book_id: str) -> Dict[str, Any]:
    """读取读者状态，缺失或损坏时回退默认状态"""
    state = default_reader_state()
    if not book_id:
        return state
    try:
        raw = _get_db().get_system_config(f"{_STATE_KEY_PREFIX}{book_id}")
        if raw:
            data = json.loads(raw)
            if isinstance(data, dict):
                for key in state:
                    if key in data:
                        state[key] = data[key]
    except Exception as e:
        logger.warning(f"[ReaderState] 读取失败 (book={book_id})，使用默认状态: {e}")
    return state


def save_reader_state(book_id: str, state: Dict[str, Any]) -> None:
    """持久化读者状态"""
    if not book_id:
        return
    try:
        _get_db().set_system_config(f"{_STATE_KEY_PREFIX}{book_id}", json.dumps(state, ensure_ascii=False))
    except Exception as e:
        logger.error(f"[ReaderState] 保存失败 (book={book_id}): {e}")


def render_for_planner(state: Dict[str, Any], chapter_num: int) -> str:
    """渲染给 Planner 的读者状态指令块。

    设计意图：让 Planner 从"节拍生成器"变成"悬念引擎"——
    本章规划必须回答"读者读完后知道了什么、还想知道什么"。
    """
    lines: List[str] = ["【🧲 读者认知状态 (Reader State) —— 本章必须服务于读者的“想知道”】"]

    mysteries = state.get("mysteries") or []
    if mysteries:
        lines.append("① 未解之谜（读者正在等的答案，选择推进或加固，禁止无故遗忘）：")
        for m in mysteries[:6]:
            age = chapter_num - int(m.get("introduced", chapter_num))
            warn = " ⚠️ 欠太久，本章建议推进" if age >= _MYSTERY_AGE_WARN else ""
            lines.append(f"   - [{m.get('weight', 3)}星/已欠{age}章] {m.get('question', '')}{warn}")
    else:
        lines.append("① 未解之谜：暂无（本章应至少新埋 1 个钩子，长篇小说不能没有未回答问题）")

    debts = state.get("emotional_debts") or []
    if debts:
        lines.append("② 情绪债务（欠读者的爽点/清算，管理偿还节奏，禁止一次性还清）：")
        for d in debts[:6]:
            age = chapter_num - int(d.get("introduced", chapter_num))
            warn = " 🔥 已积压，强烈建议本章或下章兑现" if age >= _DEBT_AGE_WARN else ""
            lines.append(f"   - [紧迫度{d.get('urgency', 3)}/已欠{age}章] {d.get('debt', '')}{warn}")
    else:
        lines.append("② 情绪债务：暂无（可在本章制造新的期待，如羞辱未报/承诺未兑现）")

    anticipation = state.get("anticipation")
    if anticipation:
        lines.append(f"③ 读者当前最期待：{anticipation}（可以推进，但最好以“部分满足+新期待”的方式）")

    info_gap = state.get("info_gap") or {}
    over_hero = info_gap.get("reader_over_hero")
    over_villain = info_gap.get("reader_over_villain")
    if over_hero or over_villain:
        lines.append("④ 信息差约束（戏剧张力的来源，必须维护）：")
        if over_hero:
            lines.append(f"   - 读者知道而主角不知道：{over_hero}")
            lines.append("     ⚠️ 严禁让主角无理由知晓该信息；可利用此信息差制造“读者干着急”的张力。")
        if over_villain:
            lines.append(f"   - 读者知道而反派不知道：{over_villain}")

    last_hook = state.get("last_hook")
    if last_hook:
        lines.append(f"⑤ 上一章结尾钩子：{last_hook}")
        lines.append("   ⚠️ 本章必须回应或升级该钩子，严禁丢钩（读者是被钩子带进本章的）。")

    lines.append(
        "⑥ 本章规划硬性要求（Suspense Engine）：\n"
        "   - character_goal：主角本章必须有具体欲望目标，不是“随便逛逛”。\n"
        "   - dilemma/choice_cost：设置一个必须付出代价的选择；没有代价的胜利不吸引人。\n"
        "   - information_reveal：明确本章向读者/主角揭示什么信息、仍隐藏什么。\n"
        "   - irreversible_change：本章结束必须有不可逆改变，拒绝“一切照旧”的过渡章。\n"
        "   - chapter_hook：章末钩子 = 新信息 + 风险/悬念 + 下一步行动方向，\n"
        "     禁止“一个神秘黑影出现”式空钩子。"
    )
    return "\n".join(lines)


def render_for_reader_sim(state: Dict[str, Any]) -> str:
    """渲染给 ReaderSimulator 的读者画像上下文"""
    mysteries = "；".join(m.get("question", "") for m in (state.get("mysteries") or [])[:8]) or "无"
    debts = "；".join(d.get("debt", "") for d in (state.get("emotional_debts") or [])[:8]) or "无"
    info_gap = state.get("info_gap") or {}
    return (
        f"你此前追读到本章之前。你的阅读记忆：\n"
        f"- 你正在等的答案：{mysteries}\n"
        f"- 你期待兑现的爽点：{debts}\n"
        f"- 你当前最期待：{state.get('anticipation') or '尚未形成明确期待'}\n"
        f"- 你知道而主角不知道：{info_gap.get('reader_over_hero') or '无'}\n"
        f"- 上章结尾钩子：{state.get('last_hook') or '无'}\n"
        f"- 你当前的注意力水平：{state.get('attention', 60)}/100"
    )


def apply_reader_updates(
    state: Dict[str, Any],
    updates: Dict[str, Any],
    chapter_num: int,
) -> Dict[str, Any]:
    """将 ReaderSimulator 的增量合并进读者状态（归档时调用）。

    updates 约定字段（全部可选、容错处理）：
    - new_questions: List[str]        → 新增谜团
    - resolved_questions: List[str]   → 从谜团中按文本包含匹配移除
    - new_debts: List[str|dict]       → 新增情绪债务
    - paid_debts: List[str]           → 按文本包含匹配移除债务
    - new_known_facts: List[str]      → 追加已知事实
    - new_suspected_facts: List[str]  → 追加怀疑线索
    - anticipation: str               → 覆盖
    - info_gap: dict                  → 覆盖对应子键
    - last_hook: str                  → 覆盖
    - attention: int                  → 覆盖 (clamp 0-100)
    """
    if not isinstance(updates, dict):
        return state

    def _as_str_list(val) -> List[str]:
        if not isinstance(val, list):
            return []
        out = []
        for item in val:
            if isinstance(item, str) and item.strip():
                out.append(item.strip())
            elif isinstance(item, dict):
                # 容错：模型可能返回 {"question": "..."} / {"debt": "..."}
                text = item.get("question") or item.get("debt") or item.get("fact") or ""
                if isinstance(text, str) and text.strip():
                    out.append(text.strip())
        return out

    def _match(container_text: str, needle: str) -> bool:
        """宽松的包含匹配（双向），用于消谜/还债"""
        if not container_text or not needle:
            return False
        return needle in container_text or container_text in needle

    # 1. 谜团：先移除已解决的，再新增
    mysteries = state.get("mysteries") or []
    for resolved in _as_str_list(updates.get("resolved_questions")):
        mysteries = [m for m in mysteries if not _match(m.get("question", ""), resolved)]
    existing_qs = [m.get("question", "") for m in mysteries]
    for q in _as_str_list(updates.get("new_questions")):
        if not any(_match(eq, q) for eq in existing_qs):
            mysteries.append({"question": q, "introduced": chapter_num, "weight": 3})
    state["mysteries"] = mysteries[-12:]  # 上限防膨胀

    # 2. 情绪债务：先核销已兑现的，再新增
    debts = state.get("emotional_debts") or []
    for paid in _as_str_list(updates.get("paid_debts")):
        debts = [d for d in debts if not _match(d.get("debt", ""), paid)]
    existing_debts = [d.get("debt", "") for d in debts]
    for item in updates.get("new_debts") or []:
        if isinstance(item, str) and item.strip():
            debt_text, urgency = item.strip(), 3
        elif isinstance(item, dict):
            debt_text = str(item.get("debt", "")).strip()
            urgency = item.get("urgency", 3)
        else:
            continue
        if not debt_text:
            continue
        try:
            urgency = max(1, min(5, int(urgency)))
        except (TypeError, ValueError):
            urgency = 3
        if not any(_match(ed, debt_text) for ed in existing_debts):
            debts.append({"debt": debt_text, "introduced": chapter_num, "urgency": urgency})
    state["emotional_debts"] = debts[-12:]

    # 3. 事实与怀疑（精确匹配去重追加；模糊匹配仅用于谜团/债务的消账，
    #    事实文本若用模糊匹配会误杀前缀相同的条目，如 "事实1" 吞掉 "事实10"）
    for key, upd_key in (("known_facts", "new_known_facts"), ("suspected_facts", "new_suspected_facts")):
        facts = state.get(key) or []
        existing = set(facts)
        for f in _as_str_list(updates.get(upd_key)):
            if f not in existing:
                facts.append(f)
                existing.add(f)
        state[key] = facts[-20:]

    # 4. 标量字段
    if isinstance(updates.get("anticipation"), str) and updates["anticipation"].strip():
        state["anticipation"] = updates["anticipation"].strip()
    if isinstance(updates.get("last_hook"), str) and updates["last_hook"].strip():
        state["last_hook"] = updates["last_hook"].strip()

    if isinstance(updates.get("info_gap"), dict):
        gap = state.get("info_gap") or {"reader_over_hero": "", "reader_over_villain": ""}
        for sub in ("reader_over_hero", "reader_over_villain"):
            val = updates["info_gap"].get(sub)
            if isinstance(val, str) and val.strip():
                gap[sub] = val.strip()
        state["info_gap"] = gap

    attention = updates.get("attention")
    if attention is not None:
        try:
            state["attention"] = max(0, min(100, int(attention)))
        except (TypeError, ValueError):
            pass

    return state
