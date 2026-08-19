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
from typing import Dict, List, Optional, Tuple
from pydantic import BaseModel, Field
from app.core.logger import logger

STYLE_CARDS_DIR = "data/style_cards"

# 风格卡缓存：name -> (mtime, StyleCard)
# 避免每次 get_writer_persona / get_few_shot_examples 都读文件
_style_card_cache: Dict[str, Tuple[float, "StyleCard"]] = {}


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
    # 保存后立即更新缓存
    _style_card_cache[card.name] = (os.path.getmtime(filepath), card)
    logger.info(f"[StyleSystem] Saved style card: {card.name}")


def load_style_card(name: str) -> Optional[StyleCard]:
    """加载风格卡，带 mtime 缓存。文件未修改时直接返回缓存。"""
    filepath = os.path.join(STYLE_CARDS_DIR, f"{name}.json")
    try:
        mtime = os.path.getmtime(filepath)
    except OSError:
        # 文件不存在，清理可能存在的旧缓存
        _style_card_cache.pop(name, None)
        return None

    cached = _style_card_cache.get(name)
    if cached and cached[0] == mtime:
        return cached[1]

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        card = StyleCard(**data)
        _style_card_cache[name] = (mtime, card)
        return card
    except (json.JSONDecodeError, OSError, ValueError) as e:
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
        _style_card_cache.pop(name, None)  # 同步清理缓存
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


# ==================================================================
# 风格列表单一来源 (Single Source of Truth)
# 所有模块（前端硬编码、WorldBuilder 约束、迁移工具）都应以这里为准
# ==================================================================

# 风格下拉选项：value = 内部 key，label = 展示名，desc = 简短说明
LEGACY_STYLE_OPTIONS = [
    {"value": "男频-热血玄幻", "label": "⚔️ 热血玄幻", "desc": "高燃战斗，逆天改命"},
    {"value": "男频-系统数据", "label": "📊 系统数据", "desc": "面板升级，数据为王"},
    {"value": "男频-诡秘智斗", "label": "🔮 诡秘智斗", "desc": "悬疑推理，步步为营"},
    {"value": "男频-稳健苟道", "label": "🛡️ 稳健苟道", "desc": "稳扎稳打，长命百岁"},
    {"value": "男频-无敌碾压", "label": "👑 无敌碾压", "desc": "开局巅峰，横推一切"},
    {"value": "男频-末世/无限流", "label": "☢️ 末世废土", "desc": "末日求生，重建文明"},
    {"value": "男频-历史权谋", "label": "🏛️ 历史权谋", "desc": "朝堂博弈，权倾天下"},
    {"value": "女频-古言权谋", "label": "🌸 古言权谋", "desc": "宫廷争斗，凤仪天下"},
    {"value": "女频-现言救赎", "label": "💝 现言救赎", "desc": "都市情缘，温暖治愈"},
]

# WorldBuilder 流派约束：key 匹配 LEGACY_STYLE_OPTIONS.value
LEGACY_STYLE_CONSTRAINTS = {
    "男频-热血玄幻": """
    【流派强约束：热血玄幻】
    1. **金手指必须是"成长型"或"老爷爷型"**。能让废柴主角快速逆袭。
    2. **力量体系必须强调"破坏力"**。等级森严，一级压死人。
    3. **核心冲突必须是"莫欺少年穷"**。主角开局必须被轻视、退婚或羞辱。
    """,
    "男频-系统数据": """
    【流派强约束：系统数据流】
    1. **金手指必须是可视化的"系统面板"**。必须具备"数据化解析"、"任务发布"或"加点升级"功能。
    2. **力量体系必须数值化**。例如：战斗力、灵力值、熟练度。
    3. **世界观要有游戏感**。例如：杀怪掉宝、副本机制、排行榜。
    """,
    "男频-诡秘智斗": """
    【流派强约束：诡秘智斗】
    1. **金手指必须有巨大的副作用/代价**。例如：使用力量会扣除理智、寿命或引来不可名状的注视。
    2. **力量体系必须基于"规则"或"扮演"**。而不是单纯的比谁拳头大。
    3. **世界观必须充满谜团**。神明是疯狂的，历史是断层的。
    """,
    "男频-稳健苟道": """
    【流派强约束：稳健苟道】
    1. **金手指必须是辅助生存型**。例如：危机预感、长生不老、属性隐藏、模拟未来。严禁给主角"嘲讽脸"系统。
    2. **主角性格必须是"被迫害妄想症"**。只有在绝对安全（碾压十个境界）时才出手。
    """,
    "男频-无敌碾压": """
    【流派强约束：无敌碾压】
    1. **主角开局即巅峰**。金手指不需要升级，而是"解封"或"满级账号"。
    2. **核心爽点是"扮猪吃虎"**。反派越嚣张，死得越快。
    """,
    "男频-末世/无限流": """
    【流派强约束：末世废土】
    1. **金手指必须与"物资"或"生存"相关**。例如：无限空间、暴击掉落、避难所系统。
    2. **力量体系是次要的，资源才是核心**。世界观必须极其残酷，人吃人。
    """,
    "男频-历史权谋": """
    【流派强约束：历史权谋】
    1. **金手指不能太魔幻**。最好是"现代知识"、"图书馆"或"读心术"，严禁出现飞天遁地。
    2. **反派不是一个人，而是一个势力**。核心冲突是理念之争或利益分配。
    """,
    "女频-古言权谋": """
    【流派强约束：女频情感】
    1. **金手指服务于"魅力"或"关系"**。例如：万人迷光环、读心术、锦鲤运气。
    2. **反派通常是情敌、恶毒亲戚或主角的心魔**。
    3. **力量体系不重要**，重要的是情感链接和身份地位。
    """,
    "女频-现言救赎": """
    【流派强约束：现言救赎】
    1. **金手指服务于"魅力"或"关系"**。例如：万人迷光环、读心术、锦鲤运气。
    2. **反派通常是情敌、恶毒亲戚或主角的心魔**。
    3. **力量体系不重要**，重要的是情感链接和身份地位。
    """,
}


def get_style_constraint(style: str) -> str:
    """根据风格 key 返回 WorldBuilder 流派约束，未知风格返回标准约束"""
    if style in LEGACY_STYLE_CONSTRAINTS:
        return LEGACY_STYLE_CONSTRAINTS[style]
    # 兜底：关键词模糊匹配（兼容旧硬编码逻辑）
    if "系统" in style or "数据" in style:
        return LEGACY_STYLE_CONSTRAINTS["男频-系统数据"]
    if "热血" in style:
        return LEGACY_STYLE_CONSTRAINTS["男频-热血玄幻"]
    if "诡秘" in style or "智斗" in style:
        return LEGACY_STYLE_CONSTRAINTS["男频-诡秘智斗"]
    if "苟道" in style or "稳健" in style:
        return LEGACY_STYLE_CONSTRAINTS["男频-稳健苟道"]
    if "无敌" in style:
        return LEGACY_STYLE_CONSTRAINTS["男频-无敌碾压"]
    if "末世" in style:
        return LEGACY_STYLE_CONSTRAINTS["男频-末世/无限流"]
    if "权谋" in style or "历史" in style:
        return LEGACY_STYLE_CONSTRAINTS["男频-历史权谋"]
    if "女频" in style:
        return LEGACY_STYLE_CONSTRAINTS["女频-古言权谋"]
    return "【标准约束】设计一个逻辑自洽的网文世界，金手指要足够强力。"


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
