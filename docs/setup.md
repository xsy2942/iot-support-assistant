# Setup

## 环境位置

当前项目目录：

```text
D:\pycmexercise\agentx2
```

当前项目自己的环境与数据：

- Git 仓库：`D:\pycmexercise\agentx2\.git`
- Python 虚拟环境：`D:\pycmexercise\agentx2\.venv`
- Python 依赖：`D:\pycmexercise\agentx2\.venv\Lib\site-packages`
- 本地密钥：`D:\pycmexercise\agentx2\.env`
- PostgreSQL 工单数据库：通过 `.env` 里的 `TICKET_DB_URL` 连接
- Redis 排障上下文：通过 `.env` 里的 `TROUBLESHOOTING_REDIS_URL` 连接
- Redis Agent 记忆：通过 `.env` 里的 `AGENT_MEMORY_REDIS_URL` 连接
- SQLite 兜底数据库：`D:\pycmexercise\agentx2\data\generated\tickets.sqlite3`

当前项目没有使用 `D:\pycmexercise\ai-recruit-agent-main` 里的环境或工具。

## 已用工具

| 工具 | 用途 |
|---|---|
| Git | 项目版本管理 |
| Python 3 | 数据生成、评测脚本、FastAPI 工单服务 |
| FastAPI / Uvicorn | 本地工单服务与中文前端托管 |
| MCP Python SDK | 独立 MCP Server，暴露 Agent、知识库检索和工单工具 |
| PostgreSQL | 工单与反馈主存储 |
| Redis | 多轮排障与 Agent 记忆短期上下文，可选启用 |
| SQLite | 本地测试或未配置 PostgreSQL 时的兜底存储 |
| Docker Desktop / Docker Compose | 可选运行 PostgreSQL / Redis 等本地基础服务 |
| DeepSeek API | RAG 回答生成 |
| 阿里云百炼 API | LLM 备用与 Embedding |
| Tavily API | 联网检索补充 |

## 本地 Python 环境

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

如果 PowerShell 阻止激活脚本：

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

## 启动本项目服务

如果要使用 PostgreSQL，先在 `.env` 中配置：

```text
TICKET_DB_URL=postgresql://postgres:postgres@localhost:5432/iot_support_assistant
```

如果 `TICKET_DB_URL` 为空，服务会自动使用 SQLite 兜底，便于测试和离线演示。

如果要保存多轮排障上下文，再配置：

```text
TROUBLESHOOTING_REDIS_URL=redis://localhost:6379/0
TROUBLESHOOTING_SESSION_TTL_SECONDS=172800
AGENT_MEMORY_REDIS_URL=redis://localhost:6379/0
AGENT_MEMORY_TTL_SECONDS=172800
```

如果 `TROUBLESHOOTING_REDIS_URL` 为空，排障接口仍可无状态运行。

```powershell
.\.venv\Scripts\python.exe -m uvicorn ticket_service.main:app --reload --host 127.0.0.1 --port 8000
```

访问：

- 前端页面：[http://127.0.0.1:8000/](http://127.0.0.1:8000/)
- API 文档：[http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- 健康检查：[http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)

## MCP Server 运行方式

标准输入输出模式，适合被 MCP 客户端直接启动：

```powershell
.\.venv\Scripts\python.exe -m ticket_service.mcp_server --transport stdio
```

HTTP 模式，适合本地调试或 MCP Inspector 连接：

```powershell
.\.venv\Scripts\python.exe -m ticket_service.mcp_server --transport streamable-http --host 127.0.0.1 --port 8010 --path /mcp
```

MCP Server 暴露的工具：

- `agent_respond`
- `knowledge_search`
- `ticket_create`

MCP Server 暴露的资源和 Prompt：

- `iot://knowledge/summary`
- `iot_support_prompt`

## 端口规划

| 端口 | 服务 |
|---:|---|
| 8000 | 本项目 FastAPI 工单服务 |
| 8010 | 本项目 MCP Streamable HTTP 服务 |

## Docker 磁盘说明

本项目主链路不依赖 Docker。Docker 只在你想本地启动 PostgreSQL、Redis 或其他基础服务时使用。

你已经把 Docker Desktop 的 Disk image location 尽量迁到 E 盘。`docker info` 中的 `DockerRootDir=/var/lib/docker` 是 Docker Linux 虚拟机内部路径，不等于宿主机 C 盘路径。

需要区分：

- Docker 镜像和 named volume：存在 Docker Desktop 的磁盘镜像里，宿主机落点由 Disk image location 决定。
- bind mount：例如把 `D:\xxx` 挂到容器里，真实文件就在 D 盘。
- 本项目源码和 Python 虚拟环境：仍在 `D:\pycmexercise\agentx2`。

## 旧容器说明

Kaiwu 相关容器、镜像和卷已经清理。当前 Docker 中还能看到停止状态的 `recruit-rabbitmq`、`recruit-redis`，它们属于旧招聘项目，不是本项目新建服务；我没有自动删除它们。
