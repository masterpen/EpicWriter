from fastapi import APIRouter, Depends, HTTPException
from api.models import (
    BookCreateRequest, BookListResponse, BookResponse, GenesisRequest,
    WorldConfigRequest, BookPlanUpdateRequest,
    InterviewStartRequest, InterviewAnswerRequest,
    VariantGenerateRequest, VariantDecideRequest,
)
from app.core.database import db
from app.agents.world_builder import WorldBuilderAgent
from app.agents.creative_interviewer import CreativeInterviewerAgent
from app.agents.multi_draft_builder import MultiDraftBuilderAgent
from api.routers.auth import oauth2_scheme, decode_token
import asyncio
import uuid

router = APIRouter()


def get_current_user_id(token: str = Depends(oauth2_scheme)) -> str:
    """从 JWT 提取当前用户 ID，所有书籍接口强制登录"""
    payload = decode_token(token)
    return payload.get("sub")

@router.get("/", response_model=BookListResponse)
async def get_books(user_id: str = Depends(get_current_user_id)):
    raw_books = await asyncio.to_thread(db.get_all_books, user_id)
    books = []
    if raw_books:
        for b in raw_books:
            books.append(BookResponse(
                book_id=b.get('b.book_id'),
                title=b.get('b.title'),
                created_at=str(b.get('b.created_at', ''))
            ))
    return BookListResponse(books=books)

@router.post("/", response_model=BookResponse)
async def create_book(req: BookCreateRequest, user_id: str = Depends(get_current_user_id)):
    new_id = await asyncio.to_thread(db.create_book, req.title, user_id)
    default_template = {
        "intro": "这是一个全新的世界，等待造物主填充细节。",
        "hero": {"name": "待定主角", "identity": "某人", "tags": ["普通"]},
        "villain": {"name": "待定反派", "identity": "阴影", "tags": ["神秘"]},
        "book_plan": {
            "main_story": "主角踏上了未知的旅程。",
            "volumes": [{"title": "第一卷：序章", "goal": "确立主角目标", "estimated_chapters": 10, "antagonist": {"name": "未知麻烦", "identity": "路障"}, "key_events": ["故事开始"]}]
        }
    }
    await asyncio.to_thread(db.init_book_world, new_id, default_template)
    return BookResponse(book_id=new_id, title=req.title)

@router.delete("/{book_id}")
async def delete_book(book_id: str, user_id: str = Depends(get_current_user_id)):
    await asyncio.to_thread(db.delete_book, book_id)
    return {"message": f"Book {book_id} deleted"}

@router.post("/genesis", response_model=BookResponse)
async def genesis_book(req: GenesisRequest, user_id: str = Depends(get_current_user_id)):
    builder = WorldBuilderAgent()
    try:
        world_data = await asyncio.to_thread(
            builder.build_world,
            req.idea, req.target_chapters, req.style, "TEMP_GENESIS"
        )
        if not world_data:
            raise HTTPException(status_code=500, detail="World generation failed")

        auto_title = world_data.get("book_title", f"Project: {req.idea[:10]}")
        new_id = await asyncio.to_thread(db.create_book, auto_title, user_id, req.style)
        await asyncio.to_thread(db.init_book_world, new_id, world_data)
        
        return BookResponse(book_id=new_id, title=auto_title)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# =======================
# 🎙️ 创作访谈 + 多方案竞争 (Phase 1)
# =======================

