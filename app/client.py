import requests
from typing import Optional, Dict, List, Any
from app.core.config import settings
from app.core.logger import logger

class APIClient:
    def __init__(self):
        self.base_url = settings.API_BASE_URL

    def _get(self, endpoint: str):
        try:
            resp = requests.get(f"{self.base_url}{endpoint}")
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.error(f"GET {endpoint} failed: {e}")
            return None

    def _post(self, endpoint: str, data: Dict):
        try:
            resp = requests.post(f"{self.base_url}{endpoint}", json=data)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.error(f"POST {endpoint} failed: {e}")
            return None

    def _patch(self, endpoint: str, data: Dict):
        try:
            resp = requests.patch(f"{self.base_url}{endpoint}", json=data)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.error(f"PATCH {endpoint} failed: {e}")
            return None

    def _delete(self, endpoint: str):
        try:
            resp = requests.delete(f"{self.base_url}{endpoint}")
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.error(f"DELETE {endpoint} failed: {e}")
            return None

    def _put(self, endpoint: str, data: Dict):
        try:
            resp = requests.put(f"{self.base_url}{endpoint}", json=data)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.error(f"PUT {endpoint} failed: {e}")
            return None

    # ==========================
    # Books
    # ==========================
    def get_all_books(self):
        data = self._get("/books/")
        # Convert response list to match what UI expects (list of dicts with 'b.title' etc? No, UI expects that format from Neo4j)
        # But UI logic in web_app.py:206 `books = db.get_all_books()`
        # And `db.get_all_books` returned `[{'b.book_id':..., 'b.title':...}]`
        # My API returns `{'books': [{'book_id':..., 'title':...}]}`
        # I need to adapt the response to match UI expectation or Change UI.
        # I will adapt CLIENT to return what UI expects to minimize UI changes.
        if not data: return []
        
        # Adapt to legacy format (UI uses book['b.title'])
        # Or better: Update UI to use clean attributes. 
        # But to be safe in this refactor, let's look at web_app.py usage.
        # web_app.py:209: `book['b.title']`
        # So I should mock that structure or change web_app.py. 
        # I'll change web_app.py to use nice keys, it's cleaner.
        return data.get("books", [])

    def create_book(self, title: str):
        data = self._post("/books/", {"title": title})
        return data.get("book_id") if data else None

    def delete_book(self, book_id: str):
        self._delete(f"/books/{book_id}")

    def genesis_book(self, idea, est_chapters, style):
        data = self._post("/books/genesis", {
            "idea": idea,
            "est_chapters": est_chapters,
            "style": style
        })
        # API returns BookResponse, UI expects dictionary of world_data? 
        # No, UI `builder.build_world` returned dict, then UI called `db.create_book`.
        # Now API does everything. UI just needs to reload or get ID.
        # web_app.py:156 call `world_data = builder.build_world(...)`
        # This is a major change in flow. 
        # In `web_app.py`, it gets `world_data`, then shows status "Creating file...", then `db.create`.
        # With API, `genesis_book` calculates AND creates.
        # Function returns book_id and title.
        return data

    def get_world_config(self, book_id):
        return self._get(f"/books/{book_id}/world")

    def update_world_config(self, book_id, intro, power_system):
        self._patch(f"/books/{book_id}/world", {
            "intro": intro,
            "power_system": power_system
        })

    def get_book_plan(self, book_id):
        return self._get(f"/books/{book_id}/plan")

    def update_book_plan_field(self, book_id, field, value):
        # We only support 'current_volume' in API right now
        if field == "current_volume":
            self._patch(f"/books/{book_id}/plan", {"current_volume": value})

    def get_next_chapter_num(self, book_id):
        data = self._get(f"/workflow/chapters/next_num?book_id={book_id}")
        return data.get("next_num", 1) if data else 1

    # ==========================
    # Characters
    # ==========================
    def get_ui_main_characters(self, book_id):
        data = self._get(f"/books/{book_id}/characters/active")
        return data.get("main", []) if data else []

    def get_ui_support_characters(self, book_id):
        data = self._get(f"/books/{book_id}/characters/active")
        return data.get("support", []) if data else []

    def get_hero_full_status(self, book_id):
        return self._get(f"/books/{book_id}/characters/hero")

    # ==========================
    # Workflow
    # ==========================
    def generate_content(self, inputs):
        # inputs: chapter_num, user_intent, style, is_batch_mode, book_id, (thread_id implicit?)
        # UI stores thread_id in session.
        # We need to pass it.
        # API expects WorkflowInput
        payload = {
            "book_id": inputs.get("book_id"),
            "chapter_num": inputs.get("chapter_num"),
            "user_intent": inputs.get("user_intent"),
            "style": inputs.get("style"),
            "is_batch_mode": inputs.get("is_batch_mode"),
            "thread_id": inputs.get("thread_id") # passed from UI
        }
        return self._post("/workflow/generate", payload)

    def analyze_status_change(self, content, context=None):
        # Context is used server side in API `analyze` endpoint logic (it fetches from DB).
        # So we just pass content.
        # API requires book_id for fetching context.
        # But `web_app.py` calling maintains.analyze_status_change(draft, context)
        # We need to change the flow. UI shouldn't fetch context.
        # We need to know book_id here. 
        # Refactor: `client.analyze_status_change(content, book_id)`
        return {} # Placeholder, see implementation note

    def analyze_draft(self, book_id, content):
        data = self._post(f"/workflow/analyze?book_id={book_id}", {
            "title": "Temp", # API requires title/summary but only content matters for analysis?
            "content": content,
            "summary": "",
            "outline": {}
        })
        return data

    def archive_chapter(self, book_id, chapter_data):
        # data: chapter_num, title, content, summary, character_updates, new_entities
        self._post(f"/workflow/chapters/archive?book_id={book_id}", chapter_data)

    def get_graph_state(self, thread_id):
        return self._get(f"/workflow/state/{thread_id}")

    def generate_brainstorming_options(self, user_intent, chapter_num, book_id):
        return self._post("/workflow/brainstorm", {
            "user_intent": user_intent,
            "chapter_num": chapter_num if isinstance(chapter_num, int) else 1,
            "book_id": book_id,
            "count": 3
        })

    def approve_outline(self, thread_id: str, chapter_title: str, scenes: List[str], style: str):
        return self._put("/workflow/outline/approve", {
            "thread_id": thread_id,
            "chapter_title": chapter_title,
            "scenes": scenes,
            "style": style
        })

client = APIClient()
