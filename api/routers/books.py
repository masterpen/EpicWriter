from fastapi import APIRouter, HTTPException
from api.models import (
    BookCreateRequest, BookListResponse, BookResponse, GenesisRequest,
    WorldConfigRequest, BookPlanUpdateRequest
)
from app.core.database import db
from app.agents.world_builder import WorldBuilderAgent
import asyncio

router = APIRouter()


# 临时移除认证以便测试
# def get_current_user_id(token: str = Depends(oauth2_scheme)) -> str:
#     payload = decode_token(token)
#     return payload.get("sub")

@router.get("/", response_model=BookListResponse)
async def get_books():
    raw_books = await asyncio.to_thread(db.get_all_books)
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
async def create_book(req: BookCreateRequest):
    new_id = await asyncio.to_thread(db.create_book, req.title)
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
async def delete_book(book_id: str):
    await asyncio.to_thread(db.delete_book, book_id)
    return {"message": f"Book {book_id} deleted"}

@router.post("/genesis", response_model=BookResponse)
async def genesis_book(req: GenesisRequest):
    builder = WorldBuilderAgent()
    try:
        world_data = await asyncio.to_thread(
            builder.build_world,
            req.idea, req.est_chapters, req.style, "TEMP_GENESIS"
        )
        if not world_data:
            raise HTTPException(status_code=500, detail="World generation failed")
            
        auto_title = world_data.get("book_title", f"Project: {req.idea[:10]}")
        new_id = await asyncio.to_thread(db.create_book, auto_title, req.style)
        await asyncio.to_thread(db.init_book_world, new_id, world_data)
        
        return BookResponse(book_id=new_id, title=auto_title)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

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
