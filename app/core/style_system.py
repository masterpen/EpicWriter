"""
五维风格系统 (Five-Dimension Style System)
替代简单的作家人格库，通过五个维度的"选择惯性"精确复现写作风格。

五维度：
1. 视角距离 (perspective_distance) - 叙事镜头离主角多近
2. 节奏密度 (rhythm_density) - 信息压缩还是稀释
3. 感官偏向 (sensory_preference) - 五感中优先调用哪个
4. 对话策略 (dialogue_strategy) - 人物说话时作者介入多少
5. 留白阈值 (whitespace_threshold) - 多少信息留给读者自己拼
"""

import os
import json
from typing import Dict, List, Optional
from pydantic import BaseModel, Field
from app.core.logger import logger

STYLE_CARDS_DIR = "data/style_cards"


# ==================================================================
# 数据模型
# ==================================================================

class StyleExample(BaseModel):
    """风格示例片段"""
    scene_type: str = Field(..., description="场景类型: climax/dialogue/daily")
    content: str = Field(..., description="原文片段")
    source: str = Field("", description="来源说明")


class StyleCard(BaseModel):
    """五维风格卡"""
    name: str = Field(..., description="风格名称")
    author: str = Field("", description="目标作者/来源")

    # 五维度
    perspective_distance: str = Field(
        "tight",
        description="视角距离: tight(紧贴主角感官) / occasional_omniscient(偶尔上帝视角) / multi_pov(频繁切换)"
    )
    rhythm_density: str = Field(
        "high",
        description="节奏密度: high(一段多信息) / low(一件事写透再下一件)"
    )
    sensory_preference: List[str] = Field(
        default_factory=lambda: ["visual"],
        description="感官偏向排序，如 ['tactile','auditory','visual']"
    )
    dialogue_strategy: str = Field(
        "action_tagged",
        description="对话策略: bare(纯对话) / action_tagged(配动作) / inner_reaction(跟内心反应)"
    )
    whitespace_threshold: str = Field(
        "medium",
        description="留白阈值: high(从不解释心理) / medium(偶尔简短独白) / low(大段心理描写)"
    )

    # 生成的风格指令 (由五维度自动生成或手动覆盖)
    style_instructions: str = Field("", description="注入到writer prompt的风格指令文本")

    # 风格校验规则 (注入到review agent)
    review_checklist: List[str] = Field(
        default_factory=list,
        description="风格一致性检查项列表"
    )

    # Few-shot 示例库
    examples: List[StyleExample] = Field(
        default_factory=list,
        description="风格示例片段库，按场景类型分类"
    )

    # 兼容旧系统的原始persona文本 (可选)
    legacy_persona: str = Field("", description="兼容旧STYLE_CONFIGS的原始文本")


# ==================================================================
# 五维度 → 风格指令 自动生成
# ==================================================================

def generate_style_instructions(card: StyleCard) -> str:
    """根据五维度自动生成风格指令文本"""
    lines = ["你的写作风格必须满足："]

    # 视角距离
    perspective_map = {
        "tight": "视角始终紧贴主角的感官，只使用主角能看到/听到/感受到的信息，不使用上帝视角点评",
        "occasional_omniscient": "视角以主角为主，但允许偶尔跳出用叙述者语气做简短点评",
        "multi_pov": "允许在场景切换时切换视角人物，但每个场景内保持单一视角",
    }
    lines.append(f"- {perspective_map.get(card.perspective_distance, perspective_map['tight'])}")

    # 节奏密度
    if card.rhythm_density == "high":
        lines.append("- 高信息密度：一段话内同时推进动作、对话和环境，每段不超过3句话")
    else:
        lines.append("- 低信息密度：一件事写透再进入下一件，允许用整段铺垫一个情绪")

    # 感官偏向
    sensory_names = {
        "visual": "视觉(颜色/光影)",
        "auditory": "听觉(声音/节奏/沉默)",
        "tactile": "触觉(温度/质地/痛感)",
        "olfactory": "嗅觉",
        "gustatory": "味觉",
    }
    if card.sensory_preference:
        primary = sensory_names.get(card.sensory_preference[0], card.sensory_preference[0])
        lines.append(f"- 环境描写优先使用{primary}，而非其他感官")

    # 对话策略
    dialogue_map = {
        "bare": "对话极简，不加任何修饰标签，让对话内容本身传递情绪",
        "action_tagged": "每句对话后必须紧跟一个具体的身体动作或微表情，不解释情绪",
        "inner_reaction": "对话后紧跟主角的内心反应，用简短的心理活动推进节奏",
    }
    lines.append(f"- {dialogue_map.get(card.dialogue_strategy, dialogue_map['action_tagged'])}")

    # 留白阈值
    whitespace_map = {
        "high": "不写人物内心独白，情绪只通过行动和生理反应体现",
        "medium": "偶尔用一句简短的内心独白点明情绪，但绝不超过一句",
        "low": "允许适度的心理描写段落来展现人物内心挣扎",
    }
    lines.append(f"- {whitespace_map.get(card.whitespace_threshold, whitespace_map['medium'])}")

    return "\n".join(lines)


