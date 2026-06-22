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
    est_chapters: int = Field(100, ge=10, le=2000)

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
    scenes: List[str]
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
