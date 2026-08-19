import os
import json
import uuid
from neo4j import GraphDatabase
from app.core.config import settings
from app.core.logger import logger

# 加载 .env 里的配置
# 加载 .env 里的配置 (已由 config.py 处理)
# load_dotenv()

class DatabaseManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DatabaseManager, cls).__new__(cls)
            cls._instance._init_driver()
        return cls._instance

    def _init_driver(self):
        uri = settings.NEO4J_URI
        user = settings.NEO4J_USERNAME
        password = settings.NEO4J_PASSWORD
        
        try:
            self.driver = GraphDatabase.driver(uri, auth=(user, password))
            self.driver.verify_connectivity()
            logger.info("✅ Neo4j 连接成功！")
        except Exception as e:
            logger.error(f"❌ Neo4j 连接失败: {e}")
            raise e

    def close(self):
        if self.driver:
            self.driver.close()

    def query(self, cypher_query, parameters=None):
        """执行 Cypher 查询语句"""
        with self.driver.session() as session:
            result = session.run(cypher_query, parameters)
            return [record.data() for record in result]

    # ==============================================================================
    # 📚 书籍管理 (基础)
    # ==============================================================================
    
    def create_book(self, title, user_id: str = None, style: str = None):
        """创建一个新的书籍根节点"""
        book_id = str(uuid.uuid4())
        with self.driver.session() as session:
            session.run("""
                CREATE (b:Book {
                    book_id: $bid, 
                    title: $title, 
                    created_at: datetime(),
                    user_id: $user_id,
                    style: $style
                })
                RETURN b.book_id
            """, bid=book_id, title=title, user_id=user_id or "", style=style or "")
        return book_id

    def get_all_books(self, user_id: str = None):
        """获取书架列表"""
        if user_id:
            return self.query("""
                MATCH (b:Book) 
                WHERE b.user_id = $uid OR $uid IS NULL OR $uid = ''
                RETURN b.book_id, b.title, b.created_at 
                ORDER BY b.created_at DESC
            """, parameters={'uid': user_id})
        return self.query("""
            MATCH (b:Book) 
            RETURN b.book_id, b.title, b.created_at 
            ORDER BY b.created_at DESC
        """)
    # ==============================================================================
    # 🗑️ 删除书籍 (级联删除所有关联数据)
    # ==============================================================================
    def delete_book(self, book_id):
        """
        删除书籍及其所有关联节点（新增 Location 支持）
        """
        with self.driver.session() as session:
            session.run("""
                MATCH (b:Book {book_id: $bid})
                
                OPTIONAL MATCH (b)-[:HAS_CONFIG]->(wc)
                OPTIONAL MATCH (b)-[:HAS_PLAN]->(bp)
                OPTIONAL MATCH (b)-[:OWN_CHAPTER]->(ch)
                OPTIONAL MATCH (b)-[:EXIST_IN]->(char)
                OPTIONAL MATCH (char)-[:HAS_ABILITY]->(gf:GoldFinger)
                OPTIONAL MATCH (char)-[:POSSESSES]->(p_item:Item)
                OPTIONAL MATCH (b)-[:HAS_ITEM]->(b_item:Item)
                
                // 🟢 新增：删除地点节点
                OPTIONAL MATCH (b)-[:HAS_LOCATION]->(loc:Location)

                // 毁灭打击
                DETACH DELETE b, wc, bp, ch, char, gf, p_item, b_item, loc
            """, bid=book_id)
            logger.info(f"🗑️ 书籍 [{book_id}] 及其所有数据已销毁。")
    # ==============================================================================
    # 🌍 核心修改：世界初始化 (适配新版 WorldBuilder)
    # ==============================================================================

    def init_book_world(self, book_id, world_data):
        """
        [优化版] 根据 WorldBuilder 生成的 JSON 初始化世界观（事务化）
        """
        with self.driver.session() as session:
            # 使用事务保证原子性
            tx = session.begin_transaction()
            try:
                # 1. 检查书籍是否存在
                result = tx.run("MATCH (b:Book {book_id: $bid}) RETURN b", bid=book_id)
                if not result.single():
                    logger.warning(f"❌ 书籍 {book_id} 不存在")
                    tx.rollback()
                    return

                ai_book_title = world_data.get('book_title')
                intro = world_data.get('intro', '无简介')
                power_system_data = world_data.get('power_system', {})
                power_system_str = json.dumps(power_system_data, ensure_ascii=False)
                
                book_plan_data = world_data.get('book_plan', {})
                main_story = book_plan_data.get('main_story', '未设定')
                volumes_str = json.dumps(book_plan_data.get('volumes', []), ensure_ascii=False)

                if ai_book_title:
                    tx.run("""
                        MATCH (b:Book {book_id: $bid})
                        SET b.title = $new_title, b.updated_at = datetime()
                    """, bid=book_id, new_title=ai_book_title)

                tx.run("""
                    MATCH (b:Book {book_id: $bid})
                    CREATE (w:WorldConfig {
                        intro: $intro,
                        power_system: $power_sys,
                        power_name: $power_name
                    })
                    MERGE (b)-[:HAS_CONFIG]->(w)
                    CREATE (bp:BookPlan {
                        main_story: $main_story,
                        volumes: $volumes,
                        current_volume: 1
                    })
                    MERGE (b)-[:HAS_PLAN]->(bp)
                """, 
                    bid=book_id, intro=intro, power_sys=power_system_str,
                    power_name=power_system_data.get('name', '未知体系'),
                    main_story=main_story, volumes=volumes_str
                )

                locations = world_data.get('locations', [])
                if locations:
                    tx.run("""
                        MATCH (b:Book {book_id: $bid})
                        UNWIND $locs AS loc_name
                        MERGE (l:Location {book_id: $bid, name: loc_name})
                        MERGE (b)-[:HAS_LOCATION]->(l)
                    """, bid=book_id, locs=locations)

                hero = world_data.get('hero', {})
                tx.run("""
                    MATCH (b:Book {book_id: $bid})
                    CREATE (n:Character {
                        name: $name, identity: $identity,
                        appearance: $appearance, personality: $personality,
                        core_desire: $desire, fear: $fear,
                        speech_style: $speech, is_hero: true,
                        mental_state: '初始状态', created_at: datetime()
                    })
                    MERGE (b)-[:EXIST_IN]->(n)
                """, 
                    bid=book_id, name=hero.get('name', '主角'), 
                    identity=hero.get('identity', '普通人'),
                    appearance=hero.get('appearance', '外貌平凡'),
                    personality=hero.get('personality', '坚韧'),
                    desire=hero.get('core_desire', ''),
                    fear=hero.get('fear', ''),
                    speech=hero.get('speech_style', '')
                )

                gf = world_data.get('gold_finger', {})
                if gf:
                    tx.run("""
                        MATCH (b:Book {book_id: $bid})-[:EXIST_IN]->(h:Character {is_hero: true})
                        CREATE (g:GoldFinger {
                            name: $name, type: $type, description: $desc,
                            core_ability: $ability, limitations: $limit,
                            upgrade_route: $route
                        })
                        MERGE (h)-[:HAS_ABILITY]->(g)
                    """, 
                        bid=book_id, name=gf.get('name', '未知外挂'),
                        type=gf.get('type', 'SYSTEM'), desc=gf.get('description', ''),
                        ability=gf.get('core_ability', ''), limit=gf.get('limitations', ''),
                        route=gf.get('upgrade_route', '')
                    )

                villain = world_data.get('villain', {})
                tx.run("""
                    MATCH (b:Book {book_id: $bid})
                    CREATE (n:Character {
                        name: $name, identity: $identity,
                        motivation: $motivation, relation_to_hero: $rel,
                        is_villain: true, mental_state: '潜伏', created_at: datetime()
                    })
                    MERGE (b)-[:EXIST_IN]->(n)
                """, 
                    bid=book_id, name=villain.get('name', '最终BOSS'), 
                    identity=villain.get('identity', '未知'),
                    motivation=villain.get('motivation', ''),
                    rel=villain.get('relation_to_hero', '')
                )
                
                support_roles = world_data.get('key_support_roles', [])
                for role in support_roles:
                    tx.run("""
                        MATCH (b:Book {book_id: $bid})
                        CREATE (n:Character {
                            name: $name, identity: $role_type,
                            character_hook: $hook, utility: $utility,
                            is_core: true, created_at: datetime()
                        })
                        MERGE (b)-[:EXIST_IN]->(n)
                    """,
                        bid=book_id, name=role.get('name'),
                        role_type=role.get('role_type'),
                        hook=role.get('character_hook'),
                        utility=role.get('utility', '')
                    )
                
                tx.commit()
                print(f"✅ 书籍 [{book_id}] 初始化完成 (包含地点与完整人设)。")
            except Exception as e:
                tx.rollback()
                logger.error(f"❌ 书籍 [{book_id}] 初始化失败，事务已回滚: {e}")
                raise

    def update_world_config(self, book_id, intro, power_system):
        """
        更新世界观配置 (仅更新文本)
        """
        with self.driver.session() as session:
            session.run("""
                MATCH (b:Book {book_id: $bid})-[:HAS_CONFIG]->(w:WorldConfig)
                SET w.intro = $intro,
                    w.power_system = $power_system
            """, bid=book_id, intro=intro, power_system=power_system)
            logger.info(f"✅ 书籍 [{book_id}] 世界观配置已更新。")
    # ==============================================================================
    # 🔍 核心查询：为 Writer/Planner 提供完整上下文
    # ==============================================================================

    def get_world_config(self, book_id):
        """
        🟢 核心修复：确保 volumes 被解析为列表，而不是字符串
        """
        with self.driver.session() as session:
            # ... (前面的查询语句 Query 保持不变) ...
            result = session.run("""
                MATCH (b:Book {book_id: $bid})
                OPTIONAL MATCH (b)-[:HAS_CONFIG]->(w:WorldConfig)
                OPTIONAL MATCH (b)-[:EXIST_IN]->(h:Character {is_hero: true})
                OPTIONAL MATCH (h)-[:HAS_ABILITY]->(gf:GoldFinger)
                OPTIONAL MATCH (b)-[:EXIST_IN]->(v:Character {is_villain: true})
                OPTIONAL MATCH (b)-[:HAS_PLAN]->(bp:BookPlan)
                OPTIONAL MATCH (b)-[:HAS_LOCATION]->(l:Location)
                
                RETURN 
                    w.intro as intro, 
                    w.power_system as power_system,
                    h as hero_node,
                    gf as gold_finger_node,
                    v as villain_node,
                    bp.volumes as volumes,    
                    collect(l.name) as location_names
            """, bid=book_id)
            
            record = result.single()
            if not record: return {}

            # ==================================================
            # 🟢 关键修复点：手动解析 volumes 字符串
            # ==================================================
            volumes_data = []
            raw_volumes = record["volumes"]
            if raw_volumes and isinstance(raw_volumes, str):
                try:
                    import json
                    volumes_data = json.loads(raw_volumes)
                except json.JSONDecodeError as e:
                    logger.warning(f"[DB] volumes JSON 解析失败 (book_id={book_id}): {e}")
                    volumes_data = []
            
            # 拼装 Config
            config = {
                "intro": record["intro"] or "",
                "power_system": record["power_system"] or "{}", 
                "locations": record["location_names"] or [],
                "book_plan": {
                    # 现在这里是真正的列表了，Writer 遍历它不会报错
                    "volumes": volumes_data 
                }
            }
            
            # ... (后续 hero/villain 处理保持不变) ...
            if record["hero_node"]: config["hero"] = dict(record["hero_node"])
            if record["gold_finger_node"]: config["gold_finger"] = dict(record["gold_finger_node"])
            if record["villain_node"]: config["villain"] = dict(record["villain_node"])
                
            return config

    def get_book_plan(self, book_id):
        """获取指定书的大纲"""
        with self.driver.session() as session:
            result = session.run("""
                MATCH (b:Book {book_id: $bid})-[:HAS_PLAN]->(bp:BookPlan)
                RETURN bp.main_story, bp.volumes, bp.current_volume
            """, bid=book_id)
            record = result.single()
            if record:
                # 注意：volumes 存的是字符串，需要 Writer/Planner 自己 loads，
                # 或者在这里 load 好。为了方便 Planner，这里直接 load。
                try:
                    volumes_list = json.loads(record["bp.volumes"])
                except json.JSONDecodeError as e:
                    logger.warning(f"[DB] book_plan volumes JSON 解析失败 (book_id={book_id}): {e}")
                    volumes_list = []
                    
                return {
                    "main_story": record["bp.main_story"],
                    "volumes": volumes_list,
                    "current_volume": record["bp.current_volume"]
                }
            return None

    def get_book(self, book_id):
        """获取书籍基本信息"""
        with self.driver.session() as session:
            result = session.run("""
                MATCH (b:Book {book_id: $bid})
                RETURN b.book_id as book_id, b.title as title, b.style as style, b.created_at as created_at
            """, bid=book_id)
            record = result.single()
            if record:
                return {
                    "book_id": record["book_id"],
                    "title": record["title"],
                    "style": record.get("style", ""),
                    "created_at": str(record.get("created_at", ""))
                }
            return None

    def update_book_style(self, book_id, style):
        """更新书籍风格"""
        with self.driver.session() as session:
            session.run("""
                MATCH (b:Book {book_id: $bid})
                SET b.style = $style
            """, bid=book_id, style=style)

    # ==============================================================================
    # ⚙️ 系统配置
    # ==============================================================================
    
    def get_system_config(self, key: str):
        """获取系统配置"""
        with self.driver.session() as session:
            result = session.run("""
                MATCH (s:SystemConfig {key: $key})
                RETURN s.value as value
            """, key=key)
            record = result.single()
            return record["value"] if record else None
    
    def set_system_config(self, key: str, value: str):
        """设置系统配置"""
        with self.driver.session() as session:
            session.run("""
                MERGE (s:SystemConfig {key: $key})
                SET s.value = $value, s.updated_at = datetime()
            """, key=key, value=value)

    # ==============================================================================
    # 📝 章节管理
    # ==============================================================================

    def save_chapter(self, book_id, chapter_num, title, content, summary):
        """保存章节"""
        with self.driver.session() as session:
            session.run("""
                MATCH (b:Book {book_id: $bid})
                MERGE (c:Chapter {book_id: $bid, chapter_num: $num})
                ON CREATE SET c.created_at = datetime()
                SET c.title = $title,
                    c.content = $content,
                    c.summary = $summary,
                    c.updated_at = datetime()
                MERGE (b)-[:OWN_CHAPTER]->(c)
            """, bid=book_id, num=chapter_num, title=title, content=content, summary=summary)
            
            # 建立链表
            if chapter_num > 1:
                prev = chapter_num - 1
                session.run("""
                    MATCH (prev:Chapter {book_id: $bid, chapter_num: $prev})
                    MATCH (curr:Chapter {book_id: $bid, chapter_num: $curr})
                    MERGE (prev)-[:NEXT]->(curr)
                """, bid=book_id, prev=prev, curr=chapter_num)
            logger.info(f"✅ 书[{book_id}] 第{chapter_num}章归档完成。")

    def get_next_chapter_num(self, book_id):
        try:
            res = self.query("""
                MATCH (b:Book {book_id: $bid})-[:OWN_CHAPTER]->(c:Chapter)
                RETURN coalesce(max(c.chapter_num), 0) + 1 as next_num
            """, parameters={'bid': book_id})
            return res[0]['next_num'] if res else 1
        except Exception as e:
            return 1

    def get_prev_chapter_summary(self, book_id, current_chap_num):
        if current_chap_num <= 1:
            return "无（这是第一章）"
        with self.driver.session() as session:
            result = session.run("""
                MATCH (b:Book {book_id: $bid})-[:OWN_CHAPTER]->(c:Chapter {chapter_num: $num})
                RETURN c.summary
            """, bid=book_id, num=current_chap_num - 1)
            record = result.single()
            return record["c.summary"] if record else "无上一章存档"

    def get_volume_context(self, book_id, current_chap_num, count=5):
        """
        卷衔接增强：获取当前章节之前的最近 N 章摘要
        当 chapter_num 处于卷首（local_chap == 1）时，注入前卷最后 N 章摘要
        而非仅依赖上一章，确保跨卷叙事连续性
        返回: "第X章摘要 | 第Y章摘要 | ..."
        """
        if current_chap_num <= 1:
            return "无（这是第一章）"
        
        start_chap = max(1, current_chap_num - count)
        with self.driver.session() as session:
            result = session.run("""
                MATCH (b:Book {book_id: $bid})-[:OWN_CHAPTER]->(c:Chapter)
                WHERE c.chapter_num >= $start AND c.chapter_num < $current
                RETURN c.chapter_num as num, c.summary as summary
                ORDER BY c.chapter_num ASC
            """, bid=book_id, start=start_chap, current=current_chap_num)
            records = list(result)
            if not records:
                return "无上一章存档"
            
            parts = []
            for r in records:
                num = r["num"]
                summary = r["summary"] or ""
                parts.append(f"第{num}章: {summary}")
            return "\n".join(parts)

    def get_ui_main_characters(self, book_id):
        """
        获取主角和反派的基础信息 (用于侧边栏显示)
        返回: List[Dict]
        """
        with self.driver.session() as session:
            result = session.run("""
                MATCH (b:Book {book_id: $bid})-[:EXIST_IN]->(n:Character) 
                WHERE n.is_hero = true OR n.is_villain = true 
                RETURN n.name, n.identity, n.is_hero, n.is_villain
                ORDER BY n.is_hero DESC // 让主角排前面
            """, bid=book_id)
            
            return [
                {
                    "name": r["n.name"], 
                    "identity": r["n.identity"], 
                    "role": "主角" if r["n.is_hero"] else "反派"
                } 
                for r in result
            ]

    def get_ui_support_characters(self, book_id):
        """
        获取核心配角的基础信息 (用于侧边栏显示)
        返回: List[Dict]
        """
        with self.driver.session() as session:
            result = session.run("""
                MATCH (b:Book {book_id: $bid})-[:EXIST_IN]->(n:Character) 
                WHERE n.is_core = true 
                RETURN n.name, n.identity
            """, bid=book_id)
            
            return [
                {
                    "name": r["n.name"], 
                    "identity": r["n.identity"]
                } 
                for r in result
            ]

    def get_hero_full_status(self, book_id):
        """
        获取主角的【完整结构化】状态信息 (用于侧边栏 JSON/Metric 显示)
        注意：get_hero_state 返回的是字符串(给AI看的)，这个返回的是字典(给UI看的)
        """
        with self.driver.session() as session:
            result = session.run("""
                MATCH (b:Book {book_id: $bid})-[:EXIST_IN]->(n:Character {is_hero: true})
                // 同时也把金手指查出来
                OPTIONAL MATCH (n)-[:HAS_ABILITY]->(gf:GoldFinger)
                RETURN n, gf
                LIMIT 1
            """, bid=book_id)
            
            record = result.single()
            if record:
                hero_data = dict(record['n']) # 转为 Python 字典
                
                # 如果有金手指，也塞进去
                if record['gf']:
                    gf_data = dict(record['gf'])
                    hero_data['gold_finger'] = gf_data
                
                return hero_data
            return None
    # ==============================================================================
    # 👥 角色状态与上下文
    # ==============================================================================

    def get_hero_state(self, book_id):
        """获取主角状态 (含金手指)"""
        with self.driver.session() as session:
            result = session.run("""
                MATCH (b:Book {book_id: $bid})-[:EXIST_IN]->(n:Character {is_hero: true})
                OPTIONAL MATCH (n)-[:HAS_ABILITY]->(gf:GoldFinger)
                OPTIONAL MATCH (n)-[:POSSESSES]->(i:Item)
                RETURN n, gf, collect(i.name) as items
            """, bid=book_id)
            
            data = result.single()
            if not data: return "（未检测到主角数据）"
            
            hero = data['n']
            gf = data['gf']
            items = ", ".join([x for x in data['items'] if x]) or "无"
            
            gf_desc = f"【金手指: {gf['name']}】({gf['core_ability']})" if gf else "无金手指"
            
            return f"""
            姓名: {hero['name']} ({hero['identity']})
            性格: {hero.get('personality', '未知')}
            当前状态: {hero.get('mental_state', '正常')}
            {gf_desc}
            🎒 物品: {items}
            """

    def get_active_npcs(self, book_id):
        """获取反派和配角"""
        with self.driver.session() as session:
            result = session.run("""
                MATCH (b:Book {book_id: $bid})-[:EXIST_IN]->(n:Character) 
                WHERE (n.is_villain = true OR n.is_core = true)
                RETURN n.name, n.identity, n.is_villain, n.mental_state
                LIMIT 5
            """, bid=book_id)
            
            lines = []
            for r in result:
                role = "😈 [反派]" if r['n.is_villain'] else "🛡️ [配角]"
                lines.append(f"{role} {r['n.name']} ({r['n.identity']})")
            return "\n".join(lines) if lines else "无活跃NPC"

    # 允许安全更新的字段白名单
    _SAFE_UPDATE_FIELDS = {"current_volume", "main_story"}

    def update_book_plan_field(self, book_id, field_name, new_value):
        """更新大纲字段 (如 current_volume) - 带字段白名单防注入"""
        if field_name not in self._SAFE_UPDATE_FIELDS:
            raise ValueError(f"不允许更新字段: {field_name}，仅允许: {self._SAFE_UPDATE_FIELDS}")
        with self.driver.session() as session:
            session.run(f"""
                MATCH (b:Book {{book_id: $bid}})-[:HAS_PLAN]->(bp:BookPlan)
                SET bp.{field_name} = $val
            """, bid=book_id, val=new_value)

    def get_all_characters_dict(self, book_id):
        """获取所有角色的字典形式，用于 Maintainer 分析"""
        with self.driver.session() as session:
            result = session.run("""
                MATCH (b:Book {book_id: $bid})-[:EXIST_IN]->(c:Character)
                RETURN c.name as name, c.mental_state as mental_state, c.identity as identity
            """, bid=book_id)
            return {r["name"]: {"mental_state": r["mental_state"], "identity": r["identity"]} for r in result}

    def update_character_state(self, book_id, char_name, mental_state, tags):
        """更新角色状态和标签"""
        with self.driver.session() as session:
            session.run("""
                MATCH (b:Book {book_id: $bid})-[:EXIST_IN]->(c:Character {name: $name})
                SET c.mental_state = $mental_state, c.tags = $tags, c.updated_at = datetime()
            """, bid=book_id, name=char_name, mental_state=mental_state, tags=tags)

    def add_new_entity(self, book_id, entity):
        """添加新实体 (角色或物品)"""
        with self.driver.session() as session:
            if entity.get("type") == "Character":
                session.run("""
                    MATCH (b:Book {book_id: $bid})
                    MERGE (c:Character {name: $name, book_id: $bid})
                    ON CREATE SET 
                        c.identity = $desc, 
                        c.created_at = datetime(),
                        c.is_core = false
                    MERGE (b)-[:EXIST_IN]->(c)
                """, bid=book_id, name=entity.get("name"), desc=entity.get("desc", ""))
            elif entity.get("type") == "Item":
                session.run("""
                    MATCH (b:Book {book_id: $bid})
                    MERGE (i:Item {name: $name, book_id: $bid})
                    ON CREATE SET 
                        i.description = $desc, 
                        i.importance = $importance,
                        i.created_at = datetime()
                    MERGE (b)-[:HAS_ITEM]->(i)
                    WITH i, b
                    MATCH (b)-[:EXIST_IN]->(c:Character {name: $owner})
                    MERGE (c)-[:POSSESSES]->(i)
                """, bid=book_id, name=entity.get("name"), desc=entity.get("desc", ""),
                     importance=entity.get("importance", 1), owner=entity.get("owner", "主角"))

    # =======================
    # User 管理（认证系统）
    # =======================

    def create_user(self, user_id: str, username: str, email: str, password_hash: str, salt: str) -> bool:
        """创建用户节点，返回是否成功（用户名唯一时返回 True，已存在返回 False）"""
        with self.driver.session() as session:
            existing = session.run(
                "MATCH (u:User {username: $username}) RETURN u.user_id AS uid",
                username=username,
            ).single()
            if existing:
                return False
            session.run(
                """
                CREATE (u:User {
                    user_id: $user_id,
                    username: $username,
                    email: $email,
                    password_hash: $password_hash,
                    salt: $salt,
                    created_at: datetime()
                })
                """,
                user_id=user_id,
                username=username,
                email=email,
                password_hash=password_hash,
                salt=salt,
            )
            return True

    def get_user_by_username(self, username: str) -> dict | None:
        """按用户名查询用户，返回 dict 或 None"""
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (u:User {username: $username})
                RETURN u.user_id AS user_id,
                       u.username AS username,
                       u.email AS email,
                       u.password_hash AS password_hash,
                       u.salt AS salt
                """,
                username=username,
            ).single()
            if not result:
                return None
            return {
                "user_id": result["user_id"],
                "username": result["username"],
                "email": result["email"],
                "password_hash": result["password_hash"],
                "salt": result["salt"],
            }

    def get_user_by_id(self, user_id: str) -> dict | None:
        """按 user_id 查询用户，返回 dict 或 None"""
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (u:User {user_id: $user_id})
                RETURN u.user_id AS user_id,
                       u.username AS username,
                       u.email AS email
                """,
                user_id=user_id,
            ).single()
            if not result:
                return None
            return {
                "user_id": result["user_id"],
                "username": result["username"],
                "email": result["email"],
            }

    # ==============================================================================
    # 🎙️ 创作访谈 (Creative Interview)
    # ==============================================================================

    def create_interview_session(self, session_id, user_id, raw_idea, style):
        """创建访谈会话节点"""
        with self.driver.session() as session:
            session.run("""
                CREATE (s:InterviewSession {
                    session_id: $sid,
                    user_id: $user_id,
                    raw_idea: $raw_idea,
                    style: $style,
                    status: 'active',
                    started_at: datetime(),
                    collected_constraints: '{}',
                    question_history: '[]',
                    current_topic: ''
                })
            """, sid=session_id, user_id=user_id or "", raw_idea=raw_idea, style=style)

    def get_interview_session(self, session_id):
        """获取访谈会话状态（JSON 字段自动解析）"""
        result = self.query("""
            MATCH (s:InterviewSession {session_id: $sid})
            RETURN s
        """, parameters={'sid': session_id})
        if not result:
            return None
        s = result[0]['s']
        return {
            "session_id": s.get('session_id'),
            "user_id": s.get('user_id', ''),
            "raw_idea": s.get('raw_idea', ''),
            "style": s.get('style', ''),
            "status": s.get('status', 'active'),
            "current_topic": s.get('current_topic', ''),
            "collected_constraints": json.loads(s.get('collected_constraints', '{}') or '{}'),
            "question_history": json.loads(s.get('question_history', '[]') or '[]'),
        }

    def update_interview_session(self, session_id, status=None, current_topic=None,
                                 collected_constraints=None, question_history=None):
        """更新访谈会话字段（传 None 的字段不更新）"""
        sets = []
        params = {'sid': session_id}
        if status is not None:
            sets.append("s.status = $status")
            params['status'] = status
        if current_topic is not None:
            sets.append("s.current_topic = $topic")
            params['topic'] = current_topic
        if collected_constraints is not None:
            sets.append("s.collected_constraints = $constraints")
            params['constraints'] = json.dumps(collected_constraints, ensure_ascii=False)
        if question_history is not None:
            sets.append("s.question_history = $history")
            params['history'] = json.dumps(question_history, ensure_ascii=False)
        if not sets:
            return
        cypher = f"MATCH (s:InterviewSession {{session_id: $sid}}) SET {', '.join(sets)}"
        with self.driver.session() as session:
            session.run(cypher, **params)

    # ==============================================================================
    # 🎴 多方案竞争 (Bible Variants)
    # ==============================================================================

    def save_bible_variants(self, session_id, variants):
        """把多方案竞争结果挂到访谈会话下（:BibleVariant 节点）"""
        with self.driver.session() as session:
            # 先清空旧的 variants，避免重复
            session.run("""
                MATCH (s:InterviewSession {session_id: $sid})-[:HAS_VARIANT]->(v:BibleVariant)
                DETACH DELETE v
            """, sid=session_id)
            for v in variants:
                session.run("""
                    MATCH (s:InterviewSession {session_id: $sid})
                    CREATE (v:BibleVariant {
                        session_id: $sid,
                        label: $label,
                        seed: $seed,
                        core_setting: $core_setting,
                        strengths: $strengths,
                        risks: $risks,
                        user_decision: 'pending'
                    })
                    MERGE (s)-[:HAS_VARIANT]->(v)
                """, sid=session_id, label=v.get('label', ''),
                     seed=v.get('seed', ''),
                     core_setting=json.dumps(v.get('core_setting', {}), ensure_ascii=False),
                     strengths=json.dumps(v.get('strengths', []), ensure_ascii=False),
                     risks=json.dumps(v.get('risks', []), ensure_ascii=False))

    def get_bible_variants(self, session_id):
        """获取会话下的所有方案"""
        result = self.query("""
            MATCH (s:InterviewSession {session_id: $sid})-[:HAS_VARIANT]->(v:BibleVariant)
            RETURN v ORDER BY v.label
        """, parameters={'sid': session_id})
        variants = []
        for r in result:
            v = r['v']
            variants.append({
                "label": v.get('label', ''),
                "seed": v.get('seed', ''),
                "core_setting": json.loads(v.get('core_setting', '{}') or '{}'),
                "strengths": json.loads(v.get('strengths', '[]') or '[]'),
                "risks": json.loads(v.get('risks', '[]') or '[]'),
                "user_decision": v.get('user_decision', 'pending'),
            })
        return variants

    def set_variant_decision(self, session_id, label, decision):
        """记录用户对某方案的决策（chosen/rejected/merged）"""
        with self.driver.session() as session:
            session.run("""
                MATCH (s:InterviewSession {session_id: $sid})-[:HAS_VARIANT]->(v:BibleVariant {label: $label})
                SET v.user_decision = $decision
            """, sid=session_id, label=label, decision=decision)

    def mark_interview_completed_with_book(self, session_id, book_id):
        """访谈完成后关联到书籍（可选）"""
        with self.driver.session() as session:
            session.run("""
                MATCH (s:InterviewSession {session_id: $sid})
                MATCH (b:Book {book_id: $bid})
                MERGE (s)-[:RESULTED_IN]->(b)
            """, sid=session_id, bid=book_id)

    def save_interview_bible_draft(self, session_id, bible_draft):
        """保存访谈生成的 Bible 草稿（decide 后、confirm 前）"""
        with self.driver.session() as session:
            session.run("""
                MATCH (s:InterviewSession {session_id: $sid})
                SET s.bible_draft = $draft,
                    s.bible_draft_at = datetime()
            """, sid=session_id, draft=json.dumps(bible_draft, ensure_ascii=False))

    def get_interview_bible_draft(self, session_id):
        """获取访谈生成的 Bible 草稿"""
        result = self.query("""
            MATCH (s:InterviewSession {session_id: $sid})
            RETURN s.bible_draft AS draft
        """, parameters={'sid': session_id})
        if not result or not result[0].get('draft'):
            return None
        return json.loads(result[0]['draft'])

# 创建全局实例
db = DatabaseManager()

