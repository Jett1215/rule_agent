# AgentRuler 后端开发

后端包名为 `agentruler`，使用 FastAPI、SQLModel、LangChain，提供对话流、Agent/技能、知识库、MCP、工作空间及用量统计。工程规则见 [AGENTS.md](../../AGENTS.md)，架构和各类参考文档见 [文档索引](../../docs/README.md)。

本页环境、代码入口与配置说明以 2026-10-21 的静态检查为基线；后续定向验证及其范围以[验证报告](../../docs/verification-report.md)为准。

## 环境与配置

`pyproject.toml` 要求 Python `>=3.12`；Docker 使用 Python 3.12。项目含 Python 3.12 语法，不应使用系统旧版本解释器判断项目语法是否有效。依赖以 `pyproject.toml` 和 `uv.lock` 为锁定安装入口。

首次从项目根目录执行；已有配置不要重复覆盖：

```bash
cd src/backend
uv sync --frozen
cp -n agentruler/config.example.yaml agentruler/config.yaml
chmod 600 agentruler/config.yaml
```

安装后在本机编辑 `agentruler/config.yaml`。配置字段以 [本地模板](agentruler/config.example.yaml) 为准，不复制真实配置到文档、聊天或提交中。详见 [配置与 Git](../../docs/configuration-and-git.md)。

| 配置 | 启动和使用条件 |
| --- | --- |
| `mysql.endpoint`、`mysql.async_endpoint` | 同一 MySQL 库的同步与异步连接；现有库名 `agentchat` 保留；本地模板默认 `localhost:3306`，连接开发 Compose 的宿主机端口时改为 `127.0.0.1:3307` |
| `redis.endpoint` | Redis 地址；当前 Compose 使用 Redis 7 |
| `multi_models` | 对话、工具、推理、视觉、图像、Embedding 和 Rerank 分别配置；模型名称、权限及配额需在实际环境确认 |
| `storage.mode` 与 `storage.minio` / `storage.oss` | 按所选后端配置对象存储，文件与默认头像初始化会用到存储 |
| `rag.vector_db` | 按需要选择 `chroma`、`lite` 或 `standalone`；Compose 没有启动 Milvus 或 Elasticsearch 服务 |
| `rag.enable_elasticsearch` | 未部署 Elasticsearch 时保持禁用 |
| `tools` | 按启用的工具配置相应服务密钥 |
| `jev` | 可选决策层，模板默认 `disabled`；见 [Jev 说明](../../docs/jev-integration.md) |

YAML 不会自动展开 `${...}`。JWT 配置另由 `agentruler/api/JWT.py` 的 `BaseSettings` 读取；通过受控环境注入 `AUTHJWT_SECRET_KEY`，不要沿用代码中的开发默认值。开发 Compose 目前没有把这个变量传给后端，采用容器开发时需自行补充本地 Compose override；生产 Compose 已要求该变量。不要在终端打印环境变量或完整渲染后的 Compose 配置。

部分文件转换和截图工具还依赖 Pandoc、Chromium/ChromeDriver 及系统库。完整系统依赖见 [生产 Dockerfile](../../docker/Dockerfile.production) 和 [开发 Dockerfile](../../docker/Dockerfile)；本机只安装 Python 包不等于这些工具已经可用。

## 启动与初始化边界

必须以 `src/backend` 为工作目录，配置和初始化 JSON 都使用相对路径：

```bash
uv run --frozen uvicorn agentruler.main:app --host 127.0.0.1 --port 7860
```

需要其他设备访问时，按实际开发网络调整监听地址。CLI 的 `--host` / `--port` 决定 Uvicorn 监听地址；修改 YAML 的 `server.host` / `server.port` 不会自动覆盖本命令。

启动生命周期先加载配置，再执行 `init_agentruler_system()`。它会尝试创建数据库和缺失表，并按已有 Agent 情况初始化默认工具、LLM、MCP、Agent 和头像，或更新已有 LLM/MCP 配置；可能访问模型、MCP、图片源和对象存储，也可能写入数据库。因此不要把启动服务当成只读检查，首次试运行使用隔离数据库和存储。`create_all` 不负责已有表的字段变更，结构升级必须另行审查并在备份后演练。初始化会捕获并记录部分错误，进程存活不能证明初始化完整成功。

启动后的检查入口：

- `http://localhost:7860/health`：当前仅返回 `{"status":"OK"}`，不探测数据库、Redis、模型或对象存储健康。
- `http://localhost:7860/docs`：FastAPI 接口文档；访问及调试仍需满足实际接口鉴权要求。
- 前端开发启动见 [前端 README](../frontend/README.md)。`scripts/start.py` 只在项目根目录查找 Python requirements，而依赖文件实际在本目录，不能依赖该脚本完成后端安装。

## 代码入口与扩展

