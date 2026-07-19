# 牍知库 (Du Zhi Ku) · 本地私有化案件智能分析与文书生成平台

> 牍=法律文书，知=结构化法律知识，库=本地私有化知识库
>
> 代码工程名：LexScript · v0.1.0 · 更新日期：2026-07-18

---

## 项目概述

牍知库是一款**本地私有化**部署的法律 AI 智能平台，面向执业律师、企业法务，提供「案件智能分析 + 文书自动生成 + 法条联动」一站式服务。

- **本地私有化**：所有数据存储在本地 SQLite + ChromaDB；API Key Fernet 加密存储于磁盘，绝不外传
- **AI 对话**：支持 MiniMax / Claude / DeepSeek / GPT-4o 四家共 8 个模型；4 个角色预设（法律专家/诉讼律师/企业法务/合同专员）
- **百 MB 卷宗**：PDF/Word/Excel/图片 OCR 全格式解析，流式分片索引，不阻塞
- **一键案稿**：5 步工作流（读卷宗 → 向量检索 → 法条匹配 → 历史避错 → AI 生成）
- **法条联动**：文书自动标注法条来源，司法解释/指导案例联动匹配
- **模板库**：起诉状/答辩状/代理词/合同/律师函等内置模板，Jinja2 变量动态渲染
- **Agent 系统**：完整案件智能分析 Agent，含 1 个主控系统提示词 + 4 个场景子提示词 + 双模型协同 + 记忆迭代规则

---

## 快速启动

### 后端启动

```bash
cd /Users/kaikai/LexScript/backend

# 首次启动：创建虚拟环境
python3.11 -m venv venv
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 启动服务（自动建表 + 自动创建默认 admin 账号）
./venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 7800
```

启动后访问：
- **本机**：<http://127.0.0.1:7800>
- **局域网**：<http://{LAN_IP}:7800>（同 WiFi 设备可访问）
- **公网隧道（serveo.net）**：`cat /Users/kaikai/LexScript/tunnel_url.txt` 获取当前 URL
- **API 文档**：<http://127.0.0.1:7800/api/docs>

### 公网隧道（临时）

```bash
# 启动隧道（使手机或非局域网设备可访问）
ssh -tt -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
  -o ServerAliveInterval=30 -o ServerAliveCountMax=3 \
  -R 80:localhost:7800 serveo.net
```
隧道 URL 会打印在终端中，也可访问 `/api/v1/info` 查看（字段 `tunnel_url`）。

### 默认管理员

| 字段 | 值 |
|------|-----|
| 用户名 | `admin` |
| 密码 | `admin123` |

首次启动自动创建，启动日志会提示立即修改默认密码。后端为单用户模式（`LEGAL_SINGLE_USER=true`），注册接口默认关闭。

---

## 技术栈

| 层 | 选型 | 理由 |
|----|------|------|
| 后端 | Python 3.11 + FastAPI + uvicorn | 与 tuixue_v3 同源，原生 async 适合 SSE 流式对话 |
| LLM SDK | httpx（自封装，不走 openai-sdk） | 4 道防线：重试/熔断/Schema 校验/截断/注入防御 |
| 向量库 | ChromaDB（持久化到本地） | 比 FAISS 易用，内置 metadata 过滤，无需独立 daemon |
| Embedding | MiniMax `text-embedding-3-small` 或本地 bge-small-zh | 默认走云端，断网降级本地 sentence-transformers |
| 文档解析 | PyMuPDF + python-docx + openpyxl + pytesseract | 各格式原生库，流式读取支持百 MB |
| 数据库 | SQLite WAL + safe_write 模式 | 单文件，无部署负担，移植自 tuixue_v3 |
| 任务队列 | asyncio.create_task + APScheduler | 轻量，无需 Celery/Redis |
| 前端 | Vanilla JS + SPA（hash router） | 单文件部署，无构建步骤，与 tuixue_v3 一致 |
| 加密 | Fernet（API Key）+ bcrypt（密码）+ JWT HS256 | 双层密钥保护 |

---

## 目录结构

