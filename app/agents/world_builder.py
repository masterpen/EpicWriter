import json
import re
from app.agents.base import BaseAgent

class WorldBuilderAgent(BaseAgent):
    def __init__(self):
        super().__init__("你是一个世界观架构师。你的任务是根据用户的简短描述，设计一套完整、逻辑自洽且极具爽感的网文世界观。")
    def _get_style_constraints(self, style):
        """
        根据流派返回强力的世界观构建约束
        """
        constraints = ""
        
        if "系统" in style or "数据" in style:
            constraints = """
            【流派强约束：系统数据流】
            1. **金手指必须是可视化的“系统面板”**。必须具备“数据化解析”、“任务发布”或“加点升级”功能。
            2. **力量体系必须数值化**。例如：战斗力、灵力值、熟练度。
            3. **世界观要有游戏感**。例如：杀怪掉宝、副本机制、排行榜。
            """
            
        elif "热血" in style:
            constraints = """
            【流派强约束：热血玄幻】
            1. **金手指必须是“成长型”或“老爷爷型”**。能让废柴主角快速逆袭。
            2. **力量体系必须强调“破坏力”**。等级森严，一级压死人。
            3. **核心冲突必须是“莫欺少年穷”**。主角开局必须被轻视、退婚或羞辱。
            """
            
        elif "诡秘" in style or "智斗" in style:
            constraints = """
            【流派强约束：诡秘智斗】
            1. **金手指必须有巨大的副作用/代价**。例如：使用力量会扣除理智、寿命或引来不可名状的注视。
            2. **力量体系必须基于“规则”或“扮演”**。而不是单纯的比谁拳头大。
            3. **世界观必须充满谜团**。神明是疯狂的，历史是断层的。
            """
            
        elif "苟道" in style or "稳健" in style:
            constraints = """
            【流派强约束：稳健苟道】
            1. **金手指必须是辅助生存型**。例如：危机预感、长生不老、属性隐藏、模拟未来。严禁给主角“嘲讽脸”系统。
            2. **主角性格必须是“被迫害妄想症”**。只有在绝对安全（碾压十个境界）时才出手。
            """
            
        elif "无敌" in style:
            constraints = """
            【流派强约束：无敌碾压】
            1. **主角开局即巅峰**。金手指不需要升级，而是“解封”或“满级账号”。
            2. **核心爽点是“扮猪吃虎”**。反派越嚣张，死得越快。
            """
            
        elif "末世" in style:
            constraints = """
            【流派强约束：末世废土】
            1. **金手指必须与“物资”或“生存”相关**。例如：无限空间、暴击掉落、避难所系统。
            2. **力量体系是次要的，资源才是核心**。世界观必须极其残酷，人吃人。
            """
            
        elif "权谋" in style or "历史" in style:
            constraints = """
            【流派强约束：历史权谋】
            1. **金手指不能太魔幻**。最好是“现代知识”、“图书馆”或“读心术”，严禁出现飞天遁地。
            2. **反派不是一个人，而是一个势力**。核心冲突是理念之争或利益分配。
            """
            
        elif "女频" in style:
            constraints = """
            【流派强约束：女频情感】
            1. **金手指服务于“魅力”或“关系”**。例如：万人迷光环、读心术、锦鲤运气。
            2. **反派通常是情敌、恶毒亲戚或主角的心魔**。
            3. **力量体系不重要**，重要的是情感链接和身份地位。
            """
            
        else:
            constraints = "【标准约束】设计一个逻辑自洽的网文世界，金手指要足够强力。"
            
        return constraints   
    def build_world(self, idea, total_chapters=100, style="男频-热血玄幻", book_id=None):
        prefix = f"[{book_id}] " if book_id else ""
        print(f"🌍 [WorldBuilder] {prefix}正在构建世界 | 脑洞: {idea} | 风格: {style}...")
        # 🟢 1. 获取流派专属约束 (核心逻辑)
        style_constraints = self._get_style_constraints(style)
        prompt = f"""
        用户想要写一本这样的小说：
        【核心脑洞】{idea}
        【预估篇幅】{total_chapters} 章
        【目标风格】{style}
        
        {style_constraints}
        
        请设计一个能够支撑起这个篇幅的宏大世界。不仅要设计骨架，更要填充血肉。
        
        【🚨 核心设计要求 (CRITICAL)】
        1. **金手指 (Gold Finger)**: 必须严格遵守【目标风格】的约束。详细设计它的机制、核心爽点以及**限制/代价**。
        2. **力量体系 (Power System)**: 必须定义表现形式（视觉/听觉）、晋升仪式（如何升级）和同级强弱判定标准。
        3. **分卷反派 (Volume Boss)**: 严禁让最终 BOSS 从头跳到尾。**每一卷必须有一个独立的“阶段性反派”**，他在本卷结束时必须被主角击败或解决。
        
        【BookPlan 规划要求】
        - **第一卷 (The Hook)**: 必须是“新手村/起源”篇章。目标是获得金手指，解决第一个生存危机。
        - **分卷节奏**: 请根据 {total_chapters} 章的总长度合理切分。如果是 100 章，建议分 3-4 卷。

        【返回格式要求】 (请严格遵守此JSON结构，不要包含Markdown标记)
        {{
            "book_title": "极具吸引力的书名",
            
            "gold_finger": {{
                "name": "金手指名称",
                "type": "SYSTEM / ITEM / MEMORY / BLOODLINE",
                "description": "一句话描述",
                "core_ability": "核心功能 (如: 加点, 抽奖, 模拟未来)",
                "limitations": "使用代价或冷却限制 (必须符合流派设定)",
                "upgrade_route": "简述金手指本身的进化方向"
            }},

            "hero": {{
                "name": "姓名",
                "identity": "开篇身份",
                "appearance": "外貌特征",
                "personality": "性格关键词",
                "core_desire": "核心欲望 (他最想要什么?)",
                "fear": "恐惧之物 (弱点)",
                "speech_style": "说话风格"
            }},
            
            "villain": {{
                "name": "全书最终 BOSS 姓名",
                "identity": "身份 (也就是本书的天花板)",
                "motivation": "最终目的",
                "relation_to_hero": "与主角的深层羁绊"
            }},

            "key_support_roles": [
                {{
                    "name": "配角A",
                    "role_type": "MENTOR / PARTNER / RIVAL",
                    "character_hook": "人物记忆点 (如: 贪财, 洁癖)",
                    "utility": "功能性作用"
                }}
            ],

            "intro": "世界观简介 (200字以内)",
            
            "power_system": {{
                "name": "体系名称",
                "levels": ["L1", "L2", "...", "L9"],
                "visual_effect": "力量释放时的视觉表现 (必须符合流派画风)",
                "promotion_method": "晋升方式",
                "price": "代价 (如果有)"
            }},

            "locations": ["新手村", "进阶地图", "核心地图"],

            "book_plan": {{
                "main_story": "全书主线梗概",
                "volumes": [
                    {{
                        "title": "第一卷：卷名",
                        "goal": "本卷剧情主线",
                        "estimated_chapters": 30,
                        "antagonist": {{  <-- 🟢 关键新增：本卷的关底 BOSS
                            "name": "本卷反派姓名",
                            "identity": "身份 (如: 恶霸, 外门长老)",
                            "outcome": "结局 (如: 被主角当众斩杀)"
                        }},
                        "key_events": ["金手指觉醒", "初次冲突", "高潮决战"]
                    }},
                    {{
                        "title": "第二卷：卷名",
                        "goal": "...",
                        "estimated_chapters": 40,
                        "antagonist": {{ "name": "...", "identity": "...", "outcome": "..." }},
                        "key_events": ["..."]
                    }}
                ]
            }}
        }}
        """
        
        
        # 调用 LLM
        response = self.call(prompt, json_mode=True)
        
        # 🟢 增强版 JSON 清洗 (复用 PlannerAgent 的逻辑)
        try:
            # 1. 如果已经是字典，直接返回
            if isinstance(response, dict):
                return response
                
            # 2. 如果是字符串，尝试清洗 Markdown
            if isinstance(response, str):
                clean_json = re.sub(r'^```json\s*|```$', '', response.strip(), flags=re.MULTILINE)
                # 尝试提取花括号内容
                match = re.search(r'\{[\s\S]*\}', clean_json)
                if match:
                    return json.loads(match.group(0))
                else:
                    # 兜底：直接 parse 清洗后的字符串
                    return json.loads(clean_json)
                    
        except Exception as e:
            print(f"❌ JSON 解析失败: {e}")
            return {}
            
        return {}