import asyncio
from app.agents.base import BaseAgent
from app.core.database import db
from app.core.json_utils import parse_llm_json

class FactCheckerAgent(BaseAgent):
    def __init__(self):
        super().__init__("你是一个极为严谨的事实核查员（Fact Checker）。你的任务是找出小说正文与既有设定、历史剧情之间的逻辑矛盾。", stage_key="fact_check")
        
    def check_facts(self, draft, book_id, chapter_num):
        print(f"🔍 [FactChecker] 正在核查第 {chapter_num} 章的事实逻辑...")
        
        world_config = db.get_world_config(book_id)
        hero_state = db.get_hero_state(book_id)
        
        # 🟢 用 volume_context（5章摘要）替代仅2章，给足上下文避免误判
        prev_context = db.get_volume_context(book_id, chapter_num, count=5) if chapter_num > 1 else "（首章，无历史）"
        
        prompt = f"""
        任务：核查以下小说正文是否存在**严重的、不可解释的**设定冲突或逻辑漏洞。

        【基础设定库】
        - 主角当前状态：{hero_state}
        - 力量体系：{world_config.get('power_system', '无')}

        【近期剧情 (5章上下文)】
        {prev_context}

        【待核查正文 (第{chapter_num}章)】
        {draft[:4000]}

        【核查规则 — 严格标准，宁可漏报不可误报】
        1. **仅报硬逻辑矛盾**：主角断臂后双手持刀、已死角色复活、未获得的物品凭空出现。必须引用原文两处明确矛盾的语句才报。
        2. **不报正常发展**：主角从炼气期升到筑基期、获得新装备新技能、结识新角色，这些是正常剧情推进，不是冲突。
        3. **不报叙事选择**：主角采用什么策略、选择哪条路——这些是创作自由，不是逻辑错误。
        4. **不报轻微出入**：大纲与正文有细节出入，以正文为准。摘要是简化的，不要求100%对应。
        5. **不报合理变化**：角色心情变化、策略调整、临时改变计划，都不是冲突。
        6. 🚫 **绝对排除以下误报**：
           - "只提供了一种方案/路径" → 叙事选择，非冲突
           - "主角选择了A而非B" → 剧情方向，非冲突

        【输出格式】
        请以 JSON 格式返回：
        {{
            "has_conflict": true/false,
            "conflicts": ["确切的矛盾描述（必须引用原文两句对照）"],
            "penalty_score": 5
        }}

        ⚠️ 如果你不确定是否算冲突 → 返回 has_conflict: false。宁可漏报！"""
        
        response = self.call(prompt, json_mode=True)

        default = {"has_conflict": False, "conflicts": [], "penalty_score": 0}
        result = parse_llm_json(response, default=default)
        if result is None:
            print(f"❌ [FactChecker] 解析失败: {response[:200]}")
            return default
        return result

    async def acheck_facts(self, draft, book_id, chapter_num):
        """异步版事实核查"""
        print(f"🔍 [FactChecker] 正在异步核查第 {chapter_num} 章的事实逻辑...")
        
        # 异步并行获取 DB 数据
        world_config, hero_state, prev_context = await asyncio.gather(
            asyncio.to_thread(db.get_world_config, book_id),
            asyncio.to_thread(db.get_hero_state, book_id),
            asyncio.to_thread(db.get_volume_context, book_id, chapter_num, count=5),
        )
        
        if chapter_num == 1:
            prev_context = "（首章，无历史）"
        
        prompt = f"""
        任务：核查以下小说正文是否存在**严重的、不可解释的**设定冲突或逻辑漏洞。

        【基础设定库】
        - 主角当前状态：{hero_state}
        - 力量体系：{world_config.get('power_system', '无')}

        【近期剧情 (5章上下文)】
        {prev_context}

        【待核查正文 (第{chapter_num}章)】
        {draft[:4000]}

        【核查规则 — 严格标准，宁可漏报不可误报】
        1. **仅报硬逻辑矛盾**：主角断臂后双手持刀、已死角色复活、未获得的物品凭空出现。只有引用原文两处明确矛盾的语句才报。
        2. **不报正常发展**：升级、获得新装备新技能、结识新角色，都是正常剧情推进。
        3. **不报叙事选择**：角色采用什么策略、选择哪条路、说了几句话——这些是创作自由，不是逻辑错误。
        4. **不报轻微出入**：数量差1-2个、措辞略有不同，不算冲突。
        5. **不报合理变化**：角色心情变化、策略调整、临时改变计划，不是冲突。
        6. 🚫 **绝对排除以下误报**：
           - "只提供了一种方案/路径" → 叙事选择，非冲突
           - "主角选择了A而非B" → 剧情方向，非冲突
           - "大纲说要战斗但正文写了谈判" → 大纲是参考，以正文为准
           - 摘要与正文细节有出入 → 摘要是简化的，以正文为准

        【输出格式】
        {{
            "has_conflict": true/false,
            "conflicts": ["确切的矛盾描述（必须引用原文两句对照）"],
            "penalty_score": 5
        }}

        ⚠️ 如果你不确定是否算冲突 → 返回 has_conflict: false。宁可漏报！"""
        
        response = await self.acall(prompt, json_mode=True)

        default = {"has_conflict": False, "conflicts": [], "penalty_score": 0}
        result = parse_llm_json(response, default=default)
        if result is None:
            print(f"❌ [FactChecker] 解析失败: {response[:200]}")
            return default
        return result