```
LexScript/
├── README.md                          ← 本文档
│
├── backend/                           ← Python FastAPI 后端
│   ├── requirements.txt               依赖清单
│   ├── pyproject.toml                 项目元数据
│   ├── app/
│   │   ├── main.py                    FastAPI 入口 + 路由注册 + 静态托管 + SPA fallback
│   │   ├── config.py                  集中常量（HOST/PORT/角色预设/法条分类/文书结构）
│   │   │
│   │   ├── core/                      核心层
│   │   │   ├── security.py            Fernet 加密（自动生成 .fernet_key）
│   │   │   ├── auth.py                JWT + bcrypt 用户认证
│   │   │   ├── logger.py              loguru 分级日志
│   │   │   ├── exceptions.py          BusinessError + 全局 handler
│   │   │   ├── tunnel.py              公网隧道探测
│   │   │   │
│   │   │   ├── agent/
│   │   │   │   └── prompts.py         ★ Agent 全套提示词（主控 / 4 场景 / 双模型 / 记忆）
│   │   │   │
│   │   │   ├── llm/
│   │   │   │   ├── base.py            BaseLLM 抽象基类
│   │   │   │   ├── minimax.py         MiniMax 实现（兼容 OpenAI 协议）
│   │   │   │   ├── deepseek.py        DeepSeek 适配器
│   │   │   │   ├── claude.py          Claude 适配器
│   │   │   │   └── registry.py        LLM 注册表（8 模型 + 配置加载）
│   │   │   │
│   │   │   ├── parser/                多格式文档解析
│   │   │   │   ├── base.py            解析器基类 + Chunk 模型
│   │   │   │   ├── router.py          解析路由（自动按扩展名分发）
│   │   │   │   ├── pdf_parser.py      PyMuPDF 解析
│   │   │   │   ├── docx_parser.py     python-docx 解析
│   │   │   │   ├── excel_parser.py    openpyxl 解析
│   │   │   │   └── text_parser.py     TXT/MD/CSV/JSON 解析
│   │   │   │
│   │   │   └── vector/                向量 + 混合检索
│   │   │       ├── store.py           ChromaDB 持久化封装
│   │   │       ├── embedder.py        Embedding（MiniMax 云端 / bge-small-zh 本地）
│   │   │       ├── chunker.py         文本分片
│   │   │       └── hybrid.py          BM25 + 向量混合检索（权重可调）
│   │   │
│   │   ├── db/                        数据库层
│   │   │   ├── database.py            SQLite 引擎（WAL, busy_timeout, 线程安全）
│   │   │   ├── safe_write.py          retry+rollback 写保护
│   │   │   └── migrations/
│   │   │       ├── 001_initial.sql     12 张基础表 DDL
│   │   │       ├── 002_indexes.sql     性能索引
│   │   │       └── 003_users.sql       用户系统（3 张表 + 数据隔离预留）
│   │   │
│   │   ├── services/                  业务逻辑层
│   │   │   ├── config_service.py      系统配置（加密读/写/脱敏）
│   │   │   ├── user_service.py        用户 CRUD + 登录/登出/刷新
│   │   │   ├── chat_service.py        会话管理 + SSE 流式编排 + Agent 提示词注入
│   │   │   ├── file_service.py        文件导入/解析/索引管道
│   │   │   ├── vector_service.py      检索编排（语义/关键词/混合）
│   │   │   ├── document_generator.py  ★ 5 步一键案稿生成工作流
│   │   │   ├── template_service.py    Jinja2 模板渲染
│   │   │   ├── statute_service.py     法条缓存 + 搜索
│   │   │   └── export_service.py      PDF/DOCX/MD 导出
│   │   │
│   │   ├── schemas/                   数据模型（预留）
│   │   │
│   │   ├── api/v1/                    RESTful API 路由层
│   │   │   ├── __init__.py            APIRouter 聚合
│   │   │   ├── config.py              配置 + LLM 连通性测试
│   │   │   ├── auth.py                用户登录/注册/登出/刷新/改密
│   │   │   ├── chat.py                会话 CRUD + SSE 流式消息
│   │   │   ├── files.py               文件导入/上传/解析/索引/删除
│   │   │   ├── search.py              语义/关键词/混合检索 + 法条反查
│   │   │   ├── documents.py           文书生成/编辑/导出/法条引用/风险扫描
│   │   │   ├── templates.py           模板 CRUD + Jinja2 预览
│   │   │   ├── statutes.py            法条检索/管理/同步
│   │   │   ├── tasks.py               异步任务进度查询/取消
│   │   │   └── logs.py                操作日志列表/写入
│   │   │
│   │   ├── tasks/                     异步任务（预留）
│   │   │
│   │   └── web/
│   │       └── static/index.html      SPA 前端（1181 行，12 view）
│   │
│   ├── data/                          运行时数据（gitignore）
│   │   ├── db.sqlite                  SQLite 数据库（WAL 模式）
│   │   ├── vector_store/              ChromaDB 持久化目录
│   │   ├── exports/                   导出文件
│   │   ├── sessions/                  历史会话 JSON 备份
│   │   ├── .fernet_key                Fernet 密钥（0o600）
│   │   └── .jwt_secret                JWT 密钥（0o600）
│   │
│   └── tests/                         pytest 测试
│
└── frontend/                          （预留）Vue3 + Element Plus
    └── (Phase 2 启用)
```

---

## 配置说明

### 1. API Key 配置（首次使用必做）

进入前端 → **系统配置** 页面：

| 字段 | 说明 | 示例 |
|------|------|------|
| **API Key** | MiniMax / Claude / DeepSeek / GPT 的 API Key | `sk-PLACEHOLDER-...` |
| **Base URL** | API 端点（留空走默认 MiniMax） | `https://api.MiniMax.io/v1` |
| **模型** | 下拉选择，共 8 个预设 | `MiniMax-M3` |

**操作流程**：
1. 填入 API Key
2. 点击 **测试连接** 验证（返回延迟 + 模型回复 + token 用量）
3. 点击 **保存** 加密落库（写入 `system_config` 表，Fernet 加密）

**支持的 8 个模型**（`GET /api/v1/config/models`）：

| 提供商 | 模型 |
|--------|------|
| MiniMax | `MiniMax-M3`, `MiniMax-M2` |
| Claude | `claude-3-5-sonnet-20241022`, `claude-3-haiku-20240307` |
| DeepSeek | `deepseek-chat`, `deepseek-reasoner` |
| GPT | `gpt-4o`, `gpt-4o-mini` |

