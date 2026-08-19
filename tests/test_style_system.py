"""Style system 单元测试：五维风格指令与审核清单生成。"""
from app.core.style_system import (
    StyleCard,
    StyleExample,
    generate_style_instructions,
    generate_review_checklist,
    get_style_constraint,
    LEGACY_STYLE_OPTIONS,
    LEGACY_STYLE_CONSTRAINTS,
)


def _make_card(**kwargs) -> StyleCard:
    """构造测试用风格卡，默认值合法。"""
    defaults = {
        "name": "test-style",
        "author": "test",
        "perspective_distance": "tight",
        "rhythm_density": "high",
        "sensory_preference": ["visual"],
        "dialogue_strategy": "action_tagged",
        "whitespace_threshold": "medium",
    }
    defaults.update(kwargs)
    return StyleCard(**defaults)


class TestGenerateStyleInstructions:
    def test_returns_non_empty_string(self):
        card = _make_card()
        instructions = generate_style_instructions(card)
        assert isinstance(instructions, str)
        assert len(instructions) > 0

    def test_contains_perspective_instruction(self):
        card = _make_card(perspective_distance="tight")
        instructions = generate_style_instructions(card)
        assert "主角" in instructions or "视角" in instructions

    def test_high_rhythm_density_instruction(self):
        card = _make_card(rhythm_density="high")
        instructions = generate_style_instructions(card)
        assert "高信息密度" in instructions

    def test_low_rhythm_density_instruction(self):
        card = _make_card(rhythm_density="low")
        instructions = generate_style_instructions(card)
        assert "低信息密度" in instructions

    def test_sensory_preference_in_instruction(self):
        card = _make_card(sensory_preference=["auditory", "visual"])
        instructions = generate_style_instructions(card)
        assert "听觉" in instructions

    def test_dialogue_strategy_bare(self):
        card = _make_card(dialogue_strategy="bare")
        instructions = generate_style_instructions(card)
        assert "极简" in instructions

    def test_whitespace_high_no_inner_monologue(self):
        card = _make_card(whitespace_threshold="high")
        instructions = generate_style_instructions(card)
        assert "内心独白" in instructions

    def test_unknown_dimension_falls_back_gracefully(self):
        """未知维度值不应崩溃，应回退到默认。"""
        card = _make_card(perspective_distance="unknown_value")
        instructions = generate_style_instructions(card)
        assert isinstance(instructions, str)
        assert len(instructions) > 0


class TestGenerateReviewChecklist:
    def test_action_tagged_generates_dialogue_check(self):
        card = _make_card(dialogue_strategy="action_tagged")
        checklist = generate_review_checklist(card)
        assert any("动作" in item or "微表情" in item for item in checklist)

    def test_bare_generates_minimalism_check(self):
        card = _make_card(dialogue_strategy="bare")
        checklist = generate_review_checklist(card)
        assert any("极简" in item for item in checklist)

    def test_high_rhythm_generates_length_check(self):
        card = _make_card(rhythm_density="high")
        checklist = generate_review_checklist(card)
        assert any("3句话" in item for item in checklist)

    def test_low_rhythm_no_length_check(self):
        card = _make_card(rhythm_density="low")
        checklist = generate_review_checklist(card)
        assert not any("3句话" in item for item in checklist)

    def test_high_whitespace_blocks_inner_monologue(self):
        card = _make_card(whitespace_threshold="high")
        checklist = generate_review_checklist(card)
        assert any("内心独白" in item for item in checklist)

    def test_tight_perspective_blocks_omniscient(self):
        card = _make_card(perspective_distance="tight")
        checklist = generate_review_checklist(card)
        assert any("上帝视角" in item for item in checklist)

    def test_non_visual_sensory_generates_check(self):
        card = _make_card(sensory_preference=["auditory"])
        checklist = generate_review_checklist(card)
        assert any("听觉" in item or "声音" in item for item in checklist)

    def test_returns_list_type(self):
        card = _make_card()
        checklist = generate_review_checklist(card)
        assert isinstance(checklist, list)


class TestStyleCardModel:
    def test_default_values(self):
        card = StyleCard(name="test")
        assert card.perspective_distance == "tight"
        assert card.rhythm_density == "high"
        assert card.sensory_preference == ["visual"]
        assert card.dialogue_strategy == "action_tagged"
        assert card.whitespace_threshold == "medium"
        assert card.examples == []
        assert card.review_checklist == []

    def test_style_example_model(self):
        ex = StyleExample(scene_type="climax", content="test content")
        assert ex.scene_type == "climax"
        assert ex.content == "test content"
        assert ex.source == ""


class TestStyleOptionsSSOT:
    def test_all_options_have_value_and_label(self):
        for opt in LEGACY_STYLE_OPTIONS:
            assert "value" in opt
            assert "label" in opt
            assert len(opt["value"]) > 0
            assert len(opt["label"]) > 0

    def test_all_constraint_keys_exist_in_options(self):
        option_values = {opt["value"] for opt in LEGACY_STYLE_OPTIONS}
        for constraint_key in LEGACY_STYLE_CONSTRAINTS:
            assert constraint_key in option_values, (
                f"约束 key '{constraint_key}' 在 LEGACY_STYLE_OPTIONS 中不存在"
            )

    def test_get_style_constraint_returns_known(self):
        constraint = get_style_constraint("男频-热血玄幻")
        assert isinstance(constraint, str)
        assert len(constraint) > 0
        assert "热血玄幻" in constraint

    def test_get_style_constraint_unknown_returns_default(self):
        constraint = get_style_constraint("不存在的风格")
        assert isinstance(constraint, str)
        assert len(constraint) > 0
