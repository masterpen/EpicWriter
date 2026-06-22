from typing import TypedDict, Any
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
import asyncio
from app.agents.core import PlannerAgent, WriterAgent, ReviewerAgent
from app.agents.maintainer import MaintainerAgent
from app.agents.fact_checker import FactCheckerAgent
from app.core.database import db
from app.core.logger import logger


# 1. 定义状态
class NovelState(TypedDict):
    chapter_num: int
    user_intent: str
    context_summary: str
    outline: Any
    draft: str
    status_changed: bool
    style: str
    is_batch_mode: bool
    manual_archive: bool
    approved: bool
    book_id: str
    review_count: int
    review_comments: str
    review_score: int
    generate_mode: str  # "scenes" (default) or "direct"

# 初始化 Agent
planner = PlannerAgent()
writer = WriterAgent()
reviewer = ReviewerAgent()
maintainer = MaintainerAgent()
fact_checker = FactCheckerAgent()

async def plan_node(state: NovelState):
    """规划节点（异步）"""
    current_chap = state.get('chapter_num', 1)
    try:
        current_chap = int(current_chap)
    except:
        current_chap = 1

    user_intent = state.get('user_intent', '剧情自然发展')
    book_id = state.get('book_id')

    if state.get("outline") and not state.get("is_batch_mode", False):
        logger.info("🛡️ [Planner] 检测到现有大纲 (手动模式复用)，跳过生成。")
        return {}

    logger.info(f"🎬 [Workflow] Planner 正在规划第 {current_chap} 章...")

    outline_data = await planner.acreate_plan(
        user_intent=user_intent,
        chapter_num=current_chap,
        book_id=book_id
    )

    return {
        "outline": outline_data,
        "review_count": 0,
        "review_comments": ""
    }

async def write_node(state: NovelState):
    """写作节点（异步，支持重写模式 + 分镜并行 / 直出模式）"""
    style = state.get("style", "男频-热血玄幻")
    book_id = state.get('book_id')
    current_chap = state.get('chapter_num', 1)
    feedback = state.get("review_comments", "")
    original_draft = state.get("draft", "") if feedback else ""
    outline = state.get("outline", "本章大纲生成失败，请根据前文和设定自由发挥。")
    generate_mode = state.get("generate_mode", "scenes")

    planned_title = f"第{current_chap}章"
    if isinstance(outline, dict) and outline.get("chapter_title"):
        planned_title = outline["chapter_title"]
    elif isinstance(outline, str):
        try:
            import json
            if "{" in outline:
                parsed = json.loads(outline.split("{")[1].split("}")[0] + "}")
                if parsed.get("chapter_title"):
                    planned_title = parsed["chapter_title"]
        except:
            pass

    if feedback:
        logger.info(f"✍️ [Writer] 第 {state.get('review_count', 0)+1} 次重写中... (针对意见修正)")
    else:
        logger.info(f"✍️ [Writer] 首次撰写正文... (模式: {generate_mode})")

    try:
        if generate_mode == "direct":
            result = await writer.awrite_direct(
                outline=outline,
                chapter_num=current_chap,
                style=style,
                book_id=book_id,
                feedback=feedback,
                planned_title=planned_title,
                original_draft=original_draft,
            )
        else:
            result = await writer.awrite_draft(
                outline=outline,
                chapter_num=current_chap,
                style=style,
                book_id=book_id,
                feedback=feedback,
                planned_title=planned_title,
                original_draft=original_draft,
            )

        if result and isinstance(result, dict):
            return {
                "draft": result.get("draft", ""),
                "status_changed": result.get("status_changed", False)
            }
        elif result:
            return {"draft": str(result), "status_changed": False}
        return {"draft": "", "status_changed": False}

    except Exception as e:
        logger.error(f"❌ Writer 运行致命错误: {e}")
        return {"draft": f"系统生成失败: {str(e)}"}

async def review_node(state: NovelState):
    """审核节点（异步，FactChecker + Reviewer 并行）"""
    current_draft = state.get('draft', "")
    book_id = state.get('book_id')
    chapter_num = state.get('chapter_num', 1)

    # ===== 异步并行：FactChecker + Reviewer =====
    fact_result, review_result = await asyncio.gather(
        fact_checker.acheck_facts(current_draft, book_id, chapter_num),
        reviewer.areview_draft(current_draft, state['outline'], chapter_num, state['style']),
    )

    logger.debug(f"🐛 [Debug] Reviewer 返回内容: {review_result}")
    logger.debug(f"🐛 [Debug] FactChecker 返回内容: {fact_result}")

    if isinstance(review_result, dict):
        score = review_result.get('score', 60)
        comments = review_result.get('suggestions', '无意见')
    else:
        score = 60
        comments = "格式解析失败，建议人工复核。"

    if fact_result and fact_result.get("has_conflict"):
        penalty = fact_result.get("penalty_score", 15)
        score -= penalty
        conflict_desc = " | ".join(fact_result.get("conflicts", []))
        comments = f"【🚨事实逻辑冲突】(扣除{penalty}分): {conflict_desc}\n【编辑意见】: {comments}"
        logger.warning(f"❌ [FactChecker] 发现逻辑漏洞，总分降至 {score}")

    logger.info(f"🧐 [Editor] 最终评分: {score} | 意见: {comments[:50]}...")

    return {
        "review_score": score,
        "review_comments": comments,
        "review_count": state.get("review_count", 0) + 1
    }