### 2. 角色预设

4 个角色，影响 AI 系统提示词（新建会话时自动应用）：

| 角色 | 适用场景 |
|------|----------|
| **法律专家** | 法律问题分析、专业法律意见 |
| **诉讼律师** | 起诉状/答辩状/代理词/上诉状 |
| **企业法务** | 公司治理、合同审核、合规风控、股权架构 |
| **合同专员** | 商务合同起草审核、条款完备、风险防控 |

### 3. 环境变量

```bash
# 服务
LEGAL_HOST=0.0.0.0
LEGAL_PORT=7800
LEGAL_DEBUG=false
LEGAL_DATA_DIR=              # 数据目录，默认 backend/data

# MiniMax API（也支持在前端 UI 配置，优先级低于 DB 配置）
MINIMAX_API_KEY=sk-...
MINIMAX_BASE_URL=https://api.MiniMax.io/v1
MINIMAX_MODEL=MiniMax-M3

# Embedding
EMBEDDING_PROVIDER=minimax   # minimax | local
EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_LOCAL_MODEL=BAAI/bge-small-zh-v1.5

# 用户系统
LEGAL_SINGLE_USER=true        # true=自动建 admin/admin123；false=需注册
LEGAL_JWT_SECRET=             # 空则首次启动自动生成
LEGAL_REGISTER_OPEN=false     # true 才允许 /api/v1/auth/register

# 检索参数
CHUNK_SIZE=500
CHUNK_OVERLAP=50
TOP_K=20
HYBRID_VECTOR_WEIGHT=0.7

# 任务队列
TASK_WORKERS=2
TASK_MAX_CONCURRENT=4
```

---

## API 参考

所有 12 个路由模块已完整实现，注册于 `/api/v1/*` 前缀下。

### 健康与信息

```
GET  /api/v1/health          → {"ok":true,"service":"legal-saas","version":"0.1.0"}
GET  /api/v1/info            → 服务信息（含 LAN IP / 公网隧道 URL）
```

### 配置（Config）

```
GET   /api/v1/config              公开配置（密钥脱敏，含短别名 provider/model/api_key/base_url）
PATCH /api/v1/config              批量更新（支持短别名 provider/api_key/base_url/model）
GET   /api/v1/config/providers    4 家 Provider 列表（含 base_url + 可用模型）
GET   /api/v1/config/models       可选模型列表
POST  /api/v1/config/test         测试连接（临时凭证，20s 超时）
POST  /api/v1/config/test_saved   测试连接（已保存凭证）
GET   /api/v1/config/agent/prompt 返回 Agent 主控提示词 + 4 个场景子提示词
```

**支持的 Provider**：

| Provider | Base URL | 模型 |
|----------|----------|------|
| MiniMax | <https://api.MiniMax.io/v1> | MiniMax-M3, MiniMax-M2 |
| Claude | <https://api.anthropic.com/v1> | claude-3-5-sonnet-20241022, claude-3-haiku-20240307 |
| DeepSeek | <https://api.deepseek.com> | deepseek-chat, deepseek-reasoner |
| OpenAI | <https://api.openai.com/v1> | gpt-4o, gpt-4o-mini |

### 用户认证（Auth）

```
POST /api/v1/auth/login            登录 → 返回 access + refresh token
POST /api/v1/auth/logout           登出（撤销 token）
POST /api/v1/auth/refresh          refresh token 换新 access token
GET  /api/v1/auth/me               当前用户信息（Bearer token）
POST /api/v1/auth/register         注册新用户（默认关闭）
POST /api/v1/auth/change_password  当前用户改密（自动撤销其他登录）
```

### 对话（Chat）

```
POST   /api/v1/chat/sessions             创建会话
GET    /api/v1/chat/sessions             列出会话
GET    /api/v1/chat/sessions/{uuid}      获取会话 + 消息列表
PATCH  /api/v1/chat/sessions/{uuid}      更新会话
DELETE /api/v1/chat/sessions/{uuid}      删除会话
POST   /api/v1/chat/sessions/{uuid}/messages  SSE 流式发送消息
GET    /api/v1/chat/models              可用模型列表（含 Provider）
GET    /api/v1/chat/roles                角色预设列表
```

流式对话支持 4 种场景参数：`case_overview` / `document_generation` / `compliance_check` / `evidence_analysis`，自动注入对应的 Agent 场景子提示词。

对话支持**双模型路由**：含法律关键词（法条/起诉/诉讼/合同/风险等）的消息自动走「主 LLM 事实提取 → Alpha GPT 法律分析」双阶段流程。

### 文件（Files）

```
POST   /api/v1/files/folders           创建案件文件夹
GET    /api/v1/files/folders           列出文件夹
POST   /api/v1/files/import            导入本地路径（文件或目录递归）
POST   /api/v1/files/upload            上传文件（multipart）
GET    /api/v1/files                   列出文件（按文件夹/状态过滤）
GET    /api/v1/files/{id}              获取文件详情
DELETE /api/v1/files/{id}              删除文件（含分片 + 向量）
POST   /api/v1/files/{id}/parse        解析 + 向量索引
GET    /api/v1/files/{id}/chunks       查看文件分片
GET    /api/v1/files/vector/count      向量库文档计数
```

### 检索（Search）

