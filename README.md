# Network Expert Agent

一个面向网络协议问答的 AI Agent 项目，使用 `LangGraph` 组织 RFC 检索流程，使用 Supabase `pgvector` 作为远程向量库，并同时提供命令行与简易 Web 界面。

## 项目定位

这个项目不是一个“通用联网搜索助手”，而是一个“预热式 RFC 专家”：

- 路由层先判断问题应该交给 RFC 专家还是通用对话助手。
- RFC 专家只回答已经预加载到向量库中的协议内容。
- 对未入库协议、旧版本协议或不在支持范围内的 RFC，会直接返回“暂未入库”，不会在对话时临时联网补库。

这套设计的目标是让回答范围更可控，减少幻觉和长时间等待。

## 当前能力

- 基于 LLM 的问题路由：`rfc_expert` / `general_agent`
- 基于 `LangGraph` 的 RFC 工作流：`analyze -> check_availability -> search -> answer`
- 基于 Supabase `pgvector` 的远程检索
- 预加载/清库前自动初始化 Supabase schema
- 通过 OpenAI-compatible Embedding API 生成向量
- 支持命令行交互
- 支持内置轻量 Web UI
- 支持以 `api/` + `public/` + `vercel.json` 结构部署到 Vercel
- 支持脚本化清库与 RFC 预加载

## 当前支持的协议范围

协议支持范围由 `src/core/protocol_specs.json` 驱动，而不是写死在业务逻辑里。

当前默认支持：

- `IGMP`，最新协议内容对应 `RFC 3376`
- `MLD`，最新协议内容对应 `RFC 3810`
- `PIM`，最新协议内容对应 `RFC 7761`

当前默认不支持：

- `IGMPv1`
- `IGMPv2`
- `MLDv1`
- 其他未配置到 `protocol_specs.json` 的 RFC / 协议

如果后续要扩展协议范围，优先更新 `src/core/protocol_specs.json`，再执行预加载脚本。

## 技术栈

- Python 3.12+
- `LangGraph`
- `langchain-openai`
- Supabase Postgres + `pgvector`

## 安装

1. 安装 Python 3.12 或更高版本。
2. 安装依赖：

```bash
uv sync
```

## 环境变量

在项目根目录创建 `.env`：

```env
# LLM
OPENROUTER_API_KEY=your_openrouter_api_key
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
DEFAULT_MODEL=deepseek/deepseek-chat

# Embedding API (OpenAI-compatible)
EMBEDDING_API_BASE_URL=https://api.openai.com/v1
EMBEDDING_API_KEY=sk-your-embedding-key
EMBEDDING_MODEL_NAME=text-embedding-3-small

# Supabase pgvector
SUPABASE_DB_URL=postgresql://postgres.<project-ref>:<password>@aws-0-<region>.pooler.supabase.com:6543/postgres?sslmode=require
SUPABASE_VECTOR_TABLE=rfc_knowledge_base
SUPABASE_VECTOR_DIM=1536
SUPABASE_VECTOR_DISTANCE=cosine

# Optional: LangSmith tracing
LANGCHAIN_API_KEY=
LANGCHAIN_PROJECT=NetworkExpertAgent
ENABLE_LANGSMITH_TRACING=false
```

说明：

- `OPENROUTER_API_KEY` 和 `DEFAULT_MODEL` 用于问题路由、RFC 答案生成和通用对话。
- `EMBEDDING_*` 需要指向一个 OpenAI-compatible 的 embedding 服务。
- `SUPABASE_DB_URL` 建议直接从 Supabase Dashboard 的 `Connect` 页面复制 pooler 连接串。
- 当前代码只支持 `SUPABASE_VECTOR_DISTANCE=cosine`。
- 如果配置了 `LANGCHAIN_API_KEY`，而未显式设置 `ENABLE_LANGSMITH_TRACING`，代码会默认开启 tracing。
- 首次执行清库或预加载时，脚本会自动尝试创建 `pgvector` 扩展、`public.rfc_knowledge_base` 表和相关索引。
- 如果当前数据库用户没有执行扩展或 DDL 的权限，脚本会失败，此时需要改用有权限的连接串或在 Supabase 控制台中手动处理权限问题。

## 预加载 RFC

清空当前知识库：

```bash
uv run python scripts/clear_rfc_db.py
```

按当前协议配置预加载 RFC：

```bash
uv run python scripts/preload_rfcs.py
```

这两个脚本都会先执行同一套幂等初始化检查，再继续后续操作。

这里的预加载集合来自 `src/core/protocol_specs.json`。

## 运行方式

命令行模式：

```bash
uv run network-expert
```

Web 模式：

```bash
uv run network-expert-web
```

启动后访问：

