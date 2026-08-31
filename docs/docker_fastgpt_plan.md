# Docker and FastGPT Plan

## 当前结论

FastGPT 是本项目的外部 RAG / Workflow 运行平台，不是本仓库源码的一部分。

当前目录边界：

```text
D:\pycmexercise\
├─ agentx2\             # 本项目仓库
└─ fastgpt-runtime\     # FastGPT 独立运行目录
```

不要把 `FastGPT-main` 复制进 `D:\pycmexercise\agentx2`。这样可以保证你的个人项目边界清晰，别人看仓库时能看到你的数据集、工单服务、诊断逻辑、评测脚本和接入文档，而不是一个大型开源项目源码包。

## Docker 使用情况

本项目自己的 FastAPI 服务不跑在 Docker 里，使用本地 Python 虚拟环境启动。

FastGPT 使用 Docker Compose 运行，当前已启动：

- FastGPT Web
- AIProxy
- MongoDB
- Redis
- PostgreSQL / pgvector
- MinIO
- Plugin / Sandbox / MCP 辅助服务

当前 FastGPT 地址：

```text
http://localhost:3000
```

本项目工单服务地址：

```text
http://127.0.0.1:8000
```

如果 FastGPT 容器里要访问本机工单服务，使用：

```text
http://host.docker.internal:8000/tickets/create
```

## Docker 磁盘

你已把 Docker Desktop 的 Disk image location 迁到 E 盘。Docker CLI 里显示的 `DockerRootDir=/var/lib/docker` 是容器/WSL 内部路径，不代表宿主机又占回 C 盘。

Kaiwu 相关 Docker 资源已经清理。旧 Kaiwu 镜像最多会占磁盘、CPU、内存或端口；Docker 拉取超时更常见原因是网络、镜像仓库、代理、DNS 或 Docker Desktop 网络状态。

## FastGPT 已完成事项

- 已整理独立 compose：`D:\pycmexercise\fastgpt-runtime\docker-compose.yml`
- 已启动 FastGPT
- 已配置 DeepSeek 与百炼模型渠道
- 已创建知识库：`IoT 设备售后知识库`
- 已创建集合：`IoT 售后知识分块`
- 已导入 `data/processed/knowledge_chunks.csv`
- 已入库 124 条知识数据
- 已创建应用：`IoT Support Copilot`
- 已验证 FastGPT 搜索接口能召回 IoT 售后片段

## 可复现命令

启动 FastGPT：

```powershell
cd D:\pycmexercise\fastgpt-runtime
docker compose up -d
```

导入知识库：

```powershell
cd D:\pycmexercise\agentx2
.\.venv\Scripts\python.exe scripts\import_fastgpt_dataset.py
```

创建应用：

```powershell
.\.venv\Scripts\python.exe scripts\create_fastgpt_app.py
```

演示 RAG 到工单闭环：

```powershell
.\.venv\Scripts\python.exe scripts\fastgpt_ticket_flow_demo.py "客户要求赔偿停机损失，现场设备冒烟并且历史数据全部丢失，应该怎么答？"
```