```
POST /api/v1/search         语义/关键词/混合检索（mode 参数切换）
POST /api/v1/search/by-statute  按法条号反查引用文书
```

### 文书（Documents）

```
POST   /api/v1/documents/generate          ★ 一键生成（5 步工作流）
POST   /api/v1/documents/from-template     模板填充生成
GET    /api/v1/documents                   列出文书
GET    /api/v1/documents/{uuid}            获取文书
PATCH  /api/v1/documents/{uuid}            更新文书
DELETE /api/v1/documents/{uuid}            删除文书
POST   /api/v1/documents/{uuid}/regenerate         全量重生成
POST   /api/v1/documents/{uuid}/regenerate-section  段落重生成
POST   /api/v1/documents/{uuid}/cite-statutes       补法条引用
POST   /api/v1/documents/{uuid}/risk-scan           风险扫描
GET    /api/v1/documents/{uuid}/export              导出（MD/DOCX）
```

### 模板（Templates）

```
GET    /api/v1/templates           列出模板（按分类过滤）
POST   /api/v1/templates           创建模板
GET    /api/v1/templates/{id}      获取模板
PATCH  /api/v1/templates/{id}      更新模板
DELETE /api/v1/templates/{id}      删除模板
POST   /api/v1/templates/{id}/preview   Jinja2 变量渲染预览
GET    /api/v1/templates/builtins      内置模板列表
```

### 法条（Statutes）

```
POST /api/v1/statutes/search       法条关键词检索
GET  /api/v1/statutes/{code}       按法条号查询
POST /api/v1/statutes/upsert       新增/更新法条
GET  /api/v1/statutes/categories   法条分类列表
POST /api/v1/statutes/sync         法条批量同步
```

### 任务（Tasks）

```
GET    /api/v1/tasks           异步任务列表
GET    /api/v1/tasks/{uuid}    任务进度查询
DELETE /api/v1/tasks/{uuid}    取消任务
```

### 日志（Logs）

```
GET  /api/v1/logs     操作日志列表
POST /api/v1/logs     写入操作日志
```

完整 API 文档：启动后访问 <http://127.0.0.1:7800/api/docs>（FastAPI 自动生成 Swagger UI）。

---

## 数据库 Schema（15 张表）

### 基础 12 张表（`001_initial.sql`）

| 表名 | 说明 |
|------|------|
| `chat_sessions` | 会话（uuid/title/type/role/model） |
| `chat_messages` | 消息（session/role/content/tokens/parent） |
| `case_folders` | 案件文件夹（name/root_path/case_number） |
| `files` | 文件索引（path/size/sha256/status/chunk_count） |
| `file_chunks` | 文件分片（content/char_start/char_end/vector_id/metadata） |
| `templates` | 模板（name/category/content/variables/is_builtin） |
| `documents` | 文书归档（uuid/doc_type/content/source_files/statutes/risk_tags） |
| `document_corrections` | 纠错记录（issue_type/original/corrected/severity） |
| `statutes` | 法条缓存（code/name/category/content/source） |
| `system_config` | 系统配置（key/value_encrypted） |
| `async_tasks` | 异步任务（uuid/type/status/progress/payload/result） |
| `operation_logs` | 操作日志（action/target/detail/ip/user_agent） |

### 用户系统 3 张表（`003_users.sql`）

| 表名 | 说明 |
|------|------|
| `users` | 用户（uuid/username/email/password_hash/salt/role） |
| `auth_tokens` | JWT refresh token（token_hash/type/expires_at/revoked_at） |
| `login_attempts` | 登录尝试日志（防爆破，1h 10 次失败限频） |

### 加密策略

- **密码**：bcrypt（cost=12）+ 额外 16 字节 salt 防 rainbow table
- **JWT**：HS256，access 24h / refresh 30d，密钥 `data/.jwt_secret`（0o600 自动生成）
- **refresh token**：DB 只存 SHA256 hash，明文只返回一次，撤销灵活
- **API Key**：Fernet 对称加密，密钥 `data/.fernet_key`（0o600）

---

## 前端指南（13 View SPA）

入口为 `/Users/kaikai/LexScript/backend/app/web/static/index.html`（单文件 2688 行），Hash 路由 SPA。

| View | 路由 | 功能 | 状态 |
|------|------|------|------|
| **工作台** | `#/dashboard` | 统计 + 快捷入口 + 系统状态 + 访问入口 | 可用 |
| **本地卷宗** | `#/files` | 文件夹树 + 文件列表 + 导入/解析/索引 | 可用 |
| **AI 对话** | `#/chat` | 多角色会话 + SSE 流式对话 + 上下文 + 场景切换 | 可用 |
| **智能分析** | `#/agent` | 4 任务卡片 + Master System Prompt 展示/复制/刷新 | **新增** |
| **模板库** | `#/templates` | 模板分类 + 编辑器 + 变量渲染预览（含 5 个内置模板） | 可用 |
| **文书编辑** | `#/editor` | 文书查看/编辑/导出/法条引用/风险扫描 | 可用 |
| **一键生成** | `#/generator` | 4 步向导 → 读卷宗 → AI 生成文书 | 可用 |
| **智能检索** | `#/search` | 语义/关键词/混合检索 + 法条反查 | 可用 |
| **法条检索** | `#/statutes` | 法条分类树 + 关键词/全文检索（含 10 条法条种子数据） | 可用 |
| **复盘** | `#/review` | 历史会话回顾 + AI 复盘 | 可用 |
| **系统配置** | `#/settings` | **统一多 Provider 配置**：MiniMax/Claude/DeepSeek/OpenAI 下拉选择 + API Key 输入 + 模型选择 + 一键配置测试 | 可用 |
| **任务队列** | `#/tasks` | 异步任务进度 + 后台 worker | 可用 |
| **操作日志** | `#/logs` | API 调用 + 文书生成 + 文件操作记录 | 可用 |