async def maintainer_node(state: NovelState):
    """维护者节点（异步）"""
    logger.info("🛠️ [Maintainer] 正在同步本章状态到 Neo4j 数据库...")
    book_id = state.get("book_id")
    draft = state.get("draft", "")

    if book_id and draft:
        current_tags_dict = db.get_all_characters_dict(book_id)
        
        chapter_num = state.get('chapter_num', 1)
        
        # 🟢 检测是否为本卷最后一章（卷收尾标记）
        is_volume_end = False
        next_vol_title = ""
        try:
            bp = db.get_book_plan(book_id)
            if bp and 'volumes' in bp:
                volumes = bp.get('volumes', [])
                acc = 0
                for idx, v in enumerate(volumes):
                    vlen = v.get('estimated_chapters', 50)
                    if chapter_num <= acc + vlen:
                        if chapter_num == acc + vlen and idx + 1 < len(volumes):
                            is_volume_end = True
                            next_vol_title = volumes[idx + 1].get('title', '下一卷')
                        break
                    acc += vlen
        except:
            pass
        
        if is_volume_end:
            logger.info(f"🏁 [Maintainer] 检测到卷收尾章节 (第{chapter_num}章)，将生成卷收尾摘要...")
        
        analysis_result = await maintainer.aanalyze_status_change(
            draft, current_tags_dict, is_volume_end=is_volume_end,
            next_vol_title=next_vol_title, chapter_num=chapter_num
        )

        outline = state.get('outline', {})
        title = f"第{chapter_num}章"
        if isinstance(outline, dict) and outline.get('chapter_title'):
            title = outline['chapter_title']

        db.save_chapter(
            book_id=book_id,
            chapter_num=chapter_num,
            title=title,
            content=draft,
            summary=analysis_result.get("summary", "无摘要")
        )
        
        # 🟢 卷收尾：存储卷收尾上下文供下一卷 Planner 使用
        if is_volume_end and analysis_result.get("volume_conclusion"):
            from app.core.database import db as db2
            conclusion_key = f"volume_conclusion_{chapter_num}"
            db2.set_system_config(conclusion_key, analysis_result["volume_conclusion"])

        char_updates = analysis_result.get("character_updates", {})
        for char_name, updates in char_updates.items():
            mental_state = updates.get("mental_state", "正常")
            tags = updates.get("tags", [])
            db.update_character_state(book_id, char_name, mental_state, tags)

        new_entities = analysis_result.get("new_entities", [])
        for entity in new_entities:
            if entity.get("importance", 1) >= 2:
                db.add_new_entity(book_id, entity)

        logger.success("✅ [Maintainer] 状态同步完成！")

    return {}

# ==========================================
# 3. 构建图
# ==========================================
workflow = StateGraph(NovelState)

workflow.add_node("planner", plan_node)
workflow.add_node("writer", write_node)
workflow.add_node("reviewer", review_node)
workflow.add_node("maintainer", maintainer_node)

workflow.set_entry_point("planner")

# --- 路由逻辑 ---

def route_after_plan(state):
    if state.get("is_batch_mode", False):
        return "writer"
    if state.get("approved", False):
        return "writer"
    return END

def route_after_review(state):
    score = state.get("review_score", 0)
    count = state.get("review_count", 0)
    is_batch = state.get("is_batch_mode", False)
    manual_archive = state.get("manual_archive", True)

    if score >= 75 or count >= 3:
        if count >= 3:
            logger.warning("⚠️ [Router] 重写次数耗尽，强制通过。")
        else:
            logger.success("✅ [Router] 审核通过！")

        if is_batch or not manual_archive:
            return "maintainer"
        else:
            return END
    else:
        logger.info(f"❌ [Router] 质量不达标 ({score}分) -> 打回 Writer 重写")
        return "writer"

# --- 连线 ---
workflow.add_conditional_edges(
    "planner",
    route_after_plan,
    {"writer": "writer", END: END}
)

workflow.add_edge("writer", "reviewer")

workflow.add_conditional_edges(
    "reviewer",
    route_after_review,
    {
        "writer": "writer",
        "maintainer": "maintainer",
        END: END
    }
)

workflow.add_edge("maintainer", END)

# ==========================================
# 4. 编译
# ==========================================
memory = MemorySaver()
app = workflow.compile(checkpointer=memory)
