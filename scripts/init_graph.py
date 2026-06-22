import sys
import os

# 将项目根目录加入路径，否则找不到 app 包
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import db

def init_cyber_world():
    print("🚀 正在初始化 [赛博修真] 世界观...")
    
    # 1. 清空旧数据 (防止重复运行导致数据堆积)
    db.query("MATCH (n) DETACH DELETE n")
    print("🧹 旧世界已清除。")
    
    # 2. 创建主角：林萧
    # 注意属性：我们混合了修真(level)和赛博(implants)
    db.query("""
        CREATE (p:Character {
            name: '林萧', 
            level: '练气期 (Lv.1)', 
            identity: '贫民窟黑客',
            hp: 100, 
            mp: 50,
            implants: ['老式眼部义体', '破损的道法芯片'],
            tags: ['主角', '隐忍', '复仇']
        })
    """)
    print("👤 主角 [林萧] 已诞生。")
    
    # 3. 创建反派：赵无极
    db.query("""
        CREATE (v:Character {
            name: '赵无极', 
            level: '筑基期 (Lv.20)', 
            identity: '荒坂宗外门执事',
            hp: 2000, 
            implants: ['军用级麒麟臂', '聚灵反应堆'],
            tags: ['反派', '傲慢', '资本走狗']
        })
    """)
    print("😈 反派 [赵无极] 已诞生。")
    
    # 4. 创建地点
    db.query("""
        CREATE (l1:Location {name: '新玉京下城区', vibe: '阴暗潮湿，霓虹闪烁'})
        CREATE (l2:Location {name: '荒坂宗云端塔', vibe: '一尘不染，灵气充裕'})
    """)
    
    # 5. 建立关系 (最关键的一步！)
    # 林萧 仇恨 赵无极
    db.query("""
        MATCH (p:Character {name: '林萧'}), (v:Character {name: '赵无极'})
        CREATE (p)-[:HATES {
            reason: '赵无极强行拆迁孤儿院并夺走了林萧的家传芯片', 
            intensity: 100,
            status: 'active'
        }]->(v)
    """)
    
    # 赵无极 蔑视 林萧
    db.query("""
        MATCH (p:Character {name: '林萧'}), (v:Character {name: '赵无极'})
        CREATE (v)-[:DISDAINS {reason: '视其为下水道老鼠'}]->(p)
    """)
    
    # 林萧 位于 下城区
    db.query("""
        MATCH (p:Character {name: '林萧'}), (l:Location {name: '新玉京下城区'})
        CREATE (p)-[:LOCATED_IN]->(l)
    """)
    
    print("🔗 人物关系与地理位置已连接。")
    print("✅ 世界初始化完成！请去 Neo4j Browser 查看。")
    
    db.close()

if __name__ == "__main__":
    init_cyber_world()