**新增特性**：
- **统一 API 配置**：Provider 下拉框 → API Key 输入 → Base URL 自动填充 → 模型选择 → 「一键配置 & 测试」
- **Agent 专属页**：4 个快捷任务卡片（全案案情梳理/文书一键生成/文书合规校验/证据清单）+ Master System Prompt 展示
- **内置种子数据**：5 个法律文书模板 + 10 条常用法条（民法典/合同法/公司法/刑法/劳动法）
- **双模型路由**：法律关键词自动触发「事实提取 → Alpha GPT 分析」双阶段
- **Provider 自动发现**：切换 Provider 时自动从后端拉取可用模型列表

**特性**：
- 深色/浅色双主题切换（`🌗 主题`按钮），偏好持久化到 localStorage
- ≤768px 自动汉堡菜单，safe-area 适配刘海屏
- 紧凑布局 + 响应式网格

---

## 文档解析器

| 格式 | 库 | 说明 |
|------|----|------|
| PDF | PyMuPDF（fitz） | 文本 + 布局提取 |
| DOCX | python-docx | Word 文档段落解析 |
| XLSX | openpyxl | Excel 表格逐行读取 |
| TXT | Python 内置 | 纯文本 |
| MD | Python 内置 | Markdown 文本 |
| CSV | Python 内置 | 逗号分隔值 |
| JSON | Python 内置 | JSON 结构展开 |
| 图片 OCR | pytesseract + Pillow | 图片文字识别 |

解析器架构基于 `BaseParser` 抽象基类，返回 `Chunk` 流，支持进度回调。新格式只需继承 `BaseParser` + 注册到 `parser/router.py`。

---

## 向量存储与检索

### ChromaDB 持久化

- 数据目录：`backend/data/vector_store/`
- 默认集合名：`documents`
- 距离度量：cosine（`hnsw:space: cosine`）
- API：`VectorStore` 封装类（add / search / delete_by_metadata / count / delete_all）

### 混合检索（Hybrid Search）

向量 + BM25 加权融合：
1. 向量召回：ChromaDB cosine 距离
2. BM25 关键词召回：命中率计算
3. 加权融合：`final_score = vector_weight * v_score + (1 - vector_weight) * bm25_score`

默认 `vector_weight = 0.7`，可通过 `HYBRID_VECTOR_WEIGHT` 环境变量调整。

### 引导词

将文本切成固定大小分片（默认 500 字符，重叠 50 字符），逐片写入 `file_chunks` 表 + ChromaDB。

---

## 核心工作流：一键案稿生成

`document_generator.py` 实现了完整的 5 步工作流：

1. **读取卷宗**：从 `file_chunks` 表取出指定文件的分片内容，拼接为上下文
2. **向量检索匹配**：用 `search_hybrid` 检索同案件历史文书 + 同类模板
3. **法条匹配**：SQL `LIKE` 模糊匹配 `statutes` 表，命中相关法条
4. **历史避错**：从 `document_corrections` 表取出高频错误记录，注入 system prompt
5. **AI 生成**：调用 LLM `stream()` 流式生成，结果落库到 `documents` 表

支持段落重生成、法条自动标注、合规风险扫描（v0.2.0 完整版）。

---

## Agent 系统提示词（完整版）

以下为 Agent 系统的完整提示词体系，是牍知库的**核心智能引擎**。

### 主控系统提示词（MASTER_SYSTEM_PROMPT）

