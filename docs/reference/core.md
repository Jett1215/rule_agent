# 核心模块参考

实现基线最初于 2026-10-21 静态核对，2026-10-27 同步提交状态：Jev 代码已提交并部署，保持关闭；定向测试及发布最小链路证据见[验证报告](../verification-report.md)，不表示本页所有能力已验收。全栈边界与数据流见[当前架构](../architecture.md)，接口契约见[API 参考](api.md)。

## Agent 入口

| 模块 | 当前职责与调用方式 |
|---|---|
| `core/agents/general_agent.py` | 普通 `/api/v1/completion` 主入口。`AgentConfig` 描述用户、模型、工具、MCP、Skill、知识库、提示词和记忆开关；先 `await init_agent()`，再遍历 `astream(messages)` |
| `core/agents/mcp_agent.py` | 将某个外部 MCP Server 封装为子 Agent；发现其工具，在调用前注入用户 MCP 配置，提供 `ainvoke(messages)` |
| `core/agents/skill_agent.py` | 从数据库中的 Skill 文件树读取 `SKILL.md` 和关联文件，构造 Skill 子 Agent，提供文件查看等工具及 `ainvoke(messages)` |
| `core/agents/structured_response_agent.py` | 基于 `create_agent` 的结构化结果生成；接收响应格式，供 MCP 元信息等流程使用 |
| `core/agents/react_agent.py` | 独立的 LangGraph ReAct 实现，手动组织模型节点与工具节点；普通会话当前直接使用 `GeneralAgent` 内的 `create_agent`，不能把本类示例当成当前主链路 |
| `core/agents/plan_execute_agent.py` | 规划、逐步执行工具的独立实现；是否适用于某业务入口需沿调用链核实 |
| `core/agents/codeact_agent.py` | CodeAct 图与 Pyodide 执行适配；依赖沙箱运行环境，存在本类不代表执行隔离已经验收 |
| `core/agents/text2sql_agent.py` | 模型生成 SQL、执行和重试的独立工具实现；不应从名称推断只读 SQL 或完整数据库权限隔离 |

`GeneralAgent` 初始化时汇集内置注册工具、OpenAPI 工具、知识库检索工具、MCP 和 Skill 子 Agent，再交给 LangChain `create_agent`。`search_available_tools` 的旧探索工具仍有代码，但当前“工具超过阈值后只绑定搜索工具”的分支是注释，不能作为已启用行为描述。

## 中间件与事件

`EmitEventAgentMiddleware` 负责工具执行的 `START/END/ERROR` 事件、工具展示名解析及模型调用后的状态更新；发生工具异常时构造带错误文本的 `ToolMessage`。它是执行状态呈现机制，不是权限验证或事务补偿层。

`JevToolSelectorMiddleware` 在模型调用前对已提供的 `BaseTool` 列表做可选筛选，每轮包括工具结果返回后都会重新评估。它检查返回工具对象属于原候选集合；无法表达的 provider 原生工具、无效候选或服务错误保留原请求。工作台的工具门控位于 `services/workspace/simple_agent.py`，不在本中间件中。配置与回退行为见[Jev 接入说明](../jev-integration.md)。

`GeneralAgent.astream()` 输出统一包装的字典：

```json
{"type":"response_chunk","timestamp":0,"data":{"chunk":"文本","accumulated":"累计文本"}}
```

事件使用 `type="event"`，其 `data` 通常含 `status`、`title`、`message`。API 再序列化为 SSE 的 `data:` JSON 数据行。部分子 Agent 使用不同的内部事件字段，前端应以实际 API 契约处理；不要将内部回调字典直接当作全部接口的公共协议。

停止回调目前在 `GeneralAgent` 中只设置 `stop_streaming`，其流循环未检查此字段。断连、异步任务取消、外部工具停止及最终历史保存的组合行为需专项验证，见[测试计划](../test-plan.md)。

## 模型工厂

`core/models/manager.py::ModelManager` 根据 `app_settings.multi_models` 创建对话、工具调用、推理、视觉与 Embedding 客户端；用户模型可从 `llm` 表参数创建。主要方法是 `get_conversation_model()`、`get_tool_invocation_model()`、`get_user_model()`、`get_reasoning_model()` 和 `get_embedding_model()`。

对话和工具调用默认使用 `ChatOpenAI` 兼容客户端。`get_user_model(preserve_reasoning=True)` 选择 `ReasoningChatOpenAI`；默认 `False`。`get_conversation_model(disable_thinking=True)` 当前只对 hostname 为 `api.deepseek.com` 的配置添加指定 thinking 参数，不应泛化为所有服务商都支持同一参数。Embedding 和推理包装分别在 `embedding.py`、`reason_model.py` 等文件中。

配置参数不等于服务已可用：模型名、提供商兼容性、流式 usage 和工具调用能力均依赖实际服务，需要真实或受控替身验证。

## Token 用量记录

`core/callbacks/usage_metadata.py` 从模型回调的 `AIMessage.usage_metadata` 和 `model_name` 读取用量，用线程锁累计进程内模型统计，并同步写 `usage_stats`。用户和 Agent 信息来自 `utils/contexts.py`；缺少用户上下文时使用系统用户。仅在响应包含相应元数据时记录，不能承诺所有模型费用都已完整核算。

Jev 的用量在 `JevDecisionService` 中另行异步记录并设短超时。普通消息的 `token_usage` 另有文本估算逻辑，两者与服务商计费账单不能直接等同。

## 修改时的联动范围

- 修改 Agent 工具装配或候选筛选：同步权限/副作用约束、事件契约和异常/回退验收项。
- 修改流式执行：核对前端 SSE、断连、取消和历史/记忆保存行为。
- 修改模型工厂或回调：核对配置模板、服务商兼容性和用量记录，不在文档或日志放入真实凭据。
- 改变架构边界：更新[当前架构](../architecture.md)并按[ADR 规范](../adr/README.md)记录决策。

[migration.md](migration.md) 保留的是 LangChain 框架迁移说明，不是数据库迁移记录，也不证明其中全部示例均已通过当前环境验证。
