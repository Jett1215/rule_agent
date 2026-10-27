# AgentRuler 技术参考入口

更新日期：2026-10-21。本文承担技术文档导航职责，不再重复维护数据库字段、接口示例和部署命令。当前实现依据本地工作区源码，包含未提交修改；功能存在、部署启用与验收通过是不同状态。

AgentRuler 的前端使用 Vue 3、TypeScript、Vite、Element Plus 和 Pinia；后端使用 FastAPI、SQLModel、LangChain/LangGraph，提供会话、工作台、Agent、模型、工具、MCP、知识库、Skill 和统计等入口。代码集中在一个后端工程中，外部存储与模型服务按配置接入；这不等于已具备微服务拆分、统一安全控制或高可用能力。

## 按问题查阅

| 需要了解的内容 | 文档 |
|---|---|
| 全部文档职责与阅读顺序 | [文档索引](../README.md) |
| 当前实现边界、数据流、认证与生命周期 | [系统架构](../architecture.md) |
| Agent、模型工厂、流式事件和用量回调 | [核心模块参考](core.md) |
| RAG、记忆、MCP、存储与外部适配 | [服务模块参考](service.md) |
| 路径、参数、认证与响应 | [API 参考](api.md) |
| SQLModel 表、字段、索引、关系及迁移边界 | [数据库参考](database.md) |
| 配置与本地敏感文件管理 | [配置与仓库管理](../configuration-and-git.md) |
| Jev 的模式、接入位置和回退 | [Jev 接入说明](../jev-integration.md) |
| 当前进度、已知缺口和未完成事项 | [项目状态](../project-status.md)、[任务清单](../task-checklist.md) |
| 需求、验收与验证证据 | [需求基线](../requirements.md)、[验收标准](../acceptance-criteria.md)、[测试计划](../test-plan.md)、[验证报告](../verification-report.md) |
| 增量开发与架构决策 | [实施计划](../implementation-plan.md)、[ADR 规范](../adr/README.md) |
| 部署操作、备份与回滚 | [Docker 指南](../../docker/README.md)、[云部署说明](../cloud-deployment.md) |

## 当前需要区分的边界

- 普通会话主入口为 `GeneralAgent` 及 `create_agent`；独立 `ReactAgent`、CodeAct、PlanExecute 等类不能自动视为所有业务都已启用。
- `/api/v1` 业务 API 与 `/mcp` 对外协议入口是两套调用面；认证与资源授权必须分别核对。白名单中间件仅标记请求，MCP `check_auth()` 当前直接放行。
- MySQL、对象存储、向量库和可选 Elasticsearch 分开维护数据；没有统一事务与已验证的一致性恢复保证。
- SQLModel 模型与 `create_all()` 不能证明既有数据库已完成结构迁移；生产库名、volume、bucket 等历史 `agentchat` 标识应按兼容性要求保留。
- 存在测试入口或健康路由不代表功能已通过验证。运行结果统一记入验证报告，不在模块参考中保存无证据的性能、安全或测试通过声明。

## 历史资料

[migration.md](migration.md) 是 LangChain 框架迁移参考，包含过渡性设计和示例；它不是数据库迁移指南。名称变更的背景见[renaming.md](../renaming.md)。历史部署记录与旧示例仅供追溯，当前运行方式以维护中的配置、部署指南和实际代码为准。
