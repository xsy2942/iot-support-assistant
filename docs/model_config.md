# Model Config

本项目接入两个大模型提供方和一个联网检索工具：

- DeepSeek：默认 Agent 模型，使用 `deepseek-chat` 的标准 Tool Calling 决定下一项工具。
- 阿里云百炼：OpenAI-compatible 备用 Agent 模型，默认使用 `qwen-plus`。
- Tavily：联网检索工具，用于补充公开资料，不替代本地 IoT 售后知识库。

## 本地密钥

密钥只放在本地 `.env`，不要提交到 Git。

```env
DEEPSEEK_API_KEY=你的 DeepSeek API Key
DEEPSEEK_TRACKING_ID=你的 Tracking ID
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat

BAILIAN_API_KEY=你的百炼 API Key
BAILIAN_BASE_URL=https://your-workspace.cn-beijing.maas.aliyuncs.com/compatible-mode/v1
BAILIAN_MODEL=qwen-plus
BAILIAN_EMBEDDING_MODEL=text-embedding-v4

AGENT_MODE=auto
AGENT_PROVIDER=deepseek
AGENT_MODEL_TIMEOUT_SECONDS=45
AGENT_MODEL_MAX_TOKENS=900
AGENT_MODEL_MAX_RETRIES=1

TAVILY_API_KEY=你的 Tavily API Key
TAVILY_BASE_URL=https://api.tavily.com
```

`.env` 已写入 `.gitignore`，不会被提交。

## 连通性检查

```powershell
.\.venv\Scripts\python.exe scripts\check_deepseek.py
.\.venv\Scripts\python.exe scripts\check_bailian.py
.\.venv\Scripts\python.exe scripts\check_tavily.py
```

## Agent 运行方式

主服务通过 `AGENT_MODE` 选择运行时：

- `auto`：有模型密钥时运行 LangGraph + LLM Tool Calling，否则使用确定性回退。
- `langgraph`：必须使用所选模型，适合联调和演示。
- `deterministic`：完全离线，适合单元测试和检索基线评测。

FastAPI、官方 MCP Server 和命令行脚本共用同一个 Agent 工厂，不会出现三套不同编排逻辑。

直接验证真实 LangGraph Agent：

```powershell
.\.venv\Scripts\python.exe scripts\ask_langgraph_agent.py "GW-200 报 E104 且 MQTT 连接超时，应该怎么排查？" --provider deepseek --device-model GW-200 --error-code E104
```

返回中的 `runtime` 应为 `langgraph-tool-calling`；若模型调用失败后降级，则为 `deterministic-fallback`，并在 `fallback_reason` 中给出不含密钥的失败类型。

## 独立 RAG 脚本

如果要演示“大模型基于证据生成回答”，可以运行：

```powershell
.\.venv\Scripts\python.exe scripts\ask_rag.py "GW-200 报 E104 且 MQTT 连接超时，应该怎么排查？" --provider deepseek
```

如果要启用联网补充检索，可以加：

```powershell
.\.venv\Scripts\python.exe scripts\ask_rag.py "MQTT TLS 证书过期如何排查？" --provider deepseek --web
```