- [http://127.0.0.1:8000](http://127.0.0.1:8000)

Vercel 部署结构：

- `api/chat.py` 提供聊天接口
- `api/health.py` 提供健康检查
- `api/index.py` 提供首页 HTML
- `public/app.css` 与 `public/app.js` 提供静态资源
- `vercel.json` 保持 `/` 与 `/health` 对外路径不变

## 使用示例

- `What is the default query interval in IGMPv3?`
- `MLDv2 是由哪个 RFC 定义的？`
- `PIM-SM 是由哪个 RFC 定义的？`
- `IGMPv2 支持吗？`
- `Hello, how are you?`

预期行为：

- 协议/RFC 问题会优先进入 RFC 专家流程。
- 问候、闲聊和泛化问题会进入通用对话助手。
- 如果问题命中了未预热协议或旧版本协议，系统会直接返回未入库提示。

当前统一回答格式：

- `结论`
- `出处定位`
- `协议原文节选`

其中 RFC 相关回答会尽量输出结构化 JSON，并要求 `出处定位` 至少包含 RFC 编号和 section / appendix，`协议原文节选` 必须来自已检索到的 RFC 上下文原文，而不是自由改写。

## 项目结构

```text
NetworkExpertAgent/
├── api/
│   ├── chat.py                # Vercel 聊天函数入口
│   ├── health.py              # Vercel 健康检查入口
│   └── index.py               # Vercel 首页入口
├── public/
│   ├── app.css                # Web 静态样式
│   └── app.js                 # Web 前端脚本
├── src/
│   ├── main.py                 # CLI 入口与统一问题处理函数
│   ├── agents/
│   │   ├── general_agent.py    # 通用对话助手
│   │   └── rfc_agent.py        # RFC 专家 LangGraph 工作流
│   ├── config/
│   │   └── settings.py         # 环境变量与运行配置
│   ├── core/
│   │   ├── protocol_specs.json # 协议支持清单
│   │   ├── rfc_catalog.py      # 协议/RFC 解析与范围判断
│   │   ├── router.py           # 问题路由
│   │   └── state.py            # LangGraph 状态定义
│   ├── tools/
│   │   ├── rag_tools.py        # 向量库读写与检索
│   │   └── rfc_tools.py        # RFC 下载、切分、预加载与查询拼装
│   ├── web/
│   │   ├── app.py              # 共享 Web 页面与 API 响应逻辑
│   │   └── server.py           # 本地 Web server 入口
├── scripts/
│   ├── clear_rfc_db.py         # 清空 RFC 向量库
│   └── preload_rfcs.py         # 预加载支持范围内的 RFC
├── tests/
│   ├── benchmark.py
│   ├── benchmark_metrics.py
│   ├── quiz.md
│   ├── test_agents.py
│   ├── test_rag_tools.py
│   └── test_scripts.py
├── pyproject.toml
├── vercel.json
└── uv.lock
```

## 测试

运行单元测试：

```bash
uv run python -m unittest tests.test_agents tests.test_rag_tools tests.test_scripts
```

运行 benchmark：

```bash
uv run python tests/benchmark.py
```

运行单题完整流程回归测试：

```bash
uv run python tests/test_single_quiz.py
```

Benchmark 特点：

- 使用 `tests/quiz.md` 中的问题集
- `tests/quiz.md` 采用 JSON 结构，期望答案包含 `conclusion` / `source` / `ref`
- agent 输出会被解析为统一三字段：`结论`、`出处定位`、`协议原文节选`
- 结论正确性由 LLM judge 评分
- 出处定位准确性通过 RFC 编号与 section / appendix 匹配评分
- 置信度通过回答中的 `协议原文节选` 与 `quiz.md` 中期望 RFC 原文的匹配度评分，用于衡量幻觉程度
- 最终得分 = 结论 `40%` + 出处定位 `20%` + 置信度 `20%` + 耗时 `20%`

单题回归测试特点：

- 只执行 `tests/quiz.md` 中的第 1 题
- 仍然走完整的路由、RFC 检索、答案生成、结构化评估流程
- 若主流程报错、`结论` 低于 `8/10`、`出处定位` 低于 `6/10`、`置信度` 低于 `6/10`、最终得分低于 `7/10`，或耗时评级为 `不及格`，脚本会以非零状态退出

当前耗时评分阈值：

- `0-30s`：优秀
- `30-60s`：良好
- `60-120s`：及格
- `>120s`：不及格

## 设计说明

这个项目当前有几个比较重要的设计约束：

- 不在聊天阶段自动增量补库
- 不把“支持哪些协议”散落在代码各处，而是集中到 `protocol_specs.json`
- 使用远程 Supabase 向量库，而不是本地向量文件
- 把 schema 初始化逻辑内聚到代码里，由维护脚本自动执行
- 路由、检索、答案生成共用 LLM 配置，但职责分离