```text
# 角色定位
你是面向执业律师、企业法务的专属「案件智能分析与文书生成Agent」，运行于案件智能分析工作台，依托「本地私有案件知识库 + Alpha GPT专业法律引擎 + 通用大模型语义整合」三大底座工作。
你的核心准则是：**事实全部来自本地材料，法律分析优先Alpha专业能力，所有结论可溯源，错误不重复出现**。

## 核心工作铁则（必须严格遵守，零容忍违反）
1. 事实唯一原则：所有案件事实陈述100%来自当前案件已入库的本地材料，禁止脑补、推演、补充材料未提及的信息；材料存在矛盾时必须明确标注矛盾点，不得自行取舍。
2. 专业优先原则：法律定性、法条援引、请求权基础分析、风险判断、文书合规校验，必须调用Alpha GPT输出专业结论；通用大模型仅负责事实整合、排版润色、格式适配、多格式导出。
3. 全程可溯源原则：事实引用必须标注「来源文件名 + 页码/段落位置」，法条引用必须标注「法律全称 + 具体条款号 + 效力状态」，支持跳转原文核验。
4. 增量自动整合原则：当前案件新增材料入库后，自动将新内容整合进案件整体事实框架，后续所有分析、生成均基于最新全量材料，无需用户手动提示更新。
5. 零重复错误原则：自动记忆本案件历史生成中的所有纠错记录、格式问题、法律适用错误，后续生成同类内容时主动规避，不得重复出现已被指出的问题。
6. 司法规范原则：所有文书输出严格符合人民法院司法文书样式规范，法言法语准确，格式标准，逻辑层级清晰。

## 固定执行流程（所有任务必须按此顺序执行）
1. 调用【本地向量检索工具】：从当前案件知识库中检索与指令相关的全部材料片段，锁定事实依据；
2. 调用【案件记忆库】：读取本案件历史纠错记录、历史文书版本、已确认的案件事实，规避重复错误；
3. 判断任务类型：
   - 涉及法律分析、法条、风险、合规校验 → 调用【Alpha GPT法律引擎】，传入事实片段获取专业法律结论；
   - 仅涉及事实梳理、排版、格式转换 → 通用模型直接处理；
4. 整合事实+法律结论，匹配对应文书模板，生成完整成果；
5. 自检：核对事实是否有来源、法条是否有效、是否存在历史重复错误；
6. 输出结果，附带溯源标注与材料来源索引。

## 输出格式规范
1. 日常咨询分析：采用「核心结论 + 事实依据（标注来源） + 法律依据（标注法条） + 风险提示」四段式结构；
2. 结构化案件画像：分级标题+列表呈现，关键信息加粗，按当事人、时间线、证据清单、争议焦点分类；
3. 正式文书输出：严格遵循官方文书格式，段落层级分明，法条引用规范，文末附《法律依据对照表》；
4. 材料缺失提示：若材料不足无法完成指令，明确列出「缺失材料清单」，说明补充后可完成的内容，禁止强行生成。

## 能力边界
- 可处理：案情梳理、证据整理、争议焦点归纳、各类诉讼文书生成、合同审查、律师函起草、文书风险校验、法条检索、诉讼策略建议。
- 不可做：承诺案件结果、替代律师执业判断、提供绝对化胜诉结论、虚构未入库的案件事实、引用失效废止法条。
```

### 4 个场景子提示词（SCENE_PROMPTS）

#### case_overview（案件全景画像）

```text
基于当前案件全量本地材料，输出标准化案件画像，要求：
1. 基础信息：案号、案由、审理法院、当事人全称及诉讼地位、审理阶段；
2. 案件时间线：按时间顺序排列立案、举证、开庭、裁判等关键节点，标注来源文件；
3. 原告诉称与被告辩称：分别提炼核心事实主张与诉讼请求/抗辩意见；
4. 证据清单：按原被告分组，列明证据名称、证明事项、证据来源文件；
5. 核心争议焦点：归纳3-5个本案核心法律与事实争议点；
6. 新增材料已自动整合，标注本次更新新增的信息项。
输出结构清晰，层级分明，所有事实标注材料来源。
```

#### document_generation（文书生成）

```text
基于当前案件全量材料，生成一份符合司法规范的【{doc_type}】，执行要求：
1. 先调用Alpha GPT确定本案请求权基础、对应法条、诉讼请求的合规性；
2. 从本地材料中提取当事人信息、事实经过、证据清单，填充至文书对应位置；
3. 严格遵循法院文书格式：首部→诉讼请求→事实与理由→证据清单→尾部；
4. 事实与理由部分逻辑清晰，法言法语规范，不添加材料外的主观臆断；
5. 文末附法律依据对照表，列明引用的全部法条全称、条款号、原文内容；
6. 读取本案件历史纠错记录，规避已出现过的格式、表述、法律适用错误；
7. 所有事实标注对应材料来源，支持溯源核验。
生成完成后同步渲染至本地对应模板，支持导出DOCX/PDF格式。
```

#### compliance_check（合规校验）

```text
对当前目标文书做全面专业合规校验，调用Alpha GPT完成以下审查：
1. 法条适用审查：引用法条是否现行有效、是否与本案法律关系匹配、是否存在引用错误；
2. 逻辑与事实审查：事实陈述是否与在案材料一致、是否存在矛盾、诉讼请求是否有事实支撑；
3. 程序风险审查：是否存在诉讼时效、管辖、主体资格、举证期限等程序风险；
4. 格式规范审查：是否符合司法文书样式标准、术语是否准确、层级是否清晰；
5. 输出格式：问题清单+风险等级（高/中/低）+ 修改建议+对应法条依据；
6. 对比历史纠错记录，标注是否重复出现同类问题。
```

#### evidence_analysis（证据分析）

```text
基于本案全量证据材料，完成以下工作：
1. 按「原告证据/被告证据」分组，生成标准化证据清单，包含序号、证据名称、证据类型、证明事项、页码范围、来源文件；
2. 针对对方证据，逐一出具质证意见，从「真实性、合法性、关联性、证明目的」四维度分析；
3. 质证意见的法律依据调用Alpha GPT校验，确保举证规则适用准确；
4. 所有意见标注对应材料来源，可跳转核验；
5. 输出可直接用于庭审的标准格式，支持导出。
```

### 双模型协同规则（DUAL_MODEL_COLLAB_PROMPT）

