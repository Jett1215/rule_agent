# AgentRuler（智治）

AgentRuler（智治）是一个支持用户自主构建和扩展智能体的应用平台，平台提供大模型对话、知识库检索等基础能力，用户可以根据自己的需求，灵活配置模型、提示词和知识库，并按需组合Tool、Skill和 MCP等能力，搭建面向特定场景的专属Agent。

## 主要功能

- **智能体管理**：配置模型、提示词和工具，创建不同用途的 AI 助手。
- **知识库检索**：支持文件上传、文本分块、向量检索和 Chunk 可视化查看。
- **工具与 MCP**：接入内置工具及 MCP 服务，扩展智能体能力。
- **对话与工作空间**：提供聊天记录、任务执行和模型配置界面。

## 技术栈

- 后端：Python、FastAPI、LangChain
- 前端：Vue 3、TypeScript、Element Plus
- 数据存储：MySQL、Redis、Chroma、MinIO
- 部署：Docker Compose

配置方法见 [配置说明](docs/configuration-and-git.md)。真实密钥和本地数据不提交到仓库。

已有部署升级时，请参照 [名称变更说明](docs/renaming.md) 保留数据库、存储桶及数据卷配置。

## 开发与项目文档

- [工程文档导航](docs/README.md)：需求、验收、架构、接口、数据库及运维入口。
- [项目开发规则](AGENTS.md)：AI Agent 与维护者的工作约定。
- [当前项目状态](docs/project-status.md)和[任务清单](docs/task-checklist.md)：跨会话恢复进度与后续候选任务。
- [后端开发](src/backend/README.md)、[前端开发](src/frontend/README.md)与[Docker 指南](docker/README.md)：环境配置及运行方式。
- [测试计划](docs/test-plan.md)和[实际验证记录](docs/verification-report.md)：区分验证方法与已执行结果。

现有功能、需求建议和验收通过分别记录；文档基线不代表全部功能已完成运行验证。
