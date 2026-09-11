# Model Config

本项目接入两个大模型提供方和一个联网检索工具：

- DeepSeek：可选生成模型，本地 RAG 脚本可使用 `deepseek-chat` 对检索证据进行回答润色。
- 阿里云百炼：OpenAI-compatible 生成模型与向量模型，可作为备用 LLM 或后续 pgvector 向量化来源。
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

## 当前使用方式

主服务 `ticket_service` 默认使用确定性 Python Agent 和本地知识库检索，不要求必须配置大模型密钥。

如果要演示“大模型基于证据生成回答”，可以运行：

```powershell
.\.venv\Scripts\python.exe scripts\ask_rag.py "GW-200 报 E104 且 MQTT 连接超时，应该怎么排查？" --provider deepseek
```

如果要启用联网补充检索，可以加：

```powershell
.\.venv\Scripts\python.exe scripts\ask_rag.py "MQTT TLS 证书过期如何排查？" --provider deepseek --web
```
