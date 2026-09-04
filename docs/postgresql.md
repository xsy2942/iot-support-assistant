# PostgreSQL

本项目把 PostgreSQL 作为工单与反馈的主存储。SQLite 只保留为本地测试或未配置数据库时的兜底方案。

## 作用边界

PostgreSQL 在本项目中负责：

- 保存转人工工单
- 保存用户反馈
- 支持按状态、时间查询工单
- 为后续多用户、权限、统计报表扩展留空间

pgvector 的定位不同：

- 如果使用 FastGPT，知识库向量通常由 FastGPT 自己的 PostgreSQL / pgvector 容器管理。
- 本项目的工单表不需要 pgvector。
- 如果后续想自研知识库检索，可以在本项目 PostgreSQL 中启用 pgvector，新增 `knowledge_chunks` 向量表。

## 建库示例

确认本机 PostgreSQL 已启动后，创建数据库：

```sql
CREATE DATABASE iot_support_assistant;
```

如果后续要自研向量检索，可以进入该数据库后启用 pgvector：

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

当前工单服务不依赖 pgvector，普通 PostgreSQL 即可运行。

## 环境变量

在 `.env` 中配置：

```text
TICKET_DB_URL=postgresql://postgres:postgres@localhost:5432/iot_support_assistant
```

字段含义：

- `postgres`：数据库用户名
- `postgres`：数据库密码
- `localhost`：本机数据库地址
- `5432`：PostgreSQL 默认端口
- `iot_support_assistant`：项目数据库名

如果你的 PostgreSQL 用户名、密码或端口不同，需要按实际情况修改。

## 多项目是否冲突

同一台 PostgreSQL 可以给多个项目同时使用，只要每个项目使用不同的数据库名或不同的 schema，就不会互相覆盖。

连接串最后一段是数据库名：

```text
postgresql://postgres:密码@localhost:5432/iot_support_assistant
                                                ^^^^^^^^^^^^^^^^^^^^^
```

本项目建议使用独立数据库：

```text
iot_support_assistant
```

另一个项目可以使用自己的数据库名，例如：

```text
ai_recruit_agent
```

这样两个项目虽然都连接同一个 PostgreSQL 服务、同一个端口 `5432`、甚至同一个用户 `postgres`，但数据保存在不同数据库里，不会互相覆盖。

需要避免的是两个项目共用同一个数据库，并且表名也一样。例如两个项目都连到 `postgres` 数据库，并且都创建 `tickets`、`feedback` 这类表，就可能混在一起。

## 启动后检查

先检查数据库连接：

```powershell
.\.venv\Scripts\python.exe scripts\check_postgres.py
```

启动服务：

```powershell
.\.venv\Scripts\python.exe -m uvicorn ticket_service.main:app --reload --host 127.0.0.1 --port 8000
```

访问健康检查：

```text
http://127.0.0.1:8000/health
```

如果返回：

```json
{
  "status": "ok",
  "database": "postgresql"
}
```

说明当前服务正在使用 PostgreSQL。

如果返回：

```json
{
  "status": "ok",
  "database": "sqlite"
}
```

说明 `.env` 没有配置 `TICKET_DB_URL`，服务正在使用 SQLite 兜底。

## 后续 Redis 扩展

PostgreSQL 更适合保存长期数据，例如工单、反馈、用户、权限和统计报表。

Redis 更适合保存短期会话状态，例如：

- 多轮排障上下文
- 当前用户已经回答过哪些追问
- 临时 `session_id`
- 过期自动清理的客服会话

所以后续完整聊天记忆建议采用：

```text
Redis 保存短期会话上下文
PostgreSQL 保存长期工单和反馈记录
FastGPT / pgvector 保存知识库向量检索数据
```
