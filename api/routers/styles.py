from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional
from app.core.style_system import (
    StyleCard, StyleExample, save_style_card, load_style_card,
    list_style_cards, delete_style_card, migrate_legacy_style,
    generate_style_instructions, generate_review_checklist,
)

router = APIRouter()


# =======================
# Request/Response Models
# =======================

class StyleExampleRequest(BaseModel):
    scene_type: str = Field(..., description="climax/dialogue/daily")
    content: str
    source: str = ""


class StyleCardRequest(BaseModel):
    name: str
    author: str = ""
    perspective_distance: str = "tight"
    rhythm_density: str = "high"
    sensory_preference: List[str] = ["visual"]
    dialogue_strategy: str = "action_tagged"
    whitespace_threshold: str = "medium"
    style_instructions: str = ""
    review_checklist: List[str] = []
    examples: List[StyleExampleRequest] = []
    legacy_persona: str = ""


class StyleCardResponse(BaseModel):
    name: str
    author: str
    perspective_distance: str
    rhythm_density: str
    sensory_preference: List[str]
    dialogue_strategy: str
    whitespace_threshold: str
    style_instructions: str
    review_checklist: List[str]
    examples: List[StyleExampleRequest]
    legacy_persona: str


class AddExampleRequest(BaseModel):
    scene_type: str
    content: str
    source: str = ""


# =======================
# Endpoints
# =======================

@router.get("/", response_model=List[str])
async def get_all_styles():
    """列出所有可用风格卡"""
    return list_style_cards()


@router.get("/{name}", response_model=StyleCardResponse)
async def get_style(name: str):
    """获取指定风格卡"""
    card = load_style_card(name)
    if not card:
        raise HTTPException(status_code=404, detail=f"Style card '{name}' not found")
    return card.model_dump()


@router.post("/", response_model=StyleCardResponse)
async def create_style(req: StyleCardRequest):
    """创建或更新风格卡"""
    examples = [StyleExample(**ex.model_dump()) for ex in req.examples]
    card = StyleCard(
        name=req.name,
        author=req.author,
        perspective_distance=req.perspective_distance,
        rhythm_density=req.rhythm_density,
        sensory_preference=req.sensory_preference,
        dialogue_strategy=req.dialogue_strategy,
        whitespace_threshold=req.whitespace_threshold,
        style_instructions=req.style_instructions,
        review_checklist=req.review_checklist,
        examples=examples,
        legacy_persona=req.legacy_persona,
    )
    # 自动生成指令和校验清单（如果未提供）
    if not card.style_instructions:
        card.style_instructions = generate_style_instructions(card)
    if not card.review_checklist:
        card.review_checklist = generate_review_checklist(card)

    save_style_card(card)
    return card.model_dump()


@router.delete("/{name}")
async def remove_style(name: str):
    """删除风格卡"""
    if not delete_style_card(name):
        raise HTTPException(status_code=404, detail=f"Style card '{name}' not found")
    return {"message": f"Style card '{name}' deleted"}


@router.post("/{name}/examples")
async def add_example(name: str, req: AddExampleRequest):
    """为风格卡添加示例片段"""
    card = load_style_card(name)
    if not card:
        raise HTTPException(status_code=404, detail=f"Style card '{name}' not found")

    card.examples.append(StyleExample(
        scene_type=req.scene_type,
        content=req.content,
        source=req.source,
    ))
    save_style_card(card)
    return {"message": "Example added", "total_examples": len(card.examples)}


@router.delete("/{name}/examples/{index}")
async def remove_example(name: str, index: int):
    """删除风格卡中的指定示例"""
    card = load_style_card(name)
    if not card:
        raise HTTPException(status_code=404, detail=f"Style card '{name}' not found")
    if index < 0 or index >= len(card.examples):
        raise HTTPException(status_code=400, detail="Invalid example index")

    card.examples.pop(index)
    save_style_card(card)
    return {"message": "Example removed", "total_examples": len(card.examples)}


@router.post("/{name}/regenerate")
async def regenerate_instructions(name: str):
    """重新根据五维度生成风格指令和校验清单"""
    card = load_style_card(name)
    if not card:
        raise HTTPException(status_code=404, detail=f"Style card '{name}' not found")

    card.style_instructions = generate_style_instructions(card)
    card.review_checklist = generate_review_checklist(card)
    save_style_card(card)
    return {
        "style_instructions": card.style_instructions,
        "review_checklist": card.review_checklist,
    }


@router.post("/migrate-legacy")
async def migrate_all_legacy():
    """将旧系统所有预设风格迁移为五维风格卡"""
    from app.agents.core import WriterAgent
    writer = WriterAgent()

    migrated = []
    for name, persona in writer.STYLE_CONFIGS.items():
        few_shot = writer.FEW_SHOT_SAMPLES.get(name, "")
        card = migrate_legacy_style(name, persona, few_shot)
        save_style_card(card)
        migrated.append(name)

    return {"migrated": migrated, "count": len(migrated)}
