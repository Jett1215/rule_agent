# AgentRuler 项目开发规则

AgentRuler（智治）是基于现有 AgentChat 项目演进的智能体应用平台。维护已有实现、数据和兼容性；不要把新会话当作从零开发。

## 开始工作

1. 检查 `git status --short`、当前分支和任务涉及的代码，保留用户已有修改与未跟踪文件。
2. 读取 [项目状态](docs/project-status.md)、[任务清单](docs/task-checklist.md)和对应的[实施计划](docs/implementation-plan.md)。
3. 按任务读取相关需求、验收标准、架构、接口、数据模型及 ADR；不必每次通读全部文档。
4. 说明本轮目标、修改范围和验证方式。文档与代码矛盾时先核实，不擅自覆盖既有工作。

## 代码结构与约定

- 后端为 Python 3.12+、FastAPI、SQLModel、LangChain；入口为 `src/backend/agentruler/main.py`。
- 后端依次查看 `api/v1/`（路由）、`api/services/`（业务）、`database/dao/`（数据访问）、`database/models/`（模型）；Agent、MCP、RAG 等能力分别位于 `core/`、`services/` 和 `mcp_proxy/`。遵循现有分层，避免把业务逻辑和数据库操作扩散到前端或路由。
- 前端为 Vue 3、TypeScript、Vite、Element Plus、Pinia；页面在 `src/frontend/src/pages/`，请求封装在 `apis/`、`utils/request.ts`，状态在 `store/`。
- Python 使用现有 snake_case 和类型标注；Vue/TypeScript 沿用相邻文件的组件、命名和格式约定。没有统一格式工具时不要批量格式化无关文件。
- 业务 JSON 响应沿用 `api/responses/builder.py`；流式接口分别维护其 SSE 事件结构，不套用普通 JSON 包装。错误既涉及 HTTP 状态也涉及业务状态，修改时核对调用方。
- 路由或模型中出现鉴权代码不等于完成资源所有权检查。变更用户数据、会话、知识库、工具及 MCP 时检查跨用户访问和异常路径；现有缺口见项目状态。
- 不凭空引入基类、架构层或新基础设施。新增依赖先说明必要性、兼容性与锁文件影响，遵守现有依赖管理方式。

## 开发与验证入口

下列命令均有工作目录要求。环境安装、配置条件和定向测试列表见[后端说明](src/backend/README.md)、[前端说明](src/frontend/README.md)和[测试计划](docs/test-plan.md)。

```bash
# 在 src/backend 中，使用项目 Python 3.12+ 环境
python -m uvicorn agentruler.main:app --host 127.0.0.1 --port 7860
python -m unittest agentruler.test.test_weather_response

# 在 src/frontend 中，已安装锁文件对应依赖
npm run dev
npm test
npm run lint
npm run build
```

- `npm run lint` 当前实际执行 `vue-tsc --noEmit`，属于类型检查；构建命令不替代类型检查。
- 后端测试目录混有实验脚本和外部调用示例，禁止未经检查就把全目录测试发现作为默认命令。特别是 `test_config.py` 含输出配置值的历史代码。
- 未建立统一后端 Lint、类型检查或 CI 门禁时，必须如实说明，不能声称已运行。
- 按变更执行必要的定向测试、类型检查、构建或回归；普通文档变更检查事实、链接和差异即可。新增业务逻辑覆盖关键分支、错误与权限场景；流式变更核对前后端事件和断连行为。
- 不把 Mock 测试当真实集成验证，不弱化有效断言规避失败，不把未执行检查记为通过。验证结果写明命令、环境、范围和证据。

## 配置、数据与操作边界

- 真实密钥与本机配置不入库；使用已提交的 `.example` 模板，具体见[配置与 Git](docs/configuration-and-git.md)。不要将配置值、Token、原始敏感消息写入日志、测试报告或文档。
- 不覆盖已有 `config.yaml`、Docker 本机 YAML、`.env` 或数据目录。不要仅为调查或导出文档启动应用：启动过程会初始化数据库并可能更新默认配置数据、访问外部服务。
- `SQLModel.metadata.create_all()` 不会完成已有表字段变更。数据库变化先说明兼容性、迁移、备份、恢复和验证方案；不得假定重启即完成迁移。
- Python 包名为 `agentruler`；已有数据库、对象桶等兼容标识保留 `agentchat`。生产 Compose 项目标识及数据卷规则见[名称变更](docs/renaming.md)。
- 普通、可逆且处于用户授权范围内的修改可继续完成；生产部署、生产数据破坏性变更、大规模删除覆盖、权限扩大、重大架构调整和高成本外部服务决策须有明确授权。现有缺陷不自动授权无关改造。
- 不擅自提交、推送、发布或重置用户工作区。Git 历史与推送范围遵守配置文档中的仓库约束。

## 文档与会话交接

完整入口为 [docs/README.md](docs/README.md)。需求、验收、架构、API、数据库、任务状态和验证各有维护位置，避免复制第二份独立事实。

重要任务结束或中断时更新任务清单与项目状态；验证结论变化时更新验证报告；需求、接口、数据结构变化时同步对应文档。具有长期影响的新架构决定使用 [ADR](docs/adr/README.md)，不编造历史决策理由。

交接说明实际完成内容、重要文件、检查结果、未解决问题和下一步。`DONE` 只表示对应任务完成条件满足；代码存在、测试文件存在和功能验收通过是不同状态。