```text
# 双模型分工与协同规则
## 能力分工（严格边界，不得越位）
### Alpha GPT 负责（专业法律核心）
- 法律关系定性、请求权基础分析、抗辩权梳理
- 精准法条援引、效力校验、司法解释关联
- 文书合规性审查、法律风险预判
- 类案裁判观点参考、诉讼策略论证
- 法律术语规范、司法程序判断

### 通用大模型（MiniMax）负责（事实与工程层）
- 本地案件材料深度检索、事实提取、内容整合
- 文书排版润色、格式调整、模板变量填充
- 多轮对话交互、上下文记忆、用户需求理解
- 多格式文档转换（PDF/DOCX/Markdown）
- 案件结构化信息梳理、时间线/证据清单排版

## 协同执行流程
1. 通用模型接收指令，检索本地材料，提取标准化事实片段；
2. 通用模型整理清晰的指令+事实摘要，传入Alpha GPT；
3. Alpha GPT输出专业法律框架、法条依据、专业结论；
4. 通用模型将法律结论与案件事实结合，填充模板、排版润色、补充溯源标注；
5. 最终输出完整可用的成果。

## 数据隐私规则
- 案件原始卷宗、涉密材料默认不上传Alpha GPT；
- 仅传入生成所需的最小化事实摘要与结构化信息，不传完整原文；
- 可由用户手动开启「全量材料上传模式」，提升分析精准度。
```

### 记忆与迭代规则（MEMORY_ITERATION_PROMPT）

```text
# 案件记忆与迭代规则
## 记忆内容范围
1. 本案件所有历史对话记录、已确认的案件事实、用户明确认可的结论；
2. 历史生成的所有文书版本、用户指出的错误与修改意见；
3. 用户明确的格式偏好、表述习惯、文书排版要求；
4. 已确认的当事人信息、证据分类、争议焦点等结构化信息。

## 记忆使用规则
1. 每次生成文书前，必须读取对应类型的历史纠错记录，主动规避同类错误；
2. 用户新增材料后，自动更新案件结构化记忆，后续回答默认基于最新全量信息；
3. 用户未明确推翻的事实与结论，默认持续有效，无需反复确认；
4. 同类案件的通用格式错误、法律适用错误，跨案件积累沉淀，全局规避。

## 增量更新规则
1. 新增材料入库后，自动对比原有案件画像，输出「新增/变更信息摘要」；
2. 自动修正因新材料导致的事实变化、争议焦点变化，同步更新案件记忆库；
3. 历史生成文书若与新材料冲突，主动标注冲突点，提示用户是否更新文书。
```

### 角色预设到系统提示词的映射

```text
legal_expert:         MASTER_SYSTEM_PROMPT + 「你当前角色：**法律专家**。精通法律体系，擅长分析法律问题、提供专业法律意见。」
litigator:           MASTER_SYSTEM_PROMPT + 「你当前角色：**诉讼律师**。擅长诉讼文书(起诉状/答辩状/代理词/上诉状)，注重诉讼策略、事实论证、法条适用。」
corp_counsel:        MASTER_SYSTEM_PROMPT + 「你当前角色：**企业法务**。擅长公司治理、合同审核、合规风控、股权架构，兼顾商业可行性与法律风险。」
contract_specialist:  MASTER_SYSTEM_PROMPT + 「你当前角色：**合同专员**。擅长起草审核各类商务合同，注重条款完备性、风险防控、权责对等。」
```

---

## 用户系统（预埋 · 未开放 UI）

### 当前状态

- 单用户模式（默认）：首次启动自动创建 `admin` / `admin123`
- 登录 API 完整可用，但前端未暴露登录 UI
- 切换多用户：`LEGAL_SINGLE_USER=false` + `LEGAL_REGISTER_OPEN=true`

### API 端点状态

| 方法 | 路径 | 说明 | 状态 |
|------|------|------|------|
| `POST` | `/api/v1/auth/login` | 用户名密码登录 | 可用 |
| `POST` | `/api/v1/auth/logout` | 登出 | 可用 |
| `POST` | `/api/v1/auth/refresh` | 刷新 token | 可用 |
| `GET` | `/api/v1/auth/me` | 当前用户信息 | 可用 |
| `POST` | `/api/v1/auth/register` | 注册新用户 | 默认关闭 |
| `POST` | `/api/v1/auth/change_password` | 改密 | 可用 |

### 数据隔离（v0.2.0 启用）

`files` / `case_folders` / `chat_sessions` / `chat_messages` / `documents` / `templates` 表预留了 `owner_user_id` 字段。

---

## 外网隧道（可选）

```bash
# SSH 反向隧道（绕过 DNS 劫持）
ssh -R 80:localhost:7800 serveo.net

# 或 ngrok（需要 authtoken）
ngrok http 7800
```

前端"访问入口"区域自动展示所有可访问 URL（本机 / LAN / 公网隧道）。

---

## 开发与扩展

### 添加新 LLM

```python
# backend/app/core/llm/myprovider.py
from app.core.llm.base import BaseLLM

class MyProviderLLM(BaseLLM):
    name = "myprovider"
    default_model = "my-model-v1"

    async def chat(self, messages, **kwargs): ...
    async def stream(self, messages, **kwargs): ...
```

注册到 `registry.py`，前端自动出现在模型下拉。

### 添加新解析器

```python
# backend/app/core/parser/myparser.py
from app.core.parser.base import BaseParser

class MyParser(BaseParser):
    extensions = [".myformat"]
    def parse(self, path: str, progress_cb=None):
        for chunk in ...:
            yield chunk
```

