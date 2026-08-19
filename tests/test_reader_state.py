"""ReaderState（读者认知状态）模块测试。

覆盖：
- 默认状态结构
- apply_reader_updates 的合并/去重/消谜/还债/钳制逻辑
- render_for_planner 的 prompt 渲染
- get/save 的持久化（monkeypatch 掉 Neo4j db）
- prompt_config 新增 stage 的完整性
"""
import json

import pytest

from app.core import reader_state as rs
from app.core.prompt_config import DEFAULT_PROMPTS, get_prompt
from app.core.prompt_renderer import render_prompt


# ---------------------------------------------------------------
# 默认状态
# ---------------------------------------------------------------

class TestDefaultState:
    def test_structure(self):
        state = rs.default_reader_state()
        assert state["known_facts"] == []
        assert state["mysteries"] == []
        assert state["emotional_debts"] == []
        assert state["attention"] == 60
        assert state["info_gap"] == {"reader_over_hero": "", "reader_over_villain": ""}


# ---------------------------------------------------------------
# apply_reader_updates 合并逻辑
# ---------------------------------------------------------------

class TestApplyReaderUpdates:
    def test_new_questions_added_with_chapter(self):
        state = rs.default_reader_state()
        state = rs.apply_reader_updates(state, {"new_questions": ["盒子里是什么？"]}, chapter_num=3)
        assert state["mysteries"] == [{"question": "盒子里是什么？", "introduced": 3, "weight": 3}]

    def test_resolved_questions_removed_by_fuzzy_match(self):
        state = rs.default_reader_state()
        state["mysteries"] = [
            {"question": "林默的父亲是谁杀的？", "introduced": 1, "weight": 4},
            {"question": "黑袍人的身份", "introduced": 2, "weight": 3},
        ]
        state = rs.apply_reader_updates(
            state, {"resolved_questions": ["父亲是谁杀的"]}, chapter_num=5
        )
        assert len(state["mysteries"]) == 1
        assert state["mysteries"][0]["question"] == "黑袍人的身份"

    def test_duplicate_question_not_added_twice(self):
        state = rs.default_reader_state()
        state = rs.apply_reader_updates(state, {"new_questions": ["谁是凶手？"]}, chapter_num=1)
        state = rs.apply_reader_updates(state, {"new_questions": ["到底谁是凶手？"]}, chapter_num=2)
        assert len(state["mysteries"]) == 1

    def test_debts_add_and_pay(self):
        state = rs.default_reader_state()
        state = rs.apply_reader_updates(
            state,
            {"new_debts": [{"debt": "主角被赵家羞辱未反击", "urgency": 4}, "妹妹的仇未报"]},
            chapter_num=2,
        )
        assert len(state["emotional_debts"]) == 2
        assert state["emotional_debts"][0] == {"debt": "主角被赵家羞辱未反击", "introduced": 2, "urgency": 4}
        # 字符串形式默认 urgency=3
        assert state["emotional_debts"][1]["urgency"] == 3

        state = rs.apply_reader_updates(state, {"paid_debts": ["赵家羞辱"]}, chapter_num=6)
        assert len(state["emotional_debts"]) == 1
        assert state["emotional_debts"][0]["debt"] == "妹妹的仇未报"

    def test_debt_urgency_clamped(self):
        state = rs.default_reader_state()
        state = rs.apply_reader_updates(
            state, {"new_debts": [{"debt": "x", "urgency": 99}]}, chapter_num=1
        )
        assert state["emotional_debts"][0]["urgency"] == 5

    def test_facts_dedup_and_cap(self):
        state = rs.default_reader_state()
        updates = {"new_known_facts": [f"事实{i}" for i in range(30)]}
        state = rs.apply_reader_updates(state, updates, chapter_num=1)
        assert len(state["known_facts"]) == 20  # 上限

    def test_scalars_and_info_gap(self):
        state = rs.default_reader_state()
        state = rs.apply_reader_updates(
            state,
            {
                "anticipation": "主角什么时候觉醒",
                "last_hook": "盒子里只有一句话：别相信你母亲",
                "info_gap": {"reader_over_hero": "师父就是凶手"},
                "attention": 250,
            },
            chapter_num=4,
        )
        assert state["anticipation"] == "主角什么时候觉醒"
        assert state["last_hook"].startswith("盒子里")
        assert state["info_gap"]["reader_over_hero"] == "师父就是凶手"
        assert state["info_gap"]["reader_over_villain"] == ""  # 未提供的子键保持
        assert state["attention"] == 100  # clamp 到上限

    def test_malformed_updates_safe(self):
        state = rs.default_reader_state()
        assert rs.apply_reader_updates(state, None, 1) == state
        assert rs.apply_reader_updates(state, "bad", 1) == state
        # 列表里混入非法项不崩溃
        state = rs.apply_reader_updates(
            state,
            {"new_questions": [123, None, {"question": "合法问题"}, "  "],
             "new_debts": [42, {"nodebt": 1}, "合法债务"]},
            chapter_num=1,
        )
        assert [m["question"] for m in state["mysteries"]] == ["合法问题"]
        assert [d["debt"] for d in state["emotional_debts"]] == ["合法债务"]


