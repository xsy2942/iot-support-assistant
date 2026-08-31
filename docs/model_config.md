# Model Config

本项目接入两个大模型提供方和一个联网检索工具：

- DeepSeek：默认生成模型，当前 FastGPT 应用使用 `deepseek-chat`。
- 阿里云百炼：OpenAI-compatible 生成模型与向量模型，当前知识库使用 `text-embedding-v4`。
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

## FastGPT 模型配置

FastGPT 的 AIProxy 已配置两个模型渠道：

- `DeepSeek IoT Chat`：`deepseek-chat`
- `Bailian IoT Chat & Embedding`：`qwen-plus`、`text-embedding-v4`

FastGPT 系统模型表中已启用：

- `deepseek-chat`：LLM
- `qwen-plus`：LLM
- `text-embedding-v4`：Embedding

知识库向量模型使用 `text-embedding-v4`，应用回答模型使用 `deepseek-chat`。
