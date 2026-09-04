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
- SQLite 兜底数据库：`D:\pycmexercise\agentx2\data\generated\tickets.sqlite3`

当前项目没有使用 `D:\pycmexercise\ai-recruit-agent-main` 里的环境或工具。

## 已用工具

| 工具 | 用途 |
|---|---|
| Git | 项目版本管理 |
| Python 3 | 数据生成、评测脚本、FastAPI 工单服务 |
| FastAPI / Uvicorn | 本地工单服务与中文前端托管 |
| PostgreSQL | 工单与反馈主存储 |
| Redis | 多轮排障短期上下文，可选启用 |
| SQLite | 本地测试或未配置 PostgreSQL 时的兜底存储 |
| Docker Desktop / Docker Compose | 运行 FastGPT 及其依赖服务 |
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
TROUBLESHOOTING_SESSION_TTL_SECONDS=1800
```

如果 `TROUBLESHOOTING_REDIS_URL` 为空，排障接口仍可无状态运行。

```powershell
.\.venv\Scripts\python.exe -m uvicorn ticket_service.main:app --reload --host 127.0.0.1 --port 8000
```

访问：

- 前端页面：[http://127.0.0.1:8000/](http://127.0.0.1:8000/)
- API 文档：[http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- 健康检查：[http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)

## FastGPT 运行方式

FastGPT 放在当前项目旁边：

```text
D:\pycmexercise\fastgpt-runtime
```

启动：

```powershell
cd D:\pycmexercise\fastgpt-runtime
docker compose up -d
```

访问：

- FastGPT Web：[http://localhost:3000](http://localhost:3000)

当前 FastGPT 使用 Docker 运行，主要服务包括：

- `fastgpt-app`
- `fastgpt-aiproxy`
- `fastgpt-mongo`
- `fastgpt-redis`
- `fastgpt-pg`
- `fastgpt-minio`
- `fastgpt-plugin`
- sandbox / MCP 相关辅助服务

## 端口规划

| 端口 | 服务 |
|---:|---|
| 3000 | FastGPT Web |
| 3003 | FastGPT MCP Server |
| 3006 | FastGPT Agent Sandbox Proxy |
| 8000 | 本项目 FastAPI 工单服务 |
| 9000 / 9001 | FastGPT MinIO |

## Docker 磁盘说明

你已经把 Docker Desktop 的 Disk image location 尽量迁到 E 盘。`docker info` 中的 `DockerRootDir=/var/lib/docker` 是 Docker Linux 虚拟机内部路径，不等于宿主机 C 盘路径。

需要区分：

- Docker 镜像和 named volume：存在 Docker Desktop 的磁盘镜像里，宿主机落点由 Disk image location 决定。
- bind mount：例如把 `D:\xxx` 挂到容器里，真实文件就在 D 盘。
- 本项目源码和 Python 虚拟环境：仍在 `D:\pycmexercise\agentx2`。

## 旧容器说明

Kaiwu 相关容器、镜像和卷已经清理。当前 Docker 中还能看到停止状态的 `recruit-rabbitmq`、`recruit-redis`，它们属于旧招聘项目，不是本项目新建服务；我没有自动删除它们。
