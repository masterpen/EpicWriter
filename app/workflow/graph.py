from typing import TypedDict, Any
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
import asyncio
from app.agents.core import PlannerAgent, WriterAgent
from app.agents.reviewer import UnifiedReviewerAgent
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
    review_result: dict  # 完整审核结果（包含 maintainer 数据）

# 初始化 Agent
planner = PlannerAgent()
writer = WriterAgent()
unified_reviewer = UnifiedReviewerAgent()


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


async def unified_review_node(state: NovelState):
    """
    合并审核节点：Reviewer + FactChecker + Maintainer
    原本 3 次 LLM 调用 → 1 次调用
    """
    book_id = state.get('book_id')
    current_draft = state.get('draft', "")
    chapter_num = state.get('chapter_num', 1)
    style = state.get('style', "男频-热血玄幻")
    outline = state.get('outline', {})

    if not book_id or not current_draft:
        logger.warning("⚠️ [UnifiedReviewer] 缺少必要数据，跳过审核")
        return {"review_score": 70, "review_comments": "数据不足，默认通过", "review_count": 1}

    # 获取已知角色列表（用于 Maintainer 任务）
    current_tags_dict = await asyncio.to_thread(db.get_all_characters_dict, book_id)

    # 检测是否为卷末
    is_volume_end = False
    next_vol_title = ""
    try:
        bp = await asyncio.to_thread(db.get_book_plan, book_id)
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
        logger.info(f"🏁 [UnifiedReviewer] 检测到卷收尾章节 (第{chapter_num}章)")

    # ===== 一次 LLM 调用完成所有审核任务 =====
    logger.info(f"🧐 [UnifiedReviewer] 正在审核第 {chapter_num} 章...")

    review_result = await unified_reviewer.review_and_analyze(
        draft=current_draft,
        outline=outline,
        chapter_num=chapter_num,
        style=style,
        book_id=book_id,
        current_tags_dict=current_tags_dict,
        is_volume_end=is_volume_end,
        next_vol_title=next_vol_title
    )

    # 提取结果
    final_score = review_result.get("final_score", 70)
    review_data = review_result.get("review", {})
    comments = review_data.get("suggestions", review_data.get("comments", "无意见"))

    logger.info(f"🧐 [UnifiedReviewer] 最终评分: {final_score} | 意见: {comments[:50]}...")

    return {
        "review_score": final_score,
        "review_comments": comments,
        "review_count": state.get("review_count", 0) + 1,
        "review_result": review_result  # 保存完整结果，供后续 maintainer 使用
    }


async def archive_node(state: NovelState):
    """
    归档节点：将审核通过的章节保存到数据库
    （从原 maintainer_node 拆出，只负责归档）
    """
    book_id = state.get("book_id")
    draft = state.get("draft", "")
    chapter_num = state.get('chapter_num', 1)
    review_result = state.get("review_result", {})

    if not book_id or not draft:
        return {}

    logger.info("🛠️ [Archive] 正在归档本章到数据库...")

    # 从 review_result 中提取 maintainer 数据
    maintainer_data = review_result.get("maintainer", {})
    outline = state.get('outline', {})
    title = f"第{chapter_num}章"
    if isinstance(outline, dict) and outline.get('chapter_title'):
        title = outline['chapter_title']

    # 保存章节
    await asyncio.to_thread(
        db.save_chapter,
        book_id=book_id,
        chapter_num=chapter_num,
        title=title,
        content=draft,
        summary=maintainer_data.get("summary", "无摘要")
    )

    # 卷收尾：存储卷收尾上下文
    is_volume_end = maintainer_data.get("volume_conclusion") is not None
    if is_volume_end and maintainer_data.get("volume_conclusion"):
        conclusion_key = f"volume_conclusion_{chapter_num}"
        await asyncio.to_thread(db.set_system_config, conclusion_key, maintainer_data["volume_conclusion"])

    # 更新角色状态
    char_updates = maintainer_data.get("character_updates", {})
    for char_name, updates in char_updates.items():
        mental_state = updates.get("mental_state", "正常")
        tags = updates.get("tags", [])
        await asyncio.to_thread(db.update_character_state, book_id, char_name, mental_state, tags)

    # 添加新实体
    new_entities = maintainer_data.get("new_entities", [])
    for entity in new_entities:
        if entity.get("importance", 1) >= 2:
            await asyncio.to_thread(db.add_new_entity, book_id, entity)

    logger.success("✅ [Archive] 归档完成！")
    return {}


# ==========================================
# 3. 构建图
# ==========================================
workflow = StateGraph(NovelState)

workflow.add_node("planner", plan_node)
workflow.add_node("writer", write_node)
workflow.add_node("reviewer", unified_review_node)
workflow.add_node("archiver", archive_node)

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
            return "archiver"
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
        "archiver": "archiver",
        END: END
    }
)

workflow.add_edge("archiver", END)

# ==========================================
# 4. 编译
# ==========================================
memory = MemorySaver()
app = workflow.compile(checkpointer=memory)