@router.post("/interview/start")
async def interview_start(req: InterviewStartRequest, user_id: str = Depends(get_current_user_id)):
    """启动创作访谈，返回第一个问题"""
    interviewer = CreativeInterviewerAgent()
    try:
        result = await interviewer.astart_session(req.raw_idea, req.style)
        result["user_id"] = user_id
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/interview/{session_id}/answer")
async def interview_answer(session_id: str, req: InterviewAnswerRequest,
                           user_id: str = Depends(get_current_user_id)):
    """回答当前问题，返回下一个问题（答完返回 question=None）"""
    interviewer = CreativeInterviewerAgent()
    try:
        option_value = ""
        free_input = ""
        if req.answer:
            option_value = req.answer.option_value or ""
            free_input = req.answer.free_input or ""
        return await interviewer.anext_question(
            session_id, req.question_id, option_value, free_input
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/interview/{session_id}/skip")
async def interview_skip(session_id: str, user_id: str = Depends(get_current_user_id)):
    """跳过当前题，返回下一题"""
    interviewer = CreativeInterviewerAgent()
    try:
        return await interviewer.askip(session_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/interview/{session_id}/complete")
async def interview_complete(session_id: str, user_id: str = Depends(get_current_user_id)):
    """结束访谈，返回结构化约束"""
    interviewer = CreativeInterviewerAgent()
    try:
        return await interviewer.abuild_constraints(session_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/interview/{session_id}/variants/generate")
async def variants_generate(session_id: str, req: VariantGenerateRequest,
                            user_id: str = Depends(get_current_user_id)):
    """基于访谈约束生成多套差异化核心设定方案"""
    builder = MultiDraftBuilderAgent()
    try:
        constraints = req.constraints or {}
        if not constraints:
            session_data = await asyncio.to_thread(db.get_interview_session, session_id)
            if not session_data:
                raise HTTPException(status_code=404, detail="访谈会话不存在")
            constraints = session_data.get("collected_constraints", {}) or {}
            req.style = req.style or session_data.get("style", "男频-热血玄幻")
        variants = await builder.agenerate_variants(constraints, req.style, req.n)
        await asyncio.to_thread(db.save_bible_variants, session_id, variants)
        return {"session_id": session_id, "variants": variants}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/interview/{session_id}/variants/decide")
async def variants_decide(session_id: str, req: VariantDecideRequest,
                          user_id: str = Depends(get_current_user_id)):
    """用户选定方案方向后，基于约束+方案生成完整 Bible 并创建书籍"""
    from app.core.logger import logger
    try:
        session_data = await asyncio.to_thread(db.get_interview_session, session_id)
        if not session_data:
            raise HTTPException(status_code=404, detail="访谈会话不存在")

        variants = await asyncio.to_thread(db.get_bible_variants, session_id)
        constraints = session_data.get("collected_constraints", {}) or {}
        style = session_data.get("style", "") or req.style

        # 确定最终方向：choose / merge / freeform
        variant = {}
        if req.decision == "choose" and req.chosen:
            variant = next((v for v in variants if v["label"] == req.chosen), {})
            await asyncio.to_thread(db.set_variant_decision, session_id, req.chosen, "chosen")
        elif req.decision == "merge" and req.merge:
            chosen_cores = []
            for lbl in req.merge:
                await asyncio.to_thread(db.set_variant_decision, session_id, lbl, "merged")
                v = next((v for v in variants if v["label"] == lbl), None)
                if v:
                    chosen_cores.append(v.get("core_setting", {}))
            if chosen_cores:
                variant = {"seed": "融合方案: " + " + ".join(req.merge),
                           "core_setting": _merge_core_settings(chosen_cores)}
        elif req.decision == "freeform":
            variant = {
                "seed": "用户自由设定",
                "core_setting": req.freeform_data or {},
            }
        elif req.decision == "regenerate":
            raise HTTPException(status_code=400, detail="请重新调用 variants/generate 生成新方案")

        # 生成完整 Bible（草稿，不直接建书）
        builder = WorldBuilderAgent()
        total_chapters = req.total_chapters or 100
        world_data = await builder.abuild_world_from_constraints(
            constraints, variant, total_chapters, style, session_id
        )
        if not world_data:
            raise HTTPException(status_code=500, detail="Bible 生成失败")

        await asyncio.to_thread(db.save_interview_bible_draft, session_id, world_data)
        logger.info(f"[Interview] 会话 {session_id} Bible 草稿生成完成，等待用户确认")

        return {
            "session_id": session_id,
            "draft": world_data,
            "title": world_data.get("book_title", "Untitled"),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/interview/{session_id}/bible/confirm")
async def bible_confirm(session_id: str, user_id: str = Depends(get_current_user_id)):
    """用户确认 Bible 草稿后创建书籍并写入世界"""
    from app.core.logger import logger
    try:
        world_data = await asyncio.to_thread(db.get_interview_bible_draft, session_id)
        if not world_data:
            raise HTTPException(status_code=404, detail="未找到 Bible 草稿，请先完成方案确认")

        session_data = await asyncio.to_thread(db.get_interview_session, session_id)
        style = (session_data or {}).get("style", "") or "男频-热血玄幻"

        auto_title = world_data.get("book_title", "Untitled")
        new_id = await asyncio.to_thread(db.create_book, auto_title, user_id, style)
        await asyncio.to_thread(db.init_book_world, new_id, world_data)
        await asyncio.to_thread(db.mark_interview_completed_with_book, session_id, new_id)
        logger.info(f"[Interview] 会话 {session_id} → 书籍 {new_id} ({auto_title})")

        return BookResponse(book_id=new_id, title=auto_title)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def _merge_core_settings(cores: list) -> dict:
    """简单合并多套核心设定：字段级优先取第一个非空值"""
    merged = {}
    for c in cores:
        if not isinstance(c, dict):
            continue
        for k, v in c.items():
            if k not in merged and v:
                merged[k] = v
    return merged

@router.get("/{book_id}/world")
async def get_world_config(book_id: str):
    config = await asyncio.to_thread(db.get_world_config, book_id)
    if not config:
        raise HTTPException(status_code=404, detail="World config not found")
    return config

@router.patch("/{book_id}/world")
async def update_world_config(book_id: str, req: WorldConfigRequest):
    try:
        await asyncio.to_thread(db.update_world_config, book_id, req.intro, req.power_system)
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.patch("/{book_id}/plan")
async def update_book_plan(book_id: str, req: BookPlanUpdateRequest):
    try:
        await asyncio.to_thread(db.update_book_plan_field, book_id, "current_volume", req.current_volume)
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{book_id}/plan")
async def get_book_plan(book_id: str):
    plan = await asyncio.to_thread(db.get_book_plan, book_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Book plan not found")
    return plan

@router.get("/{book_id}/characters/hero")
async def get_hero(book_id: str):
    hero = await asyncio.to_thread(db.get_hero_full_status, book_id)
    if not hero:
        raise HTTPException(status_code=404, detail="Hero not found")
    return hero

@router.get("/{book_id}/characters/active")
async def get_active_characters(book_id: str):
    main, support = await asyncio.gather(
        asyncio.to_thread(db.get_ui_main_characters, book_id),
        asyncio.to_thread(db.get_ui_support_characters, book_id),
    )
    return {"main": main, "support": support}

@router.get("/{book_id}/reader-state")
async def get_book_reader_state(book_id: str):
    """获取读者认知状态（未解之谜/情绪债务/信息差/读者期待）"""
    from app.core.reader_state import get_reader_state
    return await asyncio.to_thread(get_reader_state, book_id)

@router.get("/{book_id}")
async def get_book(book_id: str):
    """获取书籍基本信息"""
    book = await asyncio.to_thread(db.get_book, book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    return book

@router.patch("/{book_id}/style")
async def update_book_style(book_id: str, req: dict):
    """更新书籍风格"""
    style = req.get("style", "")
    await asyncio.to_thread(db.update_book_style, book_id, style)
    return {"status": "success", "style": style}
