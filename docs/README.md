# AgentRuler 工程文档导航

本目录记录已有项目的当前实现、开发约定、后续任务和验证证据。2026-10-21 建立工程文档基线；2026-10-27 已按用户新增授权完成 Jev 单变量开关及本次生产发布。当前进展见[项目状态](project-status.md)，实际结果见[验证报告](verification-report.md)；其他业务优先级、完整产品验收和后续发布仍需分别确认。

## 新会话阅读顺序

先读取根目录 [AGENTS.md](../AGENTS.md)，再读取[项目状态](project-status.md)、[任务清单](task-checklist.md)及[实施计划](implementation-plan.md)中当前任务。随后按影响范围读取需求、验收、架构和模块参考，并核对工作区与代码。

## 信息维护位置

| 内容 | 维护文档 | 更新时机 |
| --- | --- | --- |
| 长期开发规则与验证入口 | [AGENTS.md](../AGENTS.md) | 项目约定实质变化 |
| 需求基线与待确认业务规则 | [requirements.md](requirements.md) | 需求或范围变化 |
| 可验证的完成条件 | [acceptance-criteria.md](acceptance-criteria.md) | 需求或验收约定变化 |
| 当前全栈架构与模块边界 | [architecture.md](architecture.md) | 架构或核心数据流变化 |
| 表、字段、索引和模型关系 | [reference/database.md](reference/database.md) | 模型及数据库变更 |
| 路由、请求、响应与流式约定 | [reference/api.md](reference/api.md) | API 变化 |
| 增量实施顺序与里程碑建议 | [implementation-plan.md](implementation-plan.md) | 开发范围或依赖变化 |
| 任务明细与任务状态 | [task-checklist.md](task-checklist.md) | 任务开始、完成或受阻 |
| 当前进展、风险与交接摘要 | [project-status.md](project-status.md) | 重要进展、验证或阻塞变化 |
| 测试方法、环境和命令 | [test-plan.md](test-plan.md) | 测试方法或范围变化 |
| 实际执行的检查与证据 | [verification-report.md](verification-report.md) | 执行验证或结论变化 |
| 有长期影响的架构决策 | [adr/README.md](adr/README.md) | 需要记录新决策时 |

任务状态只在任务清单中逐项维护，项目状态只保留摘要和链接；验证报告记录实际结果，测试计划不充当结果报告。需求中的建议不能因代码已实现而自动升级为已批准需求。

## 开发与运维

- [后端开发](../src/backend/README.md)：环境、启动、分层、定向测试。
- [前端开发](../src/frontend/README.md)：代理、页面组织、构建及类型检查。
- [配置与 Git](configuration-and-git.md)：配置模板、密钥和仓库历史边界。
- [Docker 开发部署](../docker/README.md)：本地容器与依赖服务。
- [云端部署与恢复](cloud-deployment.md)：生产配置、更新、备份与回滚条件。
- [名称变更](renaming.md)：包名、数据库和数据卷的兼容关系。
- [Jev 接入](jev-integration.md)：可选门控、候选筛选、回退与效果评估。
- [Windows 安装 MinIO](development/install_minio_win.md)：专项环境参考，命令需结合实际版本核实。

## 模块与历史参考

[技术总览](reference/agentruler.md)、[核心 Agent 与模型](reference/core.md)、[服务模块](reference/service.md)用于定位代码；接口和数据库细节分别以专门参考文档维护，避免重复。

[LangChain 迁移参考](reference/migration.md)记录旧框架到 LangChain 1.x 的历史迁移思路，不是数据库迁移手册，也不是待执行的当前迭代计划。

## 当前文档边界

本项目复用现有 API、数据库文档，没有另建 `database-design.md`。离线 `api-spec.yaml` 尚未生成；后续若需要，应在隔离环境中从实际路由和模型导出并补充 SSE 语义，不能为导出规范连接生产数据。

本轮没有新增 CI、测试框架、迁移工具，也没有重排现有测试目录。`README_EN.md` 暂为空；是否维护英文文档另行决定。
