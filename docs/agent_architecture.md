# Python Agent 主链路说明

这个项目的主链路是 LangGraph 实现的 ReAct Agent 服务。它不是像 n8n 一样固定跑完所有节点，而是由 DeepSeek 或百炼根据每轮 Observation 返回真实 `tool_calls`，动态决定下一步是读取记忆、检查信息、检索知识库、生成工单还是提交最终结论。

## 为什么叫 Agent

普通 RAG 问答通常是：

```text
用户问题 -> 知识库检索 -> 大模型回答
```

本项目的 ReAct Agent 链路是：

```text
用户问题
  -> LLM Planner
  -> Tool Call: read_session_memory / inspect_support_context / search_iot_knowledge / draft_support_ticket
  -> Observation
  -> LLM Planner
  -> ...
  -> finalize_support_response / Verify
```

也就是说，系统不是只做“检索 + 回答”，而是会根据不同情况选择不同动作：

- 信息不足：先追问设备型号、错误码、网络类型、在线状态等字段。
- 知识库可答：检索本地 IoT 售后知识分块并带引用回答。
- 高风险问题：不强答，生成转人工工单草稿。
- 未命中资料：返回 `UNKNOWN`，提示人工复核。

## 核心模块

### ReAct Executor

位置：`ticket_service/langgraph_agent.py`

作用：用 `StateGraph` 编排 `planner -> tools -> planner` 循环。Planner 调用真实 LLM，Tool Executor 执行模型选择的 Python 工具，并以 `role=tool` 将观察结果送回模型。比如“设备连不上了”可先检查缺失字段再追问；“GW-200 报 E104 且 MQTT 超时”会检索知识库再提交带引用回答；出现“冒烟、赔偿、投诉、数据丢失”等词时，程序校验器要求先生成工单再转人工。

提供给模型的工具：

- `read_session_memory`
- `inspect_support_context`
- `search_iot_knowledge`
- `draft_support_ticket`
- `finalize_support_response`

返回结果里的 `react_trace` 只记录可审计的规划摘要、工具名、输入和 Observation，不记录或伪造模型隐藏思维过程。`ticket_service/react_agent.py` 中原有确定性执行器仍保留，作为无密钥、超时或模型失败时的 fallback。

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

### Capability Tools

位置：`ticket_service/langgraph_agent.py`、`ticket_service/troubleshooting.py`、`ticket_service/knowledge_base.py`

作用：给 ReAct Executor 调用的确定性工具能力。当前注册的能力包括：

- 本地知识库检索
- 轻量多轮排障树
- 转人工工单草稿生成

工具本身是确定性 Python 函数，工具选择由 LLM 通过 OpenAI-compatible `tool_calls` 完成。两者分开后，模型负责规划，代码负责执行权限和数据边界。

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

位置：`ticket_service/langgraph_agent.py`

作用：检查输出是否有证据、是否高风险、是否信息不足，并给出结构化状态：

- `COMPLETE`：证据足够，可以直接回答。
- `PARTIAL`：有一定证据，但需要人工复核或存在高风险。
- `UNKNOWN`：知识库未命中可靠资料，不强答。
- `INCOMPLETE`：用户信息不足，先追问。

## 主链路实现

- 本地知识库检索由 `ticket_service/knowledge_base.py` 完成。
- LangGraph 编排与工具校验由 `ticket_service/langgraph_agent.py` 完成，`ticket_service/react_agent.py` 提供离线回退。
- MCP Server 由 `ticket_service/mcp_server.py` 完成。
- 工单闭环由 FastAPI + PostgreSQL/SQLite 完成。

简历上更稳的说法是：

```text
使用 LangGraph + DeepSeek/百炼 Tool Calling 实现 IoT 售后 ReAct Agent 主链路，设计动态工具选择、本地混合检索、轻量排障树、Redis 会话记忆、MCP Server、Verifier、失败降级和工单闭环。
```

## 当前边界

当前项目已经实现 LangGraph 状态图、真实 LLM Tool Calling、会话记忆、父子块路由、SSE 输出和官方 MCP SDK 工具服务，但还没有实现以下重型能力：

- HMAC 工具审批
- Kafka 异步任务队列
- Neo4j 知识图谱
- Elasticsearch 生产级全文检索
- PostgreSQL/Redis 持久化 LangGraph Checkpoint（当前 Graph Checkpoint 在进程内，业务会话记忆可使用 Redis）

这些可以作为后续升级方向，但不要在简历里写成已经完成。
