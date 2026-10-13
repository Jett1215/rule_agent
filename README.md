# Rule Agent

基于 AgentChat 二次开发的智能体应用平台，集成大模型对话、工具调用和知识库检索，支持搭建、管理和调试 AI 助手。

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

本项目基于 [AgentChat](https://github.com/Shy2593666979/AgentChat)，保留原项目的 [MIT 许可证](LICENSE)。