注册到 `parser/router.py`，前端上传自动分发。

### 启用多用户模式

```bash
LEGAL_SINGLE_USER=false
LEGAL_REGISTER_OPEN=true
# 重启 uvicorn，注册端点开放
```

---

## 测试

```bash
cd /Users/kaikai/LexScript/backend
source venv/bin/activate
pytest tests/ -v
```

手动验证清单：
- [ ] 启动后 admin 用户自动创建，日志提示改密
- [ ] Settings 页配置 API Key → 测试连接 → 返回延迟 + 回复
- [ ] `curl /api/v1/config` 返回脱敏后的 key（`sk-t**************5678`）
- [ ] 文件导入 → 解析 → 向量索引 → 检索
- [ ] AI 对话 SSE 流式输出
- [ ] 一键案稿生成完整 5 步流程
- [ ] 手机访问 LAN URL，布局自适应
- [ ] 深色/浅色主题切换无 bug
- [ ] 关闭浏览器重开，主题保持（localStorage）

---

## 实施进度

### v0.1.0（当前）

- [x] FastAPI 骨架 + 12 路由模块全部注册
- [x] SQLite WAL + safe_write（15 张表 + 索引）
- [x] LLM 适配层（4 家 8 模型：MiniMax/Claude/DeepSeek/GPT-4o）
- [x] Fernet 加密 + 系统配置（API Key 脱敏展示 + 测试连接）
- [x] JWT + bcrypt 用户系统（单用户 + 多用户预埋）
- [x] Agent 系统提示词（主控 + 4 场景 + 双模型 + 记忆迭代）
- [x] 文件解析管道（PDF/DOCX/XLSX/TXT/MD/CSV/JSON/OCR）
- [x] ChromaDB 向量库 + BM25 混合检索
- [x] 5 步一键案稿生成工作流
- [x] 模板库 + Jinja2 渲染
- [x] 法条缓存 + 检索
- [x] 文书导出（MD/DOCX）
- [x] SPA 前端（12 view + 双主题 + 移动端）
- [x] SSE 流式对话 + 场景提示词注入
- [x] 异步任务 + 操作日志
- [x] 访问入口（本机/LAN/公网隧道）

### v0.2.0（下一阶段）

- [ ] 多用户登录/注册 UI
- [ ] 案件数据隔离（`owner_user_id`）
- [ ] 文书编辑器（Monaco + 法条 chip + 定位跳转）
- [ ] 法条外部 API 自动同步
- [ ] 完整段落级重生成
- [ ] 法条自动标注 + 合规风险扫描增强
- [ ] ChatGPT 语义缓存

### v0.3.0（后续）

- [ ] Vue3 + Element Plus 重构前端
- [ ] 批量案件处理
- [ ] PyInstaller 桌面打包（单 exe）
- [ ] Docker Compose 一键部署
- [ ] 外接扫描仪/传真自动入库

---

## 关键文件清单

**后端核心入口**：
- `/Users/kaikai/LexScript/backend/app/main.py` — FastAPI 入口
- `/Users/kaikai/LexScript/backend/app/config.py` — 集中配置

**Agent 系统**：
- `/Users/kaikai/LexScript/backend/app/core/agent/prompts.py` — ★ 全套 Agent 提示词

**数据库**：
- `/Users/kaikai/LexScript/backend/app/db/database.py` — SQLite 引擎
- `/Users/kaikai/LexScript/backend/app/db/safe_write.py` — 写保护
- `/Users/kaikai/LexScript/backend/app/db/migrations/001_initial.sql` — 12 张基础表
- `/Users/kaikai/LexScript/backend/app/db/migrations/003_users.sql` — 用户 3 张表

**核心业务**：
- `/Users/kaikai/LexScript/backend/app/services/document_generator.py` — 5 步案稿生成
- `/Users/kaikai/LexScript/backend/app/services/chat_service.py` — SSE 对话 + Agent 注入
- `/Users/kaikai/LexScript/backend/app/services/file_service.py` — 文件解析管道
- `/Users/kaikai/LexScript/backend/app/services/vector_service.py` — 检索编排

**向量与解析**：
- `/Users/kaikai/LexScript/backend/app/core/vector/store.py` — ChromaDB 封装
- `/Users/kaikai/LexScript/backend/app/core/vector/hybrid.py` — BM25 混合检索
- `/Users/kaikai/LexScript/backend/app/core/parser/router.py` — 解析器路由

**前端**：
- `/Users/kaikai/LexScript/backend/app/web/static/index.html` — 12 view SPA 单文件

**数据存储**：
- `/Users/kaikai/LexScript/backend/data/db.sqlite` — SQLite 数据库
- `/Users/kaikai/LexScript/backend/data/vector_store/` — ChromaDB 持久化目录
- `/Users/kaikai/LexScript/backend/data/.fernet_key` — Fernet 密钥
- `/Users/kaikai/LexScript/backend/data/.jwt_secret` — JWT 密钥

---

## License

Private · 本地私有化部署，禁止未授权复制分发

---

**打造者**：Sushikai · **技术栈**：MiniMax / FastAPI / SQLite WAL / ChromaDB / bcrypt / JWT / Local-first
