from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

# =======================
# Book Models
# =======================

class BookCreateRequest(BaseModel):
    title: str = Field(..., description="Book title")
    # For manual creation

class BookResponse(BaseModel):
    book_id: str
    title: str
    created_at: Optional[str] = None

class BookListResponse(BaseModel):
    books: List[BookResponse]

# =======================
# World Building Models
# =======================

class GenesisRequest(BaseModel):
    idea: str = Field(..., description="Core idea or concept")
    style: str = Field(..., description="Novel style/genre")
    target_chapters: int = Field(100, ge=10, le=2000)

class WorldConfigRequest(BaseModel):
    intro: Optional[str] = None
    power_system: Optional[str] = None

class BookPlanUpdateRequest(BaseModel):
    current_volume: int

# =======================
# Workflow Models
# =======================

class WorkflowInput(BaseModel):
    book_id: str
    chapter_num: int
    user_intent: str = "剧情继续发展"
    style: str = "男频-热血玄幻"
    is_batch_mode: bool = False
    thread_id: Optional[str] = None
    generate_mode: str = "scenes"  # "scenes" or "direct"

class BrainstormRequest(BaseModel):
    user_intent: str
    book_id: str
    chapter_num: int = 1
    count: int = 5


class WorkflowResponse(BaseModel):
    draft: Optional[str] = None
    outline: Optional[Any] = None
    chapter_num: int
    thread_id: str
    status: str = "completed"
    status_changed: bool = False

class OutlineUpdateRequest(BaseModel):
    thread_id: str
    chapter_title: str
    scenes: List[Any]
    style: str

# =======================
# Chapter Models
# =======================

class ChapterSaveRequest(BaseModel):
    title: str
    content: str
    summary: str
    outline: Optional[Any] = None

class CharacterStatusUpdate(BaseModel):
    name: str
    mental_state: str
    physical_tags: List[str]

class EntityRegister(BaseModel):
    name: str
    type: str
    desc: str
    owner: str = ""
    importance: int = 1

class ChapterArchiveRequest(BaseModel):
    chapter_num: int
    title: str
    content: str
    summary: str
    character_updates: List[CharacterStatusUpdate]
    new_entities: List[EntityRegister]

# =======================
# Creative Interview Models (Phase 1)
# =======================

class InterviewStartRequest(BaseModel):
    raw_idea: str = Field(..., description="用户的原始创作想法")
    style: str = Field("男频-热血玄幻", description="目标风格")

class InterviewAnswerPayload(BaseModel):
    option_value: Optional[str] = Field(None, description="选中的选项 value")
    free_input: Optional[str] = Field(None, description="用户自由填写内容")

class InterviewAnswerRequest(BaseModel):
    question_id: str = Field(..., description="题目 ID")
    answer: Optional[InterviewAnswerPayload] = Field(None, description="回答内容")

class VariantGenerateRequest(BaseModel):
    constraints: Dict[str, Any] = Field(default_factory=dict, description="访谈得到的创作约束")
    style: str = Field("男频-热血玄幻", description="目标风格")
    n: int = Field(3, ge=2, le=5, description="方案数量")

class VariantDecideRequest(BaseModel):
    decision: str = Field(..., description="choose / merge / regenerate / freeform")
    chosen: Optional[str] = Field(None, description="选中的方案 label，如 A")
    merge: Optional[List[str]] = Field(None, description="融合的方案 label 列表，如 ['A','B']")
    freeform_data: Optional[Dict[str, Any]] = Field(None, description="自由输入的核心设定")
    total_chapters: int = Field(100, ge=10, le=2000, description="目标篇幅")