# ---------------------------------------------------------------
# render_for_planner
# ---------------------------------------------------------------

class TestRenderForPlanner:
    def test_empty_state_renders_guidance(self):
        text = rs.render_for_planner(rs.default_reader_state(), chapter_num=1)
        assert "读者认知状态" in text
        assert "chapter_hook" in text
        assert "dilemma" in text
        assert "新埋 1 个钩子" in text  # 空谜团时的引导

    def test_full_state_renders_all_sections(self):
        state = rs.default_reader_state()
        state["mysteries"] = [{"question": "父亲之死的真相", "introduced": 1, "weight": 5}]
        state["emotional_debts"] = [{"debt": "打脸赵家", "introduced": 1, "urgency": 4}]
        state["anticipation"] = "主角反击"
        state["info_gap"] = {"reader_over_hero": "师父是凶手", "reader_over_villain": ""}
        state["last_hook"] = "别相信你母亲"

        text = rs.render_for_planner(state, chapter_num=20)
        assert "父亲之死的真相" in text
        assert "打脸赵家" in text
        assert "主角反击" in text
        assert "师父是凶手" in text
        assert "别相信你母亲" in text
        assert "欠太久" in text  # 谜团欠了 19 章 > 阈值
        assert "已积压" in text  # 债务欠了 19 章 > 阈值
        assert "严禁让主角无理由知晓" in text


# ---------------------------------------------------------------
# 持久化（monkeypatch db）
# ---------------------------------------------------------------

class FakeDB:
    def __init__(self):
        self.store = {}

    def get_system_config(self, key):
        return self.store.get(key)

    def set_system_config(self, key, value):
        self.store[key] = value


class TestPersistence:
    def test_save_and_get_roundtrip(self, monkeypatch):
        fake = FakeDB()
        monkeypatch.setattr(rs, "_get_db", lambda: fake)

        state = rs.default_reader_state()
        state["mysteries"] = [{"question": "q1", "introduced": 2, "weight": 3}]
        rs.save_reader_state("book1", state)

        loaded = rs.get_reader_state("book1")
        assert loaded["mysteries"][0]["question"] == "q1"
        assert loaded["attention"] == 60

    def test_get_missing_returns_default(self, monkeypatch):
        monkeypatch.setattr(rs, "_get_db", lambda: FakeDB())
        loaded = rs.get_reader_state("nonexistent")
        assert loaded == rs.default_reader_state()

    def test_get_corrupted_returns_default(self, monkeypatch):
        fake = FakeDB()
        fake.store["reader_state_book2"] = "{not json"
        monkeypatch.setattr(rs, "_get_db", lambda: fake)
        loaded = rs.get_reader_state("book2")
        assert loaded == rs.default_reader_state()


# ---------------------------------------------------------------
# prompt_config 新 stage 完整性
# ---------------------------------------------------------------

class TestPromptConfigStages:
    def test_new_stages_exist(self):
        for stage in ("reader_sim", "unified_review", "plan", "write_direct", "write_scene"):
            assert stage in DEFAULT_PROMPTS
            cfg = get_prompt(stage)
            assert cfg.get("system")

    def test_plan_template_has_suspense_fields(self):
        tpl = DEFAULT_PROMPTS["plan"]["template"]
        for field in ("reader_objective", "character_goal", "dilemma", "choice_cost",
                      "information_reveal", "irreversible_change", "chapter_hook"):
            assert field in tpl

    def test_review_template_has_readability(self):
        tpl = DEFAULT_PROMPTS["review"]["template"]
        assert "阅读吸引力" in tpl
        assert "readability_score" in tpl

    def test_write_direct_template_hook_placeholder_renders(self):
        tpl = DEFAULT_PROMPTS["write_direct"]["template"]
        assert "{hook_instruction}" in tpl
        rendered = render_prompt(tpl, {
            "style": "s", "writer_persona": "", "few_shot": "", "hero_profile": "",
            "opening_guide": "", "world_constraints": "", "feedback_instruction": "",
            "planned_title": "t", "outline": "o", "target_words": "4000",
            "position_tracker": "", "hook_instruction": "HOOK_BLOCK",
        })
        assert "HOOK_BLOCK" in rendered
        assert "{hook_instruction}" not in rendered

    def test_reader_sim_template_renders(self):
        tpl = DEFAULT_PROMPTS["reader_sim"]["template"]
        rendered = render_prompt(tpl, {
            "chapter_num": "3", "reader_profile": "PROFILE", "draft": "正文",
        })
        assert "PROFILE" in rendered
        assert "will_continue" in rendered
        assert "last_hook" in rendered
