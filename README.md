# IoT Support Assistant

IoT 设备技术支持知识库与工单助手。

这是一个面向 IoT 设备售后场景的个人项目，重点覆盖设备离线、MQTT 连接超时、网关心跳丢失、固件升级失败、传感器采样异常、温湿度/振动/电压异常等问题。项目资产保留在本仓库内，FastGPT 只作为外部 RAG / Workflow 运行平台。

## 当前进度

已完成：

- 124 条 IoT 售后知识分块：FAQ、错误码说明、历史工单、产品手册。
- 60 条问答评测集与本地 RAG sanity check。
- 40 条遥测诊断样例与诊断评测脚本。
- FastAPI 工单服务：创建工单、查看工单、更新状态、记录反馈、输出评测报告。
- 中文前端 Dashboard：设备诊断、转人工工单、反馈和指标展示。
- 轻量多轮排障：用户描述不完整时先追问设备型号、错误码、在线状态、网络类型等关键信息。
- DeepSeek、阿里云百炼、Tavily 接入检查脚本。
- FastGPT 独立 Docker runtime，已创建 IoT 知识库并导入 124 条分块。
- FastGPT 应用 `IoT Support Copilot`，已连接 IoT 知识库与 DeepSeek 回答节点。
- 端到端演示脚本：FastGPT 检索 -> 低置信度/高风险判断 -> 本地工单创建。

## 技术栈

- Python 3 + FastAPI + Uvicorn + Pydantic
- PostgreSQL 工单存储，SQLite 仅作为本地测试兜底
- Redis 可选保存多轮排障短期上下文
- HTML / CSS / JavaScript 中文前端
- CSV / Markdown 领域数据集
- scikit-learn 本地 TF-IDF baseline 评测
- DeepSeek / 百炼 OpenAI-compatible API
- Tavily Web Search API
- Docker Compose 运行 FastGPT、MongoDB、Redis、PostgreSQL/pgvector、MinIO、AIProxy

## 本地启动

```powershell
.\.venv\Scripts\python.exe -m uvicorn ticket_service.main:app --reload --host 127.0.0.1 --port 8000
```

如需使用 PostgreSQL 作为工单数据库，在 `.env` 中配置：

```text
TICKET_DB_URL=postgresql://postgres:postgres@localhost:5432/iot_support_assistant
```

如需保存多轮排障上下文，在 `.env` 中配置：

```text
TROUBLESHOOTING_REDIS_URL=redis://localhost:6379/0
TROUBLESHOOTING_SESSION_TTL_SECONDS=1800
```

连接检查：

```powershell
.\.venv\Scripts\python.exe scripts\check_postgres.py
.\.venv\Scripts\python.exe scripts\check_redis.py
```

打开：

- 项目前端：[http://127.0.0.1:8000/](http://127.0.0.1:8000/)
- API 文档：[http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- 健康检查：[http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)

多轮排障接口：

- `POST /troubleshooting/next`：根据已知信息生成下一步追问或处理建议
- `POST /troubleshooting/create-ticket`：高风险或建议复核时创建工单

## 数据生成

```powershell
.\.venv\Scripts\python.exe scripts\generate_iot_data.py
.\.venv\Scripts\python.exe scripts\generate_telemetry_data.py
```

主要输出：

- `data/raw/faq.csv`
- `data/raw/error_codes.csv`
- `data/raw/historical_tickets.csv`
- `data/raw/manuals/*.md`
- `data/raw/telemetry_samples.csv`
- `data/processed/knowledge_chunks.csv`
- `eval/questions.csv`
- `eval/diagnostic_cases.csv`

## 本地评测

```powershell
.\.venv\Scripts\python.exe eval\run_eval.py
.\.venv\Scripts\python.exe eval\run_diagnostic_eval.py
```

报告输出：

- `reports/eval_report.json`
- `reports/diagnostic_eval_report.json`

当前本地评测是模拟数据 sanity check，指标偏理想；最终简历数字建议以 FastGPT 接入后真实 60 条问答复测结果为准。

## FastGPT 接入

FastGPT runtime 放在：

```text
D:\pycmexercise\fastgpt-runtime
```

本仓库不提交 FastGPT 源码。当前 FastGPT 已完成：

- Web 地址：[http://localhost:3000](http://localhost:3000)
- 知识库：`IoT 设备售后知识库`
- 知识集合：`IoT 售后知识分块`
- 导入数量：124 条
- 应用：`IoT Support Copilot`

重新导入知识库：

```powershell
.\.venv\Scripts\python.exe scripts\import_fastgpt_dataset.py
```

重新创建 FastGPT 应用：

```powershell
.\.venv\Scripts\python.exe scripts\create_fastgpt_app.py
```

演示 RAG 到工单闭环：

```powershell
.\.venv\Scripts\python.exe scripts\fastgpt_ticket_flow_demo.py "GW-200 报 E104 且 MQTT 连接超时，应该怎么排查？"
.\.venv\Scripts\python.exe scripts\fastgpt_ticket_flow_demo.py "客户要求赔偿停机损失，现场设备冒烟并且历史数据全部丢失，应该怎么答？"
```

更多说明见：

- [docs/setup.md](docs/setup.md)
- [docs/model_config.md](docs/model_config.md)
- [docs/postgresql.md](docs/postgresql.md)
- [docs/docker_fastgpt_plan.md](docs/docker_fastgpt_plan.md)
- [docs/fastgpt_workflow.md](docs/fastgpt_workflow.md)
- [docs/diagnostics.md](docs/diagnostics.md)
- [docs/troubleshooting.md](docs/troubleshooting.md)
- [docs/project_positioning.md](docs/project_positioning.md)
