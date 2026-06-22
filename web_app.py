import streamlit as st
import json
import re
import uuid
import time
from app.client import client
from app.core.logger import logger

# ==========================================
# 1. 页面配置与样式
# ==========================================
st.set_page_config(
    page_title="EpicWriter OS - 多重宇宙版",
    page_icon="🐉",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .stTextArea textarea {
        background-color: #0e1117;
        color: #00ff41; 
        font-family: 'Courier New';
    }
    .stProgress > div > div > div > div {
        background-color: #00ff41;
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 🆕 新增：主入口函数 (路由逻辑)
# ==========================================
def main():
    # 检查 Session 中是否已选书
    current_book_id = st.session_state.get('current_book_id')

    if not current_book_id:
        # A. 没选书 -> 显示书架
        render_bookshelf()
    else:
        # B. 选了书 -> 显示编辑器 (传入 book_id)
        render_editor(current_book_id)

# ==========================================
# 🆕 新增：书架界面 (Bookshelf) - 适配风格流派版
# ==========================================
def render_bookshelf():
    st.title("🌌 EpicWriter 多重宇宙书架")
    
    # 定义所有支持的流派 (必须与 Agent 里的 Key 一致)
    STYLE_OPTIONS = [
        "男频-热血玄幻",
        "男频-系统数据",
        "男频-诡秘智斗",
        "男频-稳健苟道",
        "男频-无敌碾压",
        "男频-末世废土",
        "男频-历史权谋",
        "女频-古言权谋",
        "女频-现言救赎"
    ]
    
    # 使用 Tabs 分离两种创建模式
    tab_manual, tab_ai = st.tabs(["📝 手动建档 (已有书名)", "🧠 AI 创世纪 (只有脑洞)"])
    
    # ----------------------------------------------------------------
    # 模式 A: 手动建档 (Old Way)
    # ----------------------------------------------------------------
    with tab_manual:
        with st.form("new_book_form"):
            col1, col2 = st.columns([3, 1])
            with col1:
                new_title = st.text_input("书名", placeholder="例如：赛博修仙传")
            with col2:
                submit = st.form_submit_button("立即创建")
            
            if submit and new_title:
                new_id = client.create_book(new_title)
                
                # API 内部会自动初始化默认世界观
                
                st.session_state['current_book_id'] = new_id
                # 🟢 手动模式默认给个热血玄幻，进去后可以改
                st.session_state['novel_style'] = "男频-热血玄幻" 
                
                st.success(f"《{new_title}》创建成功！")
                time.sleep(0.5)
                st.rerun()

    # ----------------------------------------------------------------
    # 模式 B: AI 创世纪 (New Way) - 核心修改区域
    # ----------------------------------------------------------------
    with tab_ai:
        st.caption("不知道起什么名字？没关系。输入你的脑洞，AI 将为你构建世界观、规划分卷，并自动生成书名。")
        
        idea = st.text_area("你的核心脑洞/梗概", height=100, placeholder="例如：全球数据化，所有人都要打怪升级...")
        
        col_style, col_len = st.columns([2, 1])
        
        with col_style:
            # 🟢 新增：风格选择器
            selected_style = st.selectbox(
                "📚 选择小说流派",
                options=STYLE_OPTIONS,
                index=1, # 默认选系统数据流
                help="决定世界观设定、金手指类型以及文风基调"
            )
            
        with col_len:
            est_chapters = st.number_input("预估篇幅 (章)", min_value=20, max_value=2000, value=100, step=20)
        
        st.write("") # 占位
        start_genesis = st.button("🚀 启动创世纪引擎", type="primary", use_container_width=True)

        if start_genesis:
            if not idea:
                st.error("请输入一点点脑洞，不然 AI 没法发挥！")
            else:
                status = st.status(f"🔮 正在推演 [{selected_style}] 宇宙...", expanded=True)
                try:
                    status.write("正在构建世界观、金手指与反派...")
                    
                    # 🟢 调用 API 创世纪
                    resp_data = client.genesis_book(
                        idea, 
                        est_chapters, 
                        style=selected_style
                    )
                    
                    if resp_data and resp_data.get('book_id'):
                        auto_title = resp_data.get('title')
                        new_id = resp_data.get('book_id')
                        
                        # 6. 保存风格偏好到 Session
                        st.session_state['novel_style'] = selected_style
                        
                        status.update(label="✅ 世界构建完成！", state="complete")
                        
                        # 7. 自动进入
                        st.session_state['current_book_id'] = new_id
                        time.sleep(1)
                        st.rerun()
                    else:
                        status.update(label="❌ 生成失败，API 返回异常", state="error")
                except Exception as e:
                    status.update(label="❌ 发生错误", state="error")
                    st.error(str(e))

    st.divider()
    st.subheader("📚 我的藏书")

    # --- 书籍列表区域 ---
    try:
        books = client.get_all_books()
    except Exception:
        books = []

    if not books:
        st.info("书架空空如也，请创建第一本书。")
    else:
        # 网格布局显示书籍
        cols = st.columns(3)
        for i, book in enumerate(books):
            with cols[i % 3]:
                with st.container(border=True):
                    # 标题和ID
                    st.markdown(f"### 📖 {book['title']}")
                    st.caption(f"ID: {book['book_id'][:8]}...")
                    
                    # 使用两列布局：左边是进入，右边是删除
                    btn_col1, btn_col2 = st.columns([2, 1])
                    
                    with btn_col1:
                        # 🟢 进入按钮
                        if st.button("进入创作", key=f"enter_{book['book_id']}", use_container_width=True):
                            st.session_state['current_book_id'] = book['book_id']
                            # 尝试获取该书的风格，如果没有则给默认
                            st.session_state['novel_style'] = "男频-热血玄幻" 
                            st.rerun()
                    
                    with btn_col2:
                        # 🔴 删除按钮 (使用 Popover 做二次确认)
                        # Popover 会显示一个小按钮，点击后弹出一个气泡框
                        with st.popover("🗑️", help="删除本书"):
                            st.warning(f"确定要彻底删除《{book['title']}》吗？")
                            st.caption("⚠️ 此操作不可逆，所有章节、设定将永久消失。")
                            
                            if st.button("确认删除", key=f"del_confirm_{book['book_id']}", type="primary"):
                                # 1. 执行数据库删除
                                client.delete_book(book['book_id'])
                                
                                # 2. 如果删除的是当前正在编辑的书，清理 Session
                                if st.session_state.get('current_book_id') == book['book_id']:
                                    st.session_state['current_book_id'] = None
                                
                                st.toast(f"《{book['title']}》已删除")
                                time.sleep(1)
                                st.rerun()


def render_editor(book_id):

    # 🆕 新增：侧边栏返回按钮
    with st.sidebar:
        if st.button("🔙 返回书架", use_container_width=True):
            del st.session_state['current_book_id']
            st.rerun()
        st.divider()

    # ==========================================
    # 2. 状态管理 (Session State)
    # ==========================================                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          
                                                                                                                                        
    if "thread_id" not in st.session_state:

        st.session_state.thread_id = str(uuid.uuid4())

    thread_config = {"configurable": {"thread_id": st.session_state.thread_id}}

    # 2. 确保核心数据结构存在 (防止 Key Error)
    if "final_novel_text" not in st.session_state:
        st.session_state.final_novel_text = ""

    # 🟢 关键修复：初始化大纲缓存
    if "current_outline" not in st.session_state:
        st.session_state.current_outline = None # 默认为 None，表示没有大纲

    if "current_chap_num" not in st.session_state:
        st.session_state.current_chap_num = 1
    # ----------------------------------------------------
    # 1. 世界观基础信息
    # ----------------------------------------------------
    with st.sidebar:
        st.image("https://img.icons8.com/color/96/000000/fantasy.png", width=50)
        st.title("🌍 世界维基")
        
        world_config = client.get_world_config(book_id)
        if world_config:
            with st.expander("📖 世界设定 (可微调)", expanded=False):
                # 允许用户手动修改简介 (Patch)
                new_intro = st.text_area("世界简介", value=world_config.get('intro', ''), height=150)
                
                # 允许用户修改力量体系 (作为文本)
                ps_val = world_config.get('power_system', '')
                if isinstance(ps_val, dict):
                    ps_val = json.dumps(ps_val, ensure_ascii=False, indent=2)
                
                new_ps = st.text_area("力量体系 (JSON/文本)", value=str(ps_val), height=100)
                
                if st.button("💾 更新设定"):
                    # 这里你需要一个 update_world_config 的 DB 方法
                    # 这是一个简单的 Update 操作，不会清空数据
                    try:
                        client.update_world_config(book_id, new_intro, new_ps)
                        st.success("设定已更新 (仅修改文本，不影响现有剧情)")
                        time.sleep(1)
                        st.rerun()
                    except Exception as e:
                        st.warning(f"更新失败: {e}")
        else:
            st.warning("⚠️ 数据丢失，请回书架重建")
    # ----------------------------------------------------
    # 2. 全书总纲 (BookPlan) - 新增
    # ----------------------------------------------------
    with st.sidebar:
        book_plan = client.get_book_plan(book_id)
        if book_plan:
            with st.expander("📜 全书总纲 & 进度", expanded=True):
                st.caption("📚 主线梗概")
                st.info(book_plan['main_story'])
                
                # 显示分卷进度
                curr_vol_idx = book_plan.get('current_volume', 1) 
                volumes = book_plan.get('volumes', [])
                
                st.caption(f"当前进度：第 {curr_vol_idx} 卷 / 共 {len(volumes)} 卷")
                
                if 0 <= curr_vol_idx - 1 < len(volumes):
                    vol = volumes[curr_vol_idx - 1]
                    st.write(f"**{vol['title']}**")
                    st.markdown(f"> 🎯 **本卷目标**：{vol['goal']}")
                    
                    # 手动推进分卷按钮 (留作扩展)
                    # if st.button("⏭️ 完成本卷"): ...

    # ----------------------------------------------------
    # 3. 卷进度监控
    # ----------------------------------------------------
    with st.sidebar:
        st.divider()
        st.header("📚 分卷进度监控")
        
        # 1. 获取全书规划
        book_plan = client.get_book_plan(book_id)
        
        if book_plan:
            # 获取当前卷索引 (0-based)
            v_idx = book_plan.get('current_volume', 1) - 1
            volumes = book_plan.get('volumes', [])
            
            if 0 <= v_idx < len(volumes):
                curr_vol = volumes[v_idx]
                est_len = curr_vol.get('estimated_chapters', 50) # 本卷预估长度
                
                # ----------------------------------------------------
                # 🟢 修复点 1: 获取真实且实时的“当前章节号”
                # ----------------------------------------------------
                # 不要只信 session，因为它可能还没更新。
                # 直接问数据库：现在写到第几章了？(get_next_chapter_num 返回的是即将要写的章节号)
                real_next_chap = client.get_next_chapter_num(book_id)
                
                # 正在写的这一章算进去，进度看起来更舒服 (比如即将写第6章，说明已经完成了5章)
                # 但为了显示“当前正在攻略第X章”，我们通常用 real_next_chap
                current_global_chap = real_next_chap 

                # ----------------------------------------------------
                # 🟢 修复点 2: 正确计算 Offset
                # ----------------------------------------------------
                # 算出前几卷加起来一共多少章
                start_offset = 0
                for i in range(v_idx):
                    # 安全获取，防止报错
                    vol_len = volumes[i].get('estimated_chapters', 50) 
                    start_offset += vol_len
                
                # ----------------------------------------------------
                # 🟢 修复点 3: 计算本卷进度
                # ----------------------------------------------------
                # 举例：全局第 55 章，前一卷 50 章 -> 本卷第 5 章
                # max(1, ...) 是为了防止刚开始写时出现 0 或负数
                local_num = max(1, current_global_chap - start_offset)
                
                # 计算百分比
                progress = min(local_num / est_len, 1.0)
                
                # ----------------------------------------------------
                # 🎨 UI 渲染
                # ----------------------------------------------------
                st.write(f"**第 {v_idx+1} 卷：{curr_vol['title']}**")
                
                # 显示进度条
                st.progress(progress)
                
                # 显示文字详情
                col_p1, col_p2 = st.columns([3, 2])
                col_p1.caption(f"本卷进度: {local_num}/{est_len}")
                col_p2.caption(f"全局: 第{current_global_chap}章")
                
                # 🚦 状态指示灯逻辑 (保持不变)
                if local_num > est_len:
                    st.error(f"⚠️ 溢出 {local_num - est_len} 章 (过渡期)")
                elif progress > 0.9:
                    st.warning("🔥 高潮收尾")
                elif progress < 0.1:
                    st.info("🌱 铺垫阶段")
                else:
                    st.success("🟢 正常推进")
        if progress > 0.8 or local_num > est_len:
                st.markdown("---")
                st.caption("🎛️ 分卷控制")
                
                # 检查是否还有下一卷
                has_next_vol = (v_idx + 1 < len(volumes))
                
                if has_next_vol:
                    next_vol_title = volumes[v_idx+1]['title']
                    if st.button(f"⏭️ 强制完结本卷 -> 进入《{next_vol_title}》"):

                        try:
                            client.update_book_plan_field(book_id, "current_volume", v_idx + 2)                               
                            st.success(f"已切换至第 {v_idx+2} 卷！")
                            time.sleep(1)
                            st.rerun()
                        except Exception as e:
                            st.error(f"切换失败: {e}")
                else:
                    st.info("🏁 当前已是最后一卷")
    with st.sidebar:
        with st.expander("🎨 AI 作家风格调校", expanded=True):
            writer_style = st.selectbox(
                "选择文风模型 (Writer Persona)",
                options=[
                    "男频-热血玄幻", 
                    "男频-系统数据",
                    "男频-诡秘智斗", 
                    "男频-稳健苟道",  # New
                    "男频-无敌碾压",  # New
                    "男频-末世废土",  # New
                    "男频-历史权谋",  # New
                    "女频-古言权谋", 
                    "女频-现言救赎"
                ],
                index=0, # 默认选个常用的
                help="不同的风格会彻底改变 AI 的遣词造句和剧情走向。",
                key="style_selector"
            )
    with st.sidebar:
        st.markdown("---")
        st.header("🏭 流水线批量生产")
        
        # 批量生成的配置项
        batch_count = st.number_input(
            "计划连续生成章节数", 
            min_value=1, 
            max_value=20, 
            value=1,
            help="一次性生成多章，适合快速推进剧情"
        )
        
        enable_auto_archive = st.checkbox(
            "启用自动归档 (跳过人工审核)", 
            value=True, 
            help="勾选后，系统会自动保存正文、更新状态并开始下一章。不勾选则生成一章后暂停。"
        )
        
        # 启动按钮
        start_batch = st.button("🔥 启动批量生成引擎", type="primary")
    
    with st.sidebar:
        with st.expander("👥 核心角色卡", expanded=True):
            # A. 主角与反派
            try:
                main_chars = client.get_ui_main_characters(book_id)
                
                if main_chars:
                    for c in main_chars:
                        # 🟢 修复点：数据库返回的是 'role' (字符串)，不是 'is_hero' (布尔)
                        # 数据格式: {'name': '...', 'identity': '...', 'role': '主角'}
                        role_str = c.get('role', '未知')
                        
                        # 根据文字决定 Emoji
                        emoji = "✨" if role_str == "主角" else "😈"
                        
                        st.markdown(f"**{c['name']}** ({emoji} {role_str})")
                        st.caption(f"身份：{c['identity']}")
                else:
                    st.caption("（暂无主角数据）")
            except Exception as e:
                # 打印详细错误方便调试
                st.error(f"角色读取失败: {e}")

            # B. 核心配角 (修复 AttributeError)
            try:
                # 🟢 如果这里报错 'no attribute'，说明 database.py 没更新全
                support_chars = client.get_ui_support_characters(book_id)
                if support_chars:
                    st.markdown("---") # 分割线
                    st.caption("🛡️ 核心团队")
                    for c in support_chars:
                        st.markdown(f"**{c['name']}**")
                        st.caption(f"身份：{c['identity']}")
            except AttributeError:
                st.warning("⚠️ database.py 未更新，缺少 get_ui_support_characters 方法")
            except Exception as e:
                st.error(f"配角读取失败: {e}")

    # -------------------------------------------------------
    # 模块 B: 主角状态监控 (Tag 系统版)
    # -------------------------------------------------------

    # ------------------------------------------------------------------
    # 侧边栏：主角状态监控 (Fixed)
    # ------------------------------------------------------------------
    with st.sidebar:
        st.subheader("👤 主角实时状态")
        
        try:
            hero = client.get_hero_full_status(book_id)

            if hero:
                # ------------------------------------------------
                # 1. 基础身份区
                # ------------------------------------------------
                st.write(f"**{hero.get('name', '未知')}**")
                st.caption(f"身份: {hero.get('identity', '无')}")
                
                # ------------------------------------------------
                # 2. 人设特征区 (新增显示)
                # ------------------------------------------------
                # 使用 expander 收纳静态人设，避免占据太多动态状态的空间
                with st.expander("🎭 人设档案", expanded=False):
                    if hero.get('personality'):
                        st.markdown(f"**性格:**\n{hero['personality']}")
                    
                    if hero.get('speech_style'):
                        st.markdown(f"**说话风格:**\n{hero['speech_style']}")
                    
                    st.divider()
                    
                    if hero.get('core_desire'):
                        st.markdown(f"🔥 **核心欲望:**\n{hero['core_desire']}")
                        
                    if hero.get('fear'):
                        st.markdown(f"😨 **恐惧/弱点:**\n{hero['fear']}")

                # ------------------------------------------------
                # 3. 金手指区 (新增显示)
                # ------------------------------------------------
                gf = hero.get('gold_finger')
                if gf:
                    st.success(f"🖐 **金手指:** {gf.get('name', '未知')}")
                    # 如果有详细描述，可以作为 help 显示，或者小字显示
                    if gf.get('core_ability'):
                        st.caption(f"能力: {gf.get('core_ability')}")

                # ------------------------------------------------
                # 4. 动态状态区 (Mental State)
                # ------------------------------------------------
                st.markdown("---") # 分割线
                
                # 心理状态
                mental = hero.get('mental_state', '平静')
                st.info(f"🧠 **心理状态:** {mental}")
                
                # ------------------------------------------------
                # 5. 身体状态 (Physical Tags)
                # ------------------------------------------------
                st.write("🏥 **身体/装备状态:**")
                
                tags = hero.get('physical_tags', [])
                
                # 兼容处理：Neo4j返回的可能是 None, 空列表, 或包含空字符串的列表
                valid_tags = [t for t in tags if t and t.strip()] # 过滤无效tag
                
                if not valid_tags:
                    st.caption("✅ 状态完美 (无负面标签)")
                else:
                    for tag in valid_tags:
                        # 用红色警告框显示每一个 Tag
                        st.error(f"🚑 {tag}")
            
            else:
                st.warning("数据同步中...")
                
        except Exception as e:
            st.error(f"状态读取失败: {e}")

        st.markdown("---")
    
    with st.sidebar:
        # 会话重置按钮
        if st.button("🗑️ 清空上下文缓存"):
            st.session_state.thread_id = str(uuid.uuid4())
            st.session_state.final_novel_text = ""
            st.rerun()

    
    if start_batch:
        st.header("🏭 正在执行批量生产任务...")
        progress_bar = st.progress(0)
        status_log = st.empty()
        
        # 进入循环
        for i in range(batch_count):
            current_step = i + 1
            current_chap_num = client.get_next_chapter_num(book_id)
            
            status_log.info(f"🚀 [进度 {current_step}/{batch_count}] 第 {current_chap_num} 章 | 正在请求 Agent 集群...")

            try:
                # ----------------------------------------------------
                # 步骤 A: 极简输入 (UI 只管发号施令)
                # ----------------------------------------------------
                inputs = {
                    "chapter_num": current_chap_num,
                    "user_intent": "剧情继续发展，保持连贯性", 
                    "style": writer_style,
                    "is_batch_mode": True,
                    "book_id": book_id,
                    "thread_id": st.session_state.thread_id
                }
                
                # 调用 Graph (API)
                resp = client.generate_content(inputs)
                
                # 获取结果
                draft_text = resp.get('draft', '')
                final_outline = resp.get('outline', {})
                if not draft_text:
                    st.error("生成失败")
                    break

                # ----------------------------------------------------
                # 步骤 B: 自动分析 (API)
                # ----------------------------------------------------
                status_log.write(f"🧠 第 {current_chap_num} 章：正在分析角色状态变更...")
                
                # AI 分析
                result = client.analyze_draft(book_id, draft_text)
                
                # ----------------------------------------------------
                # 步骤 C: 自动入库 (Database Update)
                # ----------------------------------------------------
                if enable_auto_archive:
                    status_log.write(f"💾 第 {current_chap_num} 章：正在写入数据库...")
                    
                    # ========================================================
                    # 1. 解析标题 & 摘要 (保持之前的修复)
                    # ========================================================

                    
                    # ... (标题解析逻辑保持不变) ...
                    # ... (标题解析逻辑保持不变)
                    # final_state is gone, use final_outline from API response
                    raw_outline = final_outline
                    outline_dict = {}
                    if isinstance(raw_outline, dict):
                        outline_dict = raw_outline
                    elif isinstance(raw_outline, str):
                        try:
                            clean_text = re.sub(r'^```json\s*', '', raw_outline, flags=re.MULTILINE)
                            clean_text = re.sub(r'```$', '', clean_text, flags=re.MULTILINE)
                            match = re.search(r'\{[\s\S]*\}', clean_text)
                            if match: outline_dict = json.loads(match.group(0))
                        except: pass
                    
                    chap_title_str = outline_dict.get("chapter_title", "")
                    if chap_title_str:
                        real_title = f"第{current_chap_num}章：{chap_title_str}"
                    else:
                        real_title = f"第{current_chap_num}章"

                    # ... (摘要处理逻辑保持不变) ...
                    ai_summary = result.get("summary", "")
                    if ai_summary and len(str(ai_summary)) > 10:
                        final_summary = ai_summary
                        if isinstance(final_summary, (dict, list)):
                            final_summary = json.dumps(final_summary, ensure_ascii=False)
                    else:
                        final_summary = draft_text[:150].replace("\n", " ") + "..."

                    # 构建归档请求对象
                    
                    # C. 准备角色状态更新列表
                    raw_updates = result.get("character_updates", {})
                    char_updates_list = []
                    if isinstance(raw_updates, dict):
                        for name, data in raw_updates.items():
                            final_state = "状态更新"
                            final_tags = []
                            if isinstance(data, dict):
                                final_state = data.get("mental_state", data.get("state", "状态更新"))
                                final_tags = data.get("tags", [])
                            elif isinstance(data, list) and len(data) > 0 and isinstance(data[0], dict):
                                final_state = data[0].get("mental_state", "状态更新")
                                final_tags = data[0].get("tags", [])
                            elif isinstance(data, list):
                                final_tags = data
                            
                            char_updates_list.append({
                                "name": name,
                                "mental_state": final_state,
                                "physical_tags": final_tags
                            })

                    # D. 准备新实体列表
                    new_ents = result.get("new_entities", [])
                    new_ents_list = []
                    if new_ents:
                        new_ents_list = [{
                            "name": e["name"], "type": e["type"], "desc": e["desc"],
                            "owner": e.get("owner", ""), "importance": 1
                        } for e in new_ents if e.get("name")]
                    
                    try:
                        archive_payload = {
                            "chapter_num": int(current_chap_num),
                            "title": real_title,
                            "content": draft_text,
                            "summary": str(final_summary),
                            "character_updates": char_updates_list,
                            "new_entities": new_ents_list
                        }
                        
                        client.archive_chapter(book_id, archive_payload)
                        status_log.success(f"✅ 第 {current_chap_num} 章《{real_title}》已完成并归档！")
                        
                    except Exception as e:
                       st.error(f"API 归档失败: {e}")
                       break
                    
                else:
                    st.warning("自动归档未开启，批量生成已暂停，请手动处理当前章节。")
                    st.session_state.final_novel_text = draft_text
                    break # 暂停循环

            except Exception as e:
                st.error(f"❌ 批量生成在第 {current_step} 步中断: {e}")
                break
                
            # 更新进度条
            progress_bar.progress(current_step / batch_count)
        
        # 循环结束
        st.balloons()
        status_log.success(f"🎉 批量任务完成！共生成 {batch_count} 章。")
    # ==========================================
    # 4. 主工作区
    # ==========================================
    st.title("⚔️ EpicWriter OS: 导演控制台")


    if not st.session_state.current_outline:
        try:
            snapshot_data = client.get_graph_state(st.session_state.thread_id)
            if snapshot_data:
                # 尝试从后端恢复现场
                backend_outline = snapshot_data.get('outline')
                # 只有当后端真的有东西时，才同步到前端
                if backend_outline:
                    st.session_state.current_outline = backend_outline
        except Exception as e:
            # 出错也不要紧，保持现状即可
            pass

    # --------------------------------------------------------------------
    # 逻辑判断：优先检查“防丢锁”里有没有货
    # --------------------------------------------------------------------

    # --- 场景 C: 显示结果 (优先级最高) ---
    # 只要 Session 里有正文，就直接显示，不管是刚生成的还是刷新出来的
    if st.session_state.final_novel_text:
        st.divider()
        st.header("✅ 最终成稿")
        
        # 显示正文
        st.text_area("正文内容", st.session_state.final_novel_text, height=600)
        
        # ==================================================================
        # 🟢 1. 预处理归档元数据 (在点击按钮前就准备好)
        # ==================================================================
        # A. 获取章节号
        current_chap_num = st.session_state.get("current_chap_num", client.get_next_chapter_num(book_id))
        
        # B. 获取标题 (核心修复：三级兜底策略)
        # 优先级 1: Session 中存的 planned_title (Scene B 解析过的)
        final_title = st.session_state.get("planned_title", "")
        
        # 优先级 2: 从 current_outline 里现找
        if not final_title:
            try:

                raw = st.session_state.current_outline
                if isinstance(raw, dict):
                    final_title = raw.get("chapter_title", "")
                elif isinstance(raw, str):
                    # 尝试正则提取
                    match = re.search(r'chapter_title["\']\s*:\s*["\']([^"\']+)["\']', raw)
                    if match: final_title = match.group(1)
            except:
                pass

        # 优先级 3: 默认值
        if not final_title:
            final_title = f"第 {current_chap_num} 章"
        
        # 格式美化: 如果标题只是 "迷雾"，改成 "第 15 章：迷雾"
        if f"第" not in final_title and f"Chapter" not in final_title:
            final_title = f"第 {current_chap_num} 章：{final_title}"

        # C. 准备摘要字符串 (防止 Neo4j 报错，统一转字符串)

        outline_str_for_db = "自动归档摘要"
        try:
            raw_outline = st.session_state.get("current_outline")
            if raw_outline:
                if isinstance(raw_outline, (dict, list)):
                    outline_str_for_db = json.dumps(raw_outline, ensure_ascii=False)
                else:
                    outline_str_for_db = str(raw_outline)
        except:
            pass
        
        # ==========================================
        # 👇 这里是核心修改部分：归档双按钮逻辑 👇
        # ==========================================
        st.subheader("💾 章节归档操作")
        
        col1, col2 = st.columns(2)
        
        # -------------------------------------------------------
        # 按钮 1: 快速归档 (省钱模式)
        # -------------------------------------------------------
        with col1:
            if st.button("⚡ 快速归档 (仅存正文)"):
                try:
                    # 1. 构造归档数据
                    archive_payload = {
                        "chapter_num": int(current_chap_num),
                        "title": final_title,
                        "content": st.session_state.final_novel_text,
                        "summary": outline_str_for_db,
                        # 快速归档不更新角色和实体，传空即可
                        "character_updates": [],
                        "new_entities": []
                    }
                    
                    # 2. 调用 API
                    client.archive_chapter(book_id, archive_payload)
                    
                    st.success(f"✅ 第 {current_chap_num} 章《{final_title}》已快速归档！")
                    
                    time.sleep(1)
                    
                    # 章节号 +1
                    st.session_state.current_chap_num = current_chap_num + 1
                    
                    # 重置状态
                    st.session_state.thread_id = str(uuid.uuid4())
                    st.session_state.final_novel_text = ""
                    
                    # 🟢 核心修复：必须清空大纲，否则会跳回 Scene B
                    st.session_state.current_outline = None 
                    if "planned_title" in st.session_state: del st.session_state.planned_title
                    
                    st.rerun() # 回到主页面
                    
                except Exception as e:
                    st.error(f"保存失败: {e}")

                

        # -------------------------------------------------------
        # 按钮 2: 深度归档 (AI 全局分析模式)
        # -------------------------------------------------------
        with col2:
            if st.button("🧠 深度归档 (AI分析状态)"):
                st.session_state.show_analysis = True

        # 如果点击了深度归档，显示 AI 分析和审核界面
        if st.session_state.get("show_analysis", False):
            try:
            # 🟢 修改点 1: 传入 book_id
                all_chars = client.get_ui_main_characters(book_id) + client.get_ui_support_characters(book_id)
                # Client returns list of dicts, but logic below expects dict {name: tags}
                # We need to adapt the response or the logic.
                # get_all_active_characters returned {name: [tags...]}
                # Let's mock fetching all chars via client (we don't have a single endpoint for all chars yet, but we can combine)
                # Or add `get_all_active_characters` to client.
                # Let's add a helper in client for this? Or just abuse the existing endpoints.
                # Actually, API `analyze_draft` does filtering internally now if I look at my previous refactor plan.
                # But here in "Deep Archive", it's doing manual analysis.
                # I should delegate this to API `analyze_draft` as well?
                # The logic in API `analyze_draft` (workflow.py:94) calls `maintainer.analyze_status_change`.
                # So I can just call `client.analyze_draft(book_id, content)`.
                # BUT wait, the UI here (Line 831+) allows *user* to see the analysis result BEFORE saving.
                # `client.analyze_draft` returns the result! So yes, I can use it.
                
                # Refactor strategy: 
                # Replace lines 834-871 with a single call to `client.analyze_draft`.
                pass
            except Exception:
                pass


            if "analysis_result" not in st.session_state:
                with st.spinner("Maintainer 正在扫描全员状态与新实体..."):
                    # 使用 API
                    raw_result = client.analyze_draft(book_id, st.session_state.final_novel_text)
                    st.session_state.analysis_result = raw_result
            
            # 获取原始结果
            result_text = st.session_state.analysis_result
            
            # ========================================================
            # 1. 强力 JSON 清洗与解析
            # ========================================================
            def clean_and_parse(text):
                """兼容字典、Markdown包裹、脏数据的通用解析器"""
                if isinstance(text, dict): return text
                try:
                    text = re.sub(r'^```json\s*', '', text, flags=re.MULTILINE)
                    text = re.sub(r'^```\s*', '', text, flags=re.MULTILINE)
                    text = re.sub(r'```$', '', text, flags=re.MULTILINE)
                    match = re.search(r'\{[\s\S]*\}', text)
                    if match: text = match.group(0)
                    return json.loads(text)
                except:
                    return {}

            # 执行解析
            result = clean_and_parse(result_text)
            
            # 兜底：如果解析彻底失败
            if not result:
                result = {"summary": "", "character_updates": {}, "new_entities": []}

            # --------------------------------------------------------
            # 2. 审核表单 (Tab页结构)
            # --------------------------------------------------------
            with st.form("audit_form"):
                st.subheader("🕵️ 全局状态审计")
                
                # 🟢 修复点：计算默认标题，用于界面显示
                current_chap_num = st.session_state.get("current_chap_num", 1)
                # 优先从 Scene B 存的变量拿标题
                default_title = st.session_state.get("planned_title", "")
                # 如果没拿到，尝试从大纲里现找
                if not default_title:
                    try:
                        raw_ol = st.session_state.get("current_outline")
                        if isinstance(raw_ol, dict): default_title = raw_ol.get("chapter_title", "")
                    except: pass
                if not default_title: default_title = f"第 {current_chap_num} 章"
                
                # 显示标题让用户确认
                final_title_input = st.text_input("章节标题", value=default_title)

                # 摘要编辑 (优先用 AI 生成的，如果没有就用空)
                new_summary = st.text_area("本章摘要", value=result.get("summary", ""))
                
                st.markdown("---")
                st.caption("👥 角色状态变更")
                
                # --- 数据标准化 (适配各种乱七八糟的 AI 返回格式) ---
                raw_updates = result.get("character_updates", {})
                safe_updates = []
                
                # 如果是字典 {"爱德华": {...}}
                if isinstance(raw_updates, dict):
                    for name, data in raw_updates.items():
                        if isinstance(data, dict):
                            safe_updates.append({
                                "name": name,
                                "mental_state": data.get("mental_state", data.get("state", "状态更新")), 
                                "physical_tags": data.get("tags", [])
                            })
                        elif isinstance(data, list) and len(data) > 0 and isinstance(data[0], dict):
                            # 处理 [{"state":...}] 这种套娃情况
                            safe_updates.append({
                                "name": name,
                                "mental_state": data[0].get("mental_state", "状态更新"),
                                "physical_tags": data[0].get("tags", [])
                            })
                        elif isinstance(data, list):
                            # 处理纯标签列表
                            safe_updates.append({"name": name, "mental_state": "状态更新", "physical_tags": data})
                
                # 如果是列表 [{"name":...}]
                elif isinstance(raw_updates, list):
                    for item in raw_updates:
                        if isinstance(item, dict): safe_updates.append(item)

                # --- 渲染 Tabs ---
                edited_chars_data = {} 
                if not safe_updates:
                    st.info("未检测到角色状态变更。")
                else:
                    # 限制 tab 数量防止报错
                    tabs = st.tabs([c.get("name", "未知") for c in safe_updates])
                    
                    for i, tab in enumerate(tabs):
                        char_info = safe_updates[i]
                        char_name = char_info.get("name", "未知")
                        
                        with tab:
                            c1, c2 = st.columns(2)
                            with c1:
                                new_state = st.text_input("状态/心理", value=char_info.get("mental_state", "正常"), key=f"state_{i}")
                            with c2:
                                current_tags = char_info.get("physical_tags", [])
                                tags_val = ",".join([str(t) for t in current_tags]) if isinstance(current_tags, list) else str(current_tags)
                                new_tags_str = st.text_area("特征标签", value=tags_val, key=f"tags_{i}")
                                final_tags = [t.strip() for t in new_tags_str.split(",") if t.strip()]
                            
                            # 收集数据
                            edited_chars_data[char_name] = {"tags": final_tags, "state": new_state}

                # --- 新实体注册 ---
                st.markdown("---")
                st.caption("✨ 新实体注册")
                
                detected_entities = result.get("new_entities", [])
                entity_rows = [
                    {
                        "save": True, "name": e.get("name"), "type": e.get("type", "Item"), 
                        "desc": e.get("desc", ""), "owner": e.get("owner", ""),
                        "importance": int(e.get("importance", 1))
                    } for e in detected_entities if e.get("name")
                ]
                
                edited_entities = st.data_editor(
                    entity_rows, num_rows="dynamic",
                    column_config={
                        "save": st.column_config.CheckboxColumn("入库?", width="small"),
                        "importance": st.column_config.NumberColumn("⭐", min_value=1, max_value=5, format="%d")
                    },
                    use_container_width=True, key="entity_editor"
                )

                # ========================================================
                # 3. 提交按钮 (存库 + 跳转)
                # ========================================================
                submitted = st.form_submit_button("✅ 确认全员更新并归档")
                
                if submitted:
                    status_box = st.status("正在执行世界演化...", expanded=True)
                    try:
                        # A. 存章节 (使用用户确认过的标题) - 通过 Archive API 一次性提交
                        
                        ents_to_save = [
                            {"name": i["name"], "type": i["type"], "desc": i["desc"], "owner": i["owner"]}
                            for i in edited_entities if i["save"] and i["name"]
                        ]
                        
                        # 构建 payload
                        char_updates_list = []
                        for char_name, char_data in edited_chars_data.items():
                             char_updates_list.append({
                                "name": char_name,
                                "mental_state": char_data["state"],
                                "physical_tags": char_data["tags"]
                            })

                        client.archive_chapter(
                            book_id,
                            {
                                "chapter_num": int(current_chap_num),
                                "title": final_title_input,
                                "content": st.session_state.final_novel_text,
                                "summary": new_summary,
                                "character_updates": char_updates_list,
                                "new_entities": ents_to_save
                            }
                        )
                        
                        status_box.write(f"✅ 第 {current_chap_num} 章《{final_title_input}》已存档")
                        
                        status_box.update(label="🎉 归档完成！", state="complete")
                        
                        # ========================================================
                        # 🟢 4. 自动跳转与清理 (修复卡住问题)
                        # ========================================================
                        time.sleep(1)
                        
                        # 章节号 +1
                        st.session_state.current_chap_num = current_chap_num + 1
                        
                        # 重置状态
                        st.session_state.thread_id = str(uuid.uuid4())
                        st.session_state.final_novel_text = ""
                        st.session_state.show_analysis = False
                        
                        # 🛑 必须清空大纲，否则会跳回 Scene B
                        st.session_state.current_outline = None 
                        if "planned_title" in st.session_state: del st.session_state.planned_title
                        
                        # 清理其他垃圾
                        for k in ["analysis_result", "balloons_shown", "brainstorm_ideas"]:
                            if k in st.session_state: del st.session_state[k]
                        
                        st.rerun() # 回到主页面
                        
                    except Exception as e:
                        status_box.update(label="❌ 归档失败", state="error")
                        st.error(f"详细错误: {e}")

                        
    elif st.session_state.current_outline:
        
        st.divider()
        st.header(f"🛑 导演介入：审核大纲 (第 {st.session_state.get('current_chap_num', '?')} 章)")
        

        # 1. 获取原始数据
        raw_outline = st.session_state.current_outline
        
        # 定义变量用于显示
        outline_display_text = ""
        planned_title = "未命名章节"
        pacing_note = ""

        # ------------------------------------------------------------------
        # 2. 智能解析 (兼容 字典/列表/字符串 三种格式)
        # ------------------------------------------------------------------
        # 情况 A: 已经是解析好的字典 (Agent直接返回了JSON对象)
        if isinstance(raw_outline, dict):
            planned_title = raw_outline.get("chapter_title", "未命名章节")
            scenes = raw_outline.get("scenes", [])
            pacing_note = raw_outline.get("pacing_note", "")
            # 将列表转为文本显示
            if isinstance(scenes, list):
                outline_display_text = "\n\n".join(str(s) for s in scenes)
            else:
                outline_display_text = str(scenes)

        # 情况 B: 已经是列表 (旧版逻辑)
        elif isinstance(raw_outline, list):
            planned_title = f"第 {st.session_state.get('current_chap_num')} 章"
            outline_display_text = "\n\n".join(str(s) for s in raw_outline)

        # 情况 C: 是字符串 (可能是 Markdown 或 纯 JSON 字符串)
        elif isinstance(raw_outline, str):
            
            def clean_and_parse_json(text):
                """尝试从乱七八糟的 AI 回复中提取纯净的 JSON"""
                try:
                    return json.loads(text) # 尝试直接转
                except:
                    pass
                try:
                    # 正则提取 { ... }
                    match = re.search(r'\{[\s\S]*\}', text)
                    if match: return json.loads(match.group(0))
                except:
                    pass
                return None

            # 尝试解析
            plan_data = clean_and_parse_json(raw_outline)
            
            if plan_data:
                # 解析成功
                planned_title = plan_data.get("chapter_title", "未命名章节")
                scenes = plan_data.get("scenes", [])
                pacing_note = plan_data.get("pacing_note", "")
                if isinstance(scenes, list):
                    outline_display_text = "\n\n".join(str(s) for s in scenes)
                else:
                    outline_display_text = str(scenes)
                st.success(f"📌 成功提取标题：**{planned_title}**")
            else:
                # 解析失败，降级显示
                st.warning("⚠️ 格式解析失败，显示原始文本")
                outline_display_text = raw_outline

        # ------------------------------------------------------------------
        # 3. UI 显示与编辑
        # ------------------------------------------------------------------
        if pacing_note:
            st.info(f"💡 **AI 节奏提示**: {pacing_note}")
        
        with st.expander("🔍 查看原始数据 (Debug)", expanded=False):
            st.write(raw_outline)

        st.markdown(f"### 📝 编辑大纲：{planned_title}")
        
        # 这里的 value 必须是处理过的纯文本字符串
        edited_outline_text = st.text_area("请修改分镜 (每行一个场景)：", value=outline_display_text, height=400)
        
        col1, col2, col3 = st.columns([2, 2, 2])
        
        # --- 按钮 1: 批准 ---
        with col1:
            if st.button("✅ 批准并生成正文", type="primary"):
                # A. 将文本还原回结构化数据
                # 简单的按行分割，或者按双换行分割
                final_scenes_list = [line.strip() for line in edited_outline_text.split('\n') if line.strip()]
                
                # 重组为标准格式传给后端
                final_outline_data = {
                    "chapter_title": planned_title,
                    "scenes": final_scenes_list
                }

                # B. 更新后端状态 (核心！)
                # 调用 Client 的 approve 接口
                resp = client.approve_outline(
                    st.session_state.thread_id,
                    planned_title,
                    final_scenes_list,
                    writer_style
                )
                
                generated_draft = ""
                if resp:
                    generated_draft = resp.get('draft', '')
                else:
                    st.error("后端请求失败，请检查 API 服务是否正在运行。")
                
                if generated_draft:
                    with st.status("✍️ Writer 正在撰写长文 (请耐心等待)...", expanded=True) as status:
                        try:
                            # 1. 存入正文
                            st.session_state.final_novel_text = generated_draft
                            # 2. 🟢 关键：清空大纲状态 (否则刷新后还会进 Scene B)
                            st.session_state.current_outline = None 
                            
                            status.update(label="✅ 生成成功！正在进入阅读页...", state="complete")
                            st.rerun() # 刷新 -> 进入 Scene C
                        except Exception as e:
                            st.error(f"Writer 运行出错: {e}")

        # --- 按钮 2: 模拟数据 ---
        with col2:
            if st.button("🧪 模拟生成 (测试用)"):
                mock_text = f"""
                # {planned_title} (模拟)
                
                这是一个测试生成的正文段落。如果看到这句话，说明状态流转逻辑已经通了。
                
                当前文风设置：{writer_style}
                """
                # 存入 Session
                st.session_state.final_novel_text = mock_text
                # 清空大纲，准备跳转
                st.session_state.current_outline = None
                
                st.success("✅ 已注入模拟数据！")
                st.rerun()

        # --- 按钮 3: 驳回重来 ---
        with col3:
            if st.button("❌ 驳回 / 重新规划"):
                # 清空 Session 里的大纲，页面会自动回到 Scene A
                st.session_state.current_outline = None
                # 可选：如果你想完全重置上下文，也可以更新 thread_id
                # st.session_state.thread_id = str(uuid.uuid4()) 
                st.rerun()
    # --- 场景 A: 开始新章节 ---

    # -------------------------------------------------------------------------
    # 场景 A: 初始状态 (开始新章节 / 灵感构思模式)
    # -------------------------------------------------------------------------
    else:
        st.header("🎬 编剧室 (Idea & Plan)")

        # 0. 初始化灵感缓存 (如果还没有)
        if "brainstorm_ideas" not in st.session_state:
            st.session_state.brainstorm_ideas = []

        # =================================================
        # 1. 动态获取上下文 (保持你的原逻辑)
        # =================================================
        try:
            # 查询主角
            hero_data = client.get_hero_full_status(book_id)
            # 查询世界观
            world_config = client.get_world_config(book_id)
            
            if hero_data and world_config:
                # 注意：get_hero_full_status 返回的是干净的字典，直接用 keys 即可
                hero_name = hero_data.get('name', '主角')
                
                default_intent = f"【当前主角：{hero_name}】\n请输入本章模糊意图。例如：{hero_name}到达了新地图，遇到突发状况..."
                
                intro = world_config.get('intro', '无')
                st.info(f"🌍 世界基调：{intro[:50]}...")
            else:
                hero_name = "主角" 
                default_intent = "主角开始新的冒险..."
                
        except Exception as e:
            hero_name = "主角"
            default_intent = f"读取错误: {e}"

        # =================================================
        # 2. 用户输入区
        # =================================================
        # 只有当还没生成灵感时，才允许大幅修改意图，否则锁定避免冲突
        disable_input = len(st.session_state.brainstorm_ideas) > 0
        
        user_input = st.text_area(
            "📝 第一步：输入本章剧情意图", 
            height=80, 
            value=default_intent,
            disabled=disable_input,
            help="输入你想写的剧情大概，点击'帮我构思'让AI生成具体的三个分支。"
        )
        
        # 自动获取下一章序号
        next_num = 1
        try:
            # if hasattr(db, 'get_next_chapter_num'):
            next_num = client.get_next_chapter_num(book_id)
        except:
            pass
        chapter_num = st.number_input("章节号", min_value=1, value=next_num, disabled=disable_input)

        st.markdown("---")

        # =================================================
        # 3. 核心交互流程：构思 -> 选择
        # =================================================
        
        # 【状态一：还未生成灵感】
        if not st.session_state.brainstorm_ideas:
            
            # 使用两列布局，区分两种模式
            c1, c2 = st.columns(2)
            
            # --- 模式 A: 基于输入构思 ---
            with c1:
                st.write("#### ✍️ 定向构思")
                st.caption("基于你在上方输入的意图进行发散。")
                if st.button("✨ 基于输入生成灵感", type="primary", use_container_width=True):
                    if not user_input.strip() or user_input == default_intent:
                        st.warning("请先在上方修改默认意图，或使用右侧的自动推演。")
                    else:
                        with st.spinner("🤖 Planner 正在基于你的想法头脑风暴..."):

                        # planner = PlannerAgent()

                            ideas = client.generate_brainstorming_options(user_input, chapter_num, book_id)
                            
                            if ideas:
                                st.session_state.brainstorm_ideas = ideas
                                st.rerun()
                            else:
                                st.error("灵感生成失败，请重试。")

            # --- 模式 B: 自动推演 (Auto-Pilot) ---
            with c2:
                st.write("#### 🎲 自动推演")
                st.caption("无视输入，完全基于总纲和前文接龙。")
                if st.button("🚀 帮我续写 (自动走势)", use_container_width=True):
                    with st.spinner("🤖 Planner 正在查阅总纲推演后续发展..."):

                        # planner = PlannerAgent()
                        
                        # 关键点：构造一个“特殊的意图”传给 AI
                        auto_intent = "【指令】用户未提供具体意图。请完全基于《全书总纲》的当前分卷目标，以及上一章的结尾，自动推演剧情的后续发展。"
                        
                        ideas = client.generate_brainstorming_options(auto_intent, chapter_num, book_id)
                        
                        if ideas:
                            st.session_state.brainstorm_ideas = ideas
                            st.rerun()
                        else:
                            st.error("推演失败，请重试。")

        # 【状态二：已生成灵感，等待选择】
        else:
            st.subheader("🤔 第三步：请选择一个剧情走向")
            
            # 增加一个重置按钮，万一用户想重新输入
            if st.button("🔄 不满意，重新输入"):
                st.session_state.brainstorm_ideas = []
                st.rerun()
                
            # 三列布局展示卡片
            cols = st.columns(3)
            for idx, idea in enumerate(st.session_state.brainstorm_ideas):
                with cols[idx]:
                    # 渲染漂亮的卡片
                    st.markdown(f"### 方案 {idea['option']}")
                    st.info(f"**{idea['title']}**")
                    st.caption(idea['desc'])
                    st.write(f"🎯 **影响**: {idea['impact']}")
                    
                    # 那个决定命运的按钮
                    if st.button(f"🎬 选用方案 {idea['option']}", key=f"btn_select_{idx}", use_container_width=True):
                        
                        # 1. 组合意图
                        final_intent = f"""
                        【用户原始意图】
                        {user_input}
                        
                        【选定剧情走向 (方案{idea['option']})】
                        标题：{idea['title']}
                        剧情：{idea['desc']}
                        """
                        
                        # 2. 构造输入
                        inputs = {
                            "chapter_num": chapter_num, 
                            "user_intent": final_intent,
                            "style": writer_style,
                            "book_id": book_id
                        }

                        # 3. 启动 API 生成
                        with st.status(f"🚀 正在基于方案 {idea['option']} 规划分镜...", expanded=True) as status:
                            try:
                                # 设置必要的参数
                                inputs["thread_id"] = st.session_state.thread_id
                                inputs["is_batch_mode"] = False
                                
                                # 调用 API
                                resp = client.generate_content(inputs)
                                # API 返回的是 WorkflowResponse: {draft, outline, ...}
                                
                                generated_outline = resp.get("outline")
                                
                                if generated_outline:
                                    # 存入 Session (前端状态)
                                    st.session_state.current_outline = generated_outline
                                    st.session_state.current_chap_num = chapter_num
                                    
                                    # 🗑️ 清理灵感缓存
                                    st.session_state.brainstorm_ideas = []
                                    
                                    status.update(label="✅ 大纲规划完成！正在跳转编辑器...", state="complete")
                                    
                                    # 🔄 刷新页面 -> 进入 Scene B
                                    st.rerun()
                                    
                                else:
                                    status.update(label="❌ 数据丢失", state="error")
                                    st.error("后端运行完毕，但未返回 'outline'。")
                                    st.write("API Response:", resp) # 调试看一眼
                                    
                            except Exception as e:
                                st.error(f"API 请求出错: {e}")
if __name__ == "__main__":
    main()