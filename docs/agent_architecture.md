# Python Agent 主链路说明

这个项目的主链路是一个 Python 实现的轻量 Agent 服务。它的目标不是让模型无限自由地行动，而是把售后问题拆成可控步骤：先判断问题类型，再决定是否追问、检索知识库、生成回答或转人工工单。

## 为什么叫 Agent

普通 RAG 问答通常是：

```text
用户问题 -> 知识库检索 -> 大模型回答
```

本项目的 Agent 链路是：

```text
用户问题
  -> Fast Router
  -> Structured Planner
  -> Memory / Knowledge Search / Troubleshooting Tree / Ticket Draft
  -> Verifier
  -> 回答 / 追问 / 转人工
```

也就是说，系统不是只做“检索 + 回答”，而是会根据不同情况选择不同动作：

- 信息不足：先追问设备型号、错误码、网络类型、在线状态等字段。
- 知识库可答：检索本地 IoT 售后知识分块并带引用回答。
- 高风险问题：不强答，生成转人工工单草稿。
- 未命中资料：返回 `UNKNOWN`，提示人工复核。

## 核心模块

### Fast Router

位置：`ticket_service/agent.py`

作用：判断用户问题应该走哪条路线。比如“设备连不上了”太模糊，就进入追问；“GW-200 报 E104 且 MQTT 超时”比较具体，就进入知识库检索；出现“冒烟、赔偿、投诉、数据丢失”等词，直接转人工。

### Structured Planner

位置：`ticket_service/agent.py`

作用：把一次请求拆成固定步骤。当前最多 5 步：

```text
Fast Router -> Structured Planner -> Knowledge Search -> Capability Executor -> Verifier
```

这样做的好处是执行链稳定，便于调试和评测，不会把模型返回的一段文字直接当作任务完成。

### Knowledge Search

位置：`ticket_service/knowledge_base.py`

作用：读取 `data/processed/knowledge_chunks.csv`，做本地混合检索。

当前检索方式：

- 向量检索：使用 `TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4))`，适合中文短文本和错误码混合场景。
- 关键词加权：对 `GW-200`、`E104`、`MQTT` 等设备型号、错误码、协议词做额外加分。
- 融合排序：向量分数占 72%，关键词分数占 28%。
- 父子块动态路由：先在子块级别召回，再按父块聚合去重，证据里保留 `parent_id -> child_id` 路径。

这不是大型生产级向量库，但适合个人项目展示“分块、检索、引用、评测”的完整 RAG 思路。后续可以替换成 PostgreSQL + pgvector。

### Agent Memory

位置：`ticket_service/agent_memory.py`

作用：保存同一 `session_id` 下的短期上下文。比如用户第一轮只说设备型号 `GW-200`，第二轮补充错误码 `E104`，第三轮补充网络是 `4G`，Agent 会把这些字段合并后再判断路由。

当前策略：

- 默认使用进程内 memory，方便本地演示。
- 配置 `AGENT_MEMORY_REDIS_URL` 后使用 Redis。
- 保存设备型号、固件版本、错误码、在线状态、网络类型、MQTT 状态等结构化事实。
- 保存最近 20 轮对话摘要，避免会话无限膨胀。

### Capability Executor

位置：`ticket_service/agent.py`、`ticket_service/troubleshooting.py`

作用：执行工具能力。当前注册的能力包括：

- 本地知识库检索
- 轻量多轮排障树
- 转人工工单草稿生成

这里的“工具调用”是确定性的 Python 函数调用，不是让 LLM 自己随便调用外部接口。

### MCP Server

位置：`ticket_service/mcp_server.py`

作用：基于官方 `mcp` Python SDK，把项目里的 Agent、知识库检索和工单能力暴露为标准 MCP 工具。

当前支持：

- `agent_respond`：执行 Agent 主链路，包含 memory、RAG、追问和转人工。
- `knowledge_search`：执行本地 IoT 知识库父子块检索。
- `ticket_create`：创建转人工工单。
- `iot://knowledge/summary`：知识库统计资源。
- `iot_support_prompt`：IoT 售后支持 Prompt 模板。

运行方式：

```powershell
.\.venv\Scripts\python.exe -m ticket_service.mcp_server --transport stdio
.\.venv\Scripts\python.exe -m ticket_service.mcp_server --transport streamable-http --host 127.0.0.1 --port 8010 --path /mcp
```

这让项目从“普通后端接口”进一步变成“可被 MCP 客户端发现和调用的 Agent 工具服务”。`ticket_service/mcp.py` 中的 JSON-RPC 入口只作为普通 HTTP 兼容层保留，不作为项目主 MCP 实现。

### SSE Streaming

位置：`ticket_service/main.py`

作用：提供 `GET /agent/respond/stream`。前端可以先收到 `step` 事件，再收到最终 `result` 事件，用来演示 Agent 不是一次性黑盒返回，而是有可观察的执行过程。

### Verifier

位置：`ticket_service/agent.py`

作用：检查输出是否有证据、是否高风险、是否信息不足，并给出结构化状态：

- `COMPLETE`：证据足够，可以直接回答。
- `PARTIAL`：有一定证据，但需要人工复核或存在高风险。
- `UNKNOWN`：知识库未命中可靠资料，不强答。
- `INCOMPLETE`：用户信息不足，先追问。

## 主链路实现

- 本地知识库检索由 `ticket_service/knowledge_base.py` 完成。
- Agent 编排由 `ticket_service/agent.py` 完成。
- MCP Server 由 `ticket_service/mcp_server.py` 完成。
- 工单闭环由 FastAPI + PostgreSQL/SQLite 完成。

简历上更稳的说法是：

```text
使用 Python/FastAPI 实现 IoT 售后 Agent 主链路，设计 Fast Router、Structured Planner、本地混合检索、轻量排障树、MCP Server、Verifier 和工单闭环。
```

## 当前边界

当前项目已经实现轻量 Agent 编排、会话记忆、父子块路由、SSE 流式输出和官方 MCP SDK 工具服务，但还没有实现以下重型能力：

- HMAC 工具审批
- Kafka 异步任务队列
- Neo4j 知识图谱
- Elasticsearch 生产级全文检索

这些可以作为后续升级方向，但不要在简历里写成已经完成。
