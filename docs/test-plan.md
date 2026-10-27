# 测试与验证计划

基线日期：2026-10-21。本文给出方法和候选命令；实际执行结果只记录在[验证报告](verification-report.md)。当前没有声称全项目通过测试。业务验收条目见[验收标准](acceptance-criteria.md)，正式优先级与性能门槛待确认。

## 执行条件与边界

后端使用项目 Python 3.12+ 与对应依赖，工作目录为 `src/backend`；不能使用较旧解释器的解析失败判断项目代码错误。前端使用锁文件对应依赖，工作目录为 `src/frontend`。环境安装和配置见各自 README。

定向 Mock 测试仍可能在导入阶段加载设置、数据库、存储或可选插件，必须先阅读目标测试及导入路径，确认所需的脱敏配置和隔离边界。真实服务测试需使用专用用户、测试库、桶和向量目录，并先明确可能产生的写入、费用及清理范围。

不默认执行后端全目录 `pytest` 或 `unittest discover`：现有目录包含外部服务示例、旧模块导入和顶层代码；`test_config.py` 还会输出配置值。先分类并建立隔离条件，再决定完整测试入口。

## 可定位的现有自动化测试

下表列出可定位的执行入口；已执行的子集、环境及结果见[验证报告](verification-report.md)，后续按任务范围复用证据。“Mock”表示测试隔离部分服务，不意味着已经验证真实环境。

| 组 ID | 关联需求 | 命令或脚本 | 静态可见覆盖范围与限制 |
| --- | --- | --- | --- |
| TEST-FE-001 | REQ-004、REQ-007 | 前端目录 `npm test` | `tests/session-id.test.cjs`；HTTP 的 UUID 回退和 HTTPS 原生分支，不覆盖页面流程 |
| TEST-BE-001 | REQ-006 | `python -m unittest agentruler.test.test_weather_response` | 天气响应、缺参、超时及异常，Mock HTTP |
| TEST-BE-002 | REQ-005 | `python -m unittest agentruler.test.test_chunk_browser` | 使用真实临时 Chroma 测试分页、搜索、向量和导出，API 依赖使用桩；覆盖部分跨用户拒绝 |
| TEST-BE-003 | REQ-003 | `python -m unittest agentruler.test.test_agent_skill_creation` | Skill 创建的结构化调用和失败分支；Mock 模型、存储和数据库 |
| TEST-BE-004 | REQ-006、REQ-007 | `python -m unittest agentruler.test.test_workspace_mcp_arguments` | 直接测试可见参数辅助方法的固定 query 合并和脱敏；不覆盖完整事件生命周期或真实 MCP 服务 |
| TEST-BE-005 | REQ-006 | `python -m unittest agentruler.test.test_generated_mcp_schema` | 生成的工具 Schema 与 nullable 字段处理 |
| TEST-JEV-001 | REQ-010 | `python -m unittest agentruler.test.test_jev_decisions` | 门控、候选筛选、共用 `JEV_MODE` 与 YAML 优先级、空白/非法值、独立开关、禁用/观察/回退、用量与日志；Mock TypeSafe 请求 |
| TEST-JEV-002 | REQ-010 | `python -m unittest agentruler.test.test_jev_middleware` | 按轮筛选、原注册工具集保持、非法候选与回退 |
| TEST-JEV-003 | REQ-007、REQ-010 | `python -m unittest agentruler.test.test_jev_workspace` | 工作台工具路径、上下文、事件与最终回答；隔离数据库和插件 |

测试文件位于[后端测试目录](../src/backend/agentruler/test/)与[前端测试目录](../src/frontend/tests/)。Jev 三组文件在文档整理开始时为未跟踪工作区内容。

## 前端静态检查与构建

在 `src/frontend` 分别执行并分别记录：

```bash
npm test
npm run lint
npm run build
```

`lint` 实际为 `vue-tsc --noEmit` 类型检查，没有因此提供 ESLint 或代码格式检查。`vite build` 成功也不能替代类型检查、页面行为或 API 集成验证。前端路由、SSE 解析和数据契约变化需增加相应人工或端到端回归。

后端当前没有在 `pyproject.toml` 声明统一 Ruff、Mypy、Pytest 配置或测试依赖组。需要接入时作为单独工程任务评估，不写成当前已具备的门禁。

## 集成与用户流程

从验收标准选取正式本期范围，以两个普通用户和一个管理员构造数据；记录各角色拥有的 Agent、知识库、对话及会话标识。优先覆盖：

1. 注册、登录、错误凭据和禁用用户；区分 HTTP 状态与业务错误。
2. 模型配置→Agent/Skill 绑定→建立对话→流式回答→查询历史，确认保存与展示对应。
3. 文件上传→解析状态→知识库检索→Chunk 查看/导出，验证跨用户和跨文件访问拒绝。
4. 内置工具和 MCP：参数正确、执行失败、超时、用户配置隔离；验证 MCP 入口的实际访问边界。
5. 工作台：首次会话、恢复、删除、多步工具、流式事件和断连；区分占位接口与真正保存路径。
6. 用量统计：按用户、模型、Agent、时间筛选，并核对失败记录与实际调用。

每个流程记录所用验收 ID、数据准备、操作、预期、实际、持久化检查和证据位置。当前没有已配置的 Playwright/Cypress 测试或可声称通过的完整端到端流水线；采用何种自动化工具另行决定。

## 访问控制专项

按项目状态 GAP-001～GAP-005，对无凭据、无效凭据、普通用户访问他人资源、白名单路径和 MCP 请求分别验证。重点核对 `user/update`、`user/info`、`knowledge/retrieval`、`history`、工作台 session 读取和 `check_auth()`；测试应验证拒绝访问且不返回数据、不写入他人记录。

这是目标行为的候选验收，不表示现有实现满足要求。发现失败时保存可复现证据，明确修复范围后处理，不在文档任务中直接改造鉴权。

## Jev 与非功能验证

Jev 依据[专项说明](jev-integration.md)使用同一中文任务集对照 disabled、observe、enforce，覆盖闲聊、单工具、多工具和依赖前次结果的后续请求。记录净成本、首段有效回复及总时长、任务完成、漏选与回退；观察模式不能证明节省，概率不能充当成功率。

性能、安全、可靠性、浏览器兼容及恢复目标均待确认。性能报告必须说明机器、服务、模型版本、数据规模、并发模型、样本量与分位数；不直接采用通用 Prompt 的 80% 覆盖率或任意延迟作为正式要求。恢复和回滚按[云部署说明](cloud-deployment.md)在隔离环境演练。

## 文档变更的验证

检查约定的 11 份新增文档、相对文件链接、需求与任务 ID、接口和模型引用、`git diff --check`，以及任务开始前已有非文档文件是否被改动。只检查 Markdown 的任务不要求启动服务或安装测试工具。

## 结果记录与处理

每项执行结果使用 `PASS`、`FAIL`、`BLOCKED` 或 `NOT_RUN`，附命令、工作目录、环境、退出码及脱敏证据。失败修复后执行受影响的回归；历史失败不能被删除。只有实际执行且满足对应预期的条目才可通过，未具备环境时记录缺少的条件。
