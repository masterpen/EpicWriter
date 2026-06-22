# EpicWriter - AI 小说创作系统

<p align="center">
  <img src="https://img.shields.io/badge/React-19-blue" alt="React">
  <img src="https://img.shields.io/badge/FastAPI-green" alt="FastAPI">
  <img src="https://img.shields.io/badge/LangGraph-purple" alt="LangGraph">
  <img src="https://img.shields.io/badge/Neo4j-lightgray" alt="Neo4j">
</p>

 EpicWriter 是一款 AI 驱动的网络小说创作系统，采用多 Agent 协作架构，自动完成从世界观构建到正文写作的全流程。

## ✨ 特性

- **AI 创世纪**：输入创意即可自动生成完整世界观、大纲和首章
- **多 Agent 协作**：Planner(规划) → Writer(写作) → Reviewer(审核) → Maintainer(维护)
- **章节审核**：AI 自动评分，不达标自动重写
- **世界设定管理**：Neo4j 图数据库存储人物关系和世界观
- **事实核查**：自动检测剧情逻辑冲突
- **现代 UI**：React 19 + Tailwind CSS 响应式界面

## 🛠️ 技术栈

| 前端 | 后端 | 数据库 | AI 框架 |
|------|------|--------|----------|
| React 19 | FastAPI | Neo4j | LangGraph |
| TypeScript | Python 3.10+ | | LangChain |
| Tailwind CSS | Uvicorn | | OpenAI/DeepSeek |

## 🚀 快速开始

### 前置要求

- Node.js 18+
- Python 3.10+
- Docker & Docker Compose

### 1. 克隆项目

```bash
git clone <your-repo>
cd EpicWriter
```

### 2. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env 填入你的 API Key 和数据库密码
```

### 3. 一键启动（推荐）

```bash
docker-compose up --build
```

访问：
- 前端：http://localhost:5173
- 后端 API：http://localhost:8000
- Neo4j 浏览器：http://localhost:7474

### 4. 本地开发（可选）

#### 后端

```bash
cd api
pip install -r requirements.txt
python -m uvicorn api.main:app --reload
```

#### 前端

```bash
npm install
npm run dev
```

## 📖 API 文档

启动后访问：http://localhost:8000/docs

### 认证接口

| 方法 | 路径 | 描述 |
|------|------|------|
| POST | /api/auth/register | 用户注册 |
| POST | /api/auth/login | 用户登录 |
| GET | /api/auth/me | 获取当前用户 |

### 书籍接口

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | /api/books | 获取用户书籍列表 |
| POST | /api/books | 创建新书籍 |
| GET | /api/books/{id} | 获取书籍详情 |
| DELETE | /api/books/{id} | 删除书籍 |

### 工作流接口

| 方法 | 路径 | 描述 |
|------|------|------|
| POST | /api/workflow/generate | 生成新章节 |
| POST | /api/workflow/brainstorm | 头脑风暴 |
| POST | /api/workflow/approve-outline | 审核通过大纲 |
| POST | /api/workflow/save-chapter | 保存章节 |

## 📁 项目结构

```
EpicWriter/
├── api/                    # FastAPI 后端
│   ├── main.py            # 应用入口
│   ├── models.py          # Pydantic 模型
│   └── routers/           # API 路由
│       ├── auth.py        # 认证路由
│       ├── books.py       # 书籍路由
│       └── workflow.py    # 工作流路由
├── app/                    # 核心业务逻辑
│   ├── agents/            # AI Agent 实现
│   │   ├── core.py       # Planner/Writer/Reviewer
│   │   ├── maintainer.py # 状态维护
│   │   └── fact_checker.py # 事实核查
│   ├── core/             # 核心工具
│   │   ├── config.py     # 配置
│   │   ├── database.py   # Neo4j 操作
│   │   └── logger.py     # 日志
│   └── workflow/          # LangGraph 工作流
│       └── graph.py      # 流程定义
├── src/                    # React 前端
│   ├── components/        # UI 组件
│   ├── pages/             # 页面
│   └── lib/               # 工具函数
├── docker-compose.yml     # Docker 配置
└── README.md
```

## 🔧 配置说明

| 环境变量 | 说明 | 默认值 |
|----------|------|--------|
| NEO4J_URI | Neo4j 连接地址 | bolt://localhost:7687 |
| NEO4J_USERNAME | 数据库用户名 | neo4j |
| NEO4J_PASSWORD | 数据库密码 | - |
| OPENAI_API_KEY | OpenAI/DeepSeek API Key | - |
| OPENAI_BASE_URL | API 端点 | https://api.deepseek.com |
| JWT_SECRET_KEY | JWT 密钥 | - |

## 📝 许可

MIT License
