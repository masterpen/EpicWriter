from fastapi import APIRouter, HTTPException
from api.models import (
    WorkflowInput, WorkflowResponse, OutlineUpdateRequest,
    ChapterSaveRequest, ChapterArchiveRequest, BrainstormRequest
)
from app.workflow.graph import app as graph_app
from app.core.database import db
from app.agents.reviewer import UnifiedReviewerAgent
from app.agents.core import PlannerAgent
import asyncio
import uuid
import json
import re

router = APIRouter()

@router.post("/generate", response_model=WorkflowResponse)
async def generate_content(req: WorkflowInput):
    thread_id = req.thread_id or str(uuid.uuid4())
    thread_config = {"configurable": {"thread_id": thread_id}}

    inputs = {
        "chapter_num": req.chapter_num,
        "user_intent": req.user_intent,
        "style": req.style,
        "is_batch_mode": req.is_batch_mode,
        "manual_archive": not req.is_batch_mode,
        "book_id": req.book_id,
        "generate_mode": getattr(req, 'generate_mode', 'scenes'),
    }

    try:
        # LangGraph async invoke
        final_state = await graph_app.ainvoke(inputs, config=thread_config)

        return WorkflowResponse(
            draft=final_state.get('draft'),
            outline=final_state.get('outline'),
            chapter_num=req.chapter_num,
            thread_id=thread_id,
            status="paused" if not final_state.get('draft') and final_state.get('outline') else "completed",
            status_changed=final_state.get('status_changed', False)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/outline/approve", response_model=WorkflowResponse)
async def approve_outline(req: OutlineUpdateRequest):
    thread_config = {"configurable": {"thread_id": req.thread_id}}

    final_outline_data = {
        "chapter_title": req.chapter_title,
        "scenes": req.scenes
    }

    graph_app.update_state(thread_config, {
        "outline": final_outline_data,
        "style": req.style,
        "approved": True,
        "is_batch_mode": False,
        "manual_archive": True
    })

    try:
        # LangGraph async stream
        async for event in graph_app.astream(None, thread_config):
            pass
        final_snapshot = await graph_app.aget_state(thread_config)
        generated_draft = final_snapshot.values.get('draft', '')

        return WorkflowResponse(
            draft=generated_draft,
            outline=final_outline_data,
            chapter_num=final_snapshot.values.get('chapter_num', 1),
            thread_id=req.thread_id,
            status="completed" if generated_draft else "error",
            status_changed=final_snapshot.values.get('status_changed', False)
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/analyze")
async def analyze_draft(req: ChapterSaveRequest, book_id: str):
    """使用 UnifiedReviewer 进行分析（替代旧的 MaintainerAgent）"""
    reviewer = UnifiedReviewerAgent()

    all_chars = await asyncio.to_thread(db.get_all_characters_dict, book_id)
    filtered_context = {k: v for k, v in all_chars.items() if k in req.content}

    print(f"📊 [Analyze] book_id={book_id}, content_length={len(req.content or '')}, chars_count={len(all_chars)}")

    # 使用 UnifiedReviewer 的 review_and_analyze 方法
    result = await reviewer.review_and_analyze(
        draft=req.content,
        outline={},  # 独立分析模式，无大纲
        chapter_num=1,  # 默认值
        style="男频-热血玄幻",  # 默认值
        book_id=book_id,
        current_tags_dict=filtered_context
    )

    print(f"📊 [Analyze] result={result}")

    # 返回 maintainer 部分的结果（保持 API 兼容）
    return result.get("maintainer", {})

@router.post("/chapters/archive")
async def archive_chapter(book_id: str, req: ChapterArchiveRequest):
    try:
        cleaned_content = re.sub(r'\n*>>>STATUS_CHANGED<<<', '', req.content, flags=re.IGNORECASE).strip()

        await asyncio.to_thread(
            db.save_chapter,
            book_id, req.chapter_num, req.title, cleaned_content, req.summary
        )

        try:
            for update in req.character_updates:
                await asyncio.to_thread(
                    db.update_character_state,
                    book_id, update.name, update.mental_state, update.physical_tags
                )

            for entity in req.new_entities:
                entity_dict = {
                    "name": entity.name,
                    "type": entity.type,
                    "desc": entity.desc,
                    "owner": entity.owner,
                    "importance": entity.importance
                }
                if entity_dict.get("importance", 1) >= 2:
                    await asyncio.to_thread(db.add_new_entity, book_id, entity_dict)
        except Exception as e:
            print(f"Post-archive updates failed: {e}")

        return {"status": "success", "chapter_num": req.chapter_num}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/chapters/next_num")
async def get_next_chapter_num(book_id: str):
    return {"next_num": await asyncio.to_thread(db.get_next_chapter_num, book_id)}

@router.get("/state/{thread_id}")
async def get_graph_state(thread_id: str):
    thread_config = {"configurable": {"thread_id": thread_id}}
    try:
        snapshot = await graph_app.aget_state(thread_config)
        if snapshot and snapshot.values:
            return {
                "outline": snapshot.values.get("outline"),
                "draft": snapshot.values.get("draft")
            }
        return {}
    except Exception as e:
        return {}

@router.post("/brainstorm")
async def brainstorm_ideas(req: BrainstormRequest):
    planner = PlannerAgent()
    try:
        ideas = await planner.agenerate_brainstorming_options(
            req.user_intent, req.chapter_num, req.book_id
        )
        return ideas
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