| 路径 | 职责 |
| --- | --- |
| `agentruler/main.py`、`settings.py` | FastAPI 生命周期、配置加载和中间件 |
| `agentruler/api/v1/`、`api/services/` | HTTP 参数、响应及业务服务；`api/v1/router.py` 聚合 `/api/v1` 路由 |
| `agentruler/api/mcp_proxy/`、`mcp_proxy/` | MCP 代理路由、协议和会话处理 |
| `agentruler/auth/`、`api/JWT.py` | 仓库内 JWT 实现及应用配置 |
| `agentruler/core/agents/`、`core/models/` | Agent 执行、LangChain 适配与模型创建 |
| `agentruler/database/models/`、`database/dao/` | SQLModel 模型与数据访问，同步和异步路径并存 |
| `agentruler/services/` | RAG、MCP、存储、工作空间等服务 |
| `agentruler/tools/` | 内置工具及 `AgentToolsWithName` 等映射 |
| `agentruler/test/` | 定向自动化测试和历史联调示例混合目录 |

添加接口时同步维护路由注册、请求响应模型、用户与资源权限、错误处理及 [API 参考](../../docs/reference/api.md)。Agent 实现的调用约定并不统一，按目标调用链核对 `ReactAgent`、`MCPAgent`、`SkillAgent` 等实现，不能假设存在统一的 `BaseAgent.run` 扩展协议。新增工具需核对实际工具映射与使用方；新增模型需确保导入元数据并评估表结构变更。数据库约定见 [数据库参考](../../docs/reference/database.md)。

当前认证来自仓库内 `agentruler/auth`，无需执行旧 `fastapi-jwt-auth` 修复脚本。JWT 支持 Header 和 Cookie，应用关闭 Cookie CSRF 保护；具体接口是否认证、对象归属检查是否完整，以路由依赖与服务实现为准。白名单中间件不会统一为所有接口补齐鉴权，例如 `PUT /api/v1/user/update`、`GET /api/v1/user/info` 当前没有 `get_login_user` 依赖。发布前应按 [测试计划](../../docs/test-plan.md) 核查权限，不能宣称全部接口已受保护。

## 测试与验证

当前测试路径是 `agentruler/test/`。不要使用旧文档的 `pytest test/`，也不要直接对整个目录执行 pytest 或 unittest discovery：其中含真实外部服务调用、旧包名导入和顶层执行示例；`test_config.py` 还会打印配置中的秘密。先阅读目标文件及导入链，限定模块和隔离配置。

以下命令在 `src/backend`、Python 3.12 与锁定依赖已准备好的环境中执行。按静态检查，所列测试使用 mock/临时数据隔离对应逻辑；是否通过仍需实际执行并记录：

```bash
uv run --frozen python -m unittest agentruler.test.test_generated_mcp_schema
uv run --frozen python -m unittest agentruler.test.test_jev_decisions
uv run --frozen python -m unittest agentruler.test.test_jev_middleware
uv run --frozen python -m unittest agentruler.test.test_jev_workspace
```

覆盖内容分别为生成 MCP schema、Jev 协议与降级、LangChain 中间件、工作空间门控及事件流；它们不代表真实数据库、真实模型或浏览器流程验收。

`test_agent_skill_creation` 与 `test_workspace_mcp_arguments` 也可用同样的模块命令定向运行，但它们在 `asyncSetUp` 调用 `init_app_settings()`，会读取默认 `agentruler/config.yaml`，并加载较多生产模块。只有准备好脱敏隔离配置、核查存储/模型模块构造及外部调用条件后再执行。不要把真实生产配置作为测试输入。

2026-10-21 文档整理时，上述检查均为 `NOT_RUN`。2026-10-27 已执行 Jev 三组定向测试，共 31 项通过；测试使用受控 HTTP 响应和隔离的数据库/插件边界，不代表真实 Jev 服务或完整业务验收通过。实际环境、命令与验证边界见[单变量开关验证记录](../../docs/verification-report.md#2026-10-27-jev-单变量开关)；其他检查的执行状态仍以[验证报告](../../docs/verification-report.md)为准，验证方法与前置条件见[测试计划](../../docs/test-plan.md)。

## 部署与排查

容器启动、端口和数据持久化见 [Docker 指南](../../docker/README.md)，云端历史部署与备份恢复见 [云部署说明](../../docs/cloud-deployment.md)。生产 Dockerfile 使用单个 Uvicorn worker，未配置 Gunicorn/Supervisor。

排查顺序：确认工作目录和 Python 版本；确认模板字段与连接地址；查看经脱敏的启动错误；检查依赖服务；再针对模型、MCP、存储或工具做最小联调。日志、异常体和配置可能包含敏感值，分享前先脱敏。现有项目没有统一的全异步保证或已验证的性能容量结论。