def generate_review_checklist(card: StyleCard) -> List[str]:
    """根据五维度自动生成风格校验清单"""
    checks = []

    if card.dialogue_strategy == "action_tagged":
        checks.append("对话后是否都跟了动作/微表情？（风格要求：是）")
    elif card.dialogue_strategy == "bare":
        checks.append("对话是否保持极简无修饰？（风格要求：是）")

    if card.rhythm_density == "high":
        checks.append("是否有超过3句话的段落？（风格要求：否）")

    if card.whitespace_threshold == "high":
        checks.append("是否出现了'他感到/他心想'等内心独白？（风格要求：否）")

    if card.sensory_preference and card.sensory_preference[0] != "visual":
        primary = card.sensory_preference[0]
        sensory_cn = {"auditory": "声音/温度", "tactile": "触觉/温度", "olfactory": "气味"}
        checks.append(f"环境描写是否优先使用了{sensory_cn.get(primary, primary)}而非视觉？（风格要求：是）")

    if card.perspective_distance == "tight":
        checks.append("是否出现了主角不可能知道的信息（上帝视角泄露）？（风格要求：否）")

    return checks


# ==================================================================
# 存储层：JSON文件持久化
# ==================================================================

def _ensure_dir():
    os.makedirs(STYLE_CARDS_DIR, exist_ok=True)


def save_style_card(card: StyleCard) -> None:
    """保存风格卡到文件"""
    _ensure_dir()
    # 自动生成指令（如果为空）
    if not card.style_instructions:
        card.style_instructions = generate_style_instructions(card)
    if not card.review_checklist:
        card.review_checklist = generate_review_checklist(card)

    filepath = os.path.join(STYLE_CARDS_DIR, f"{card.name}.json")
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(card.model_dump(), f, ensure_ascii=False, indent=2)
    logger.info(f"[StyleSystem] Saved style card: {card.name}")


def load_style_card(name: str) -> Optional[StyleCard]:
    """加载风格卡"""
    filepath = os.path.join(STYLE_CARDS_DIR, f"{name}.json")
    if not os.path.exists(filepath):
        return None
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        return StyleCard(**data)
    except Exception as e:
        logger.warning(f"[StyleSystem] Failed to load style card '{name}': {e}")
        return None


def list_style_cards() -> List[str]:
    """列出所有可用风格卡名称"""
    _ensure_dir()
    cards = []
    for f in os.listdir(STYLE_CARDS_DIR):
        if f.endswith(".json"):
            cards.append(f[:-5])
    return cards


def delete_style_card(name: str) -> bool:
    """删除风格卡"""
    filepath = os.path.join(STYLE_CARDS_DIR, f"{name}.json")
    if os.path.exists(filepath):
        os.remove(filepath)
        logger.info(f"[StyleSystem] Deleted style card: {name}")
        return True
    return False


# ==================================================================
# 运行时接口：供 WriterAgent 和 ReviewerAgent 调用
# ==================================================================

def get_writer_persona(style: str) -> str:
    """获取风格指令文本，供注入到writer prompt"""
    card = load_style_card(style)
    if card:
        return card.style_instructions or generate_style_instructions(card)
    # 兼容：如果没有对应风格卡，返回空字符串（由调用方fallback到旧系统）
    return ""


def get_few_shot_examples(style: str, scene_type: str = "") -> str:
    """获取few-shot示例，按场景类型筛选"""
    card = load_style_card(style)
    if not card or not card.examples:
        return ""

    # 筛选匹配的示例
    matched = [ex for ex in card.examples if not scene_type or ex.scene_type == scene_type]
    if not matched:
        # 没有精确匹配，返回所有示例（最多3个）
        matched = card.examples[:3]

    if not matched:
        return ""

    parts = ["【📖 写作范例 (请模仿以下语感和节奏)】", "---", ""]
    for ex in matched[:3]:
        parts.append(ex.content)
        parts.append("")
        parts.append("---")
        parts.append("")

    return "\n".join(parts)


def get_review_checklist(style: str) -> List[str]:
    """获取风格校验清单，供review agent使用"""
    card = load_style_card(style)
    if card:
        return card.review_checklist or generate_review_checklist(card)
    return []


def get_style_review_prompt(style: str) -> str:
    """生成风格一致性检查的prompt片段"""
    checklist = get_review_checklist(style)
    if not checklist:
        return ""

    lines = ["【风格一致性检查】", "对照以下风格基准，检查本章正文："]
    for item in checklist:
        lines.append(f"- {item}")
    lines.append("")
    lines.append("每处不符合，扣5分。")
    return "\n".join(lines)


# ==================================================================
# 迁移工具：将旧 STYLE_CONFIGS 转换为风格卡
# ==================================================================

# 旧系统风格到五维度的映射
LEGACY_STYLE_DIMENSIONS = {
    "男频-热血玄幻": {
        "perspective_distance": "tight",
        "rhythm_density": "high",
        "sensory_preference": ["tactile", "auditory", "visual"],
        "dialogue_strategy": "action_tagged",
        "whitespace_threshold": "high",
    },
    "男频-诡秘智斗": {
        "perspective_distance": "tight",
        "rhythm_density": "high",
        "sensory_preference": ["visual", "auditory"],
        "dialogue_strategy": "inner_reaction",
        "whitespace_threshold": "medium",
    },
    "男频-稳健苟道": {
        "perspective_distance": "tight",
        "rhythm_density": "low",
        "sensory_preference": ["visual", "tactile"],
        "dialogue_strategy": "inner_reaction",
        "whitespace_threshold": "low",
    },
    "男频-无敌碾压": {
        "perspective_distance": "occasional_omniscient",
        "rhythm_density": "high",
        "sensory_preference": ["visual", "auditory"],
        "dialogue_strategy": "action_tagged",
        "whitespace_threshold": "high",
    },
    "男频-末世/无限流": {
        "perspective_distance": "tight",
        "rhythm_density": "high",
        "sensory_preference": ["tactile", "visual"],
        "dialogue_strategy": "bare",
        "whitespace_threshold": "high",
    },
    "男频-系统数据": {
        "perspective_distance": "tight",
        "rhythm_density": "high",
        "sensory_preference": ["visual"],
        "dialogue_strategy": "action_tagged",
        "whitespace_threshold": "medium",
    },
    "男频-历史权谋": {
        "perspective_distance": "occasional_omniscient",
        "rhythm_density": "low",
        "sensory_preference": ["auditory", "visual"],
        "dialogue_strategy": "inner_reaction",
        "whitespace_threshold": "medium",
    },
}


def migrate_legacy_style(name: str, legacy_persona: str, legacy_few_shot: str = "") -> StyleCard:
    """将旧系统的风格配置迁移为五维风格卡"""
    dims = LEGACY_STYLE_DIMENSIONS.get(name, {
        "perspective_distance": "tight",
        "rhythm_density": "high",
        "sensory_preference": ["visual"],
        "dialogue_strategy": "action_tagged",
        "whitespace_threshold": "medium",
    })

    examples = []
    if legacy_few_shot:
        examples.append(StyleExample(
            scene_type="climax",
            content=legacy_few_shot,
            source="migrated from legacy FEW_SHOT_SAMPLES"
        ))

    card = StyleCard(
        name=name,
        author="system_preset",
        perspective_distance=dims["perspective_distance"],
        rhythm_density=dims["rhythm_density"],
        sensory_preference=dims["sensory_preference"],
        dialogue_strategy=dims["dialogue_strategy"],
        whitespace_threshold=dims["whitespace_threshold"],
        legacy_persona=legacy_persona,
        examples=examples,
    )
    # 生成指令和校验清单
    card.style_instructions = generate_style_instructions(card)
    card.review_checklist = generate_review_checklist(card)

    return card
