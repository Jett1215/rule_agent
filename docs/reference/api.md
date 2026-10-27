# AgentRuler API 参考

核对日期：2026-10-21。本文对照当前工作区路由与请求模型整理，包含未提交的 Jev 相关实现，但没有启动应用或调用接口。路由存在不代表已验证可用，`POST /workspace/session` 仍为占位实现。

## 路由与事实来源

业务接口由 [v1 路由聚合](../../src/backend/agentruler/api/v1/router.py)挂载在 `/api/v1`；MCP 代理由[代理路由聚合](../../src/backend/agentruler/api/mcp_proxy/router.py)直接挂载在 `/mcp`。普通聊天实际为 `POST /api/v1/completion`，没有 `/api/v1/chat` 别名。

应用在 lifespan 中先初始化配置、数据库与默认数据，再注册路由；不要只导入 `app` 后生成空规范，也不要为导出文档直接连接生产环境。运行中的 `/docs` 与 `/openapi.json` 可用于核对普通 HTTP Schema，但 SSE、JSON-RPC、真实权限和数据行为仍需专项说明与验证。

当前不维护第二份手写 `api-spec.yaml`。后续若需要离线快照，应从隔离环境的实际注册路由导出，并记录代码版本和 SSE 语义。

## 请求与认证

前端普通请求在 [request.ts](../../src/frontend/src/utils/request.ts)中读取 `localStorage.token` 并发送 `Authorization: Bearer <access_token>`；SSE 请求有各自调用代码。后端 [JWT 配置](../../src/backend/agentruler/api/JWT.py)决定 Header/Cookie 支持，不能仅凭登录设置 Cookie 假定全部入口都校验登录。

[白名单中间件](../../src/backend/agentruler/middleware/white_list_middleware.py)只设置请求标记，[get_login_user](../../src/backend/agentruler/api/services/user.py)才根据标记决定是否验证 JWT。用户信息读取、用户更新及知识库检索等路由未显式使用该依赖；MCP `check_auth()` 当前直接返回 `True`。这是访问控制待核实事项，不是接口安全保证；登录校验与资源所有权还需分别验证，见[项目状态](../project-status.md)和[测试计划](../test-plan.md)。

请求表中 `JSON` 表示请求体，`Query` 为查询参数，`Path` 为路径参数，`Form`/`File` 为表单及文件。类型和默认值保留源声明；没有默认值的参数通常必填。`Optional` 只描述可空性，不自动表示可省略；`Body(embed=True)` 的标量需要包在同名 JSON 字段中。约束、别名和模型默认值以源定义及隔离环境生成的 Schema 核实。

## 返回与错误

使用 [builder.py](../../src/backend/agentruler/api/responses/builder.py)的普通业务响应为：

```json
{"status_code": 200, "status_message": "SUCCESS", "data": null}
```

业务状态字段为 `status_code`、`status_message`，不是旧文档中的 `code`、`message`。`resp_500()` 返回业务失败对象，HTTP 层仍可能是 200；`raise HTTPException` 则使用 HTTP 状态与 `detail`。部分历史分支直接返回 `HTTPException` 对象，其实际序列化需验证，不能假定与抛出异常相同。认证、校验错误、文件下载、SSE 和 MCP JSON-RPC 不统一套此包装。

### 普通对话 SSE

`POST /api/v1/completion` 接受 `dialog_id`、`user_input`、可选 `file_url`，具体为 [CompletionReq](../../src/backend/agentruler/schemas/completion.py)。先创建或选择属于当前用户的对话；拥有一个 ID 不代表有权访问，需进行权限专项验证。

请求体示例只描述字段结构：

```json
{"dialog_id": "<测试对话ID>", "user_input": "你好", "file_url": null}
```

响应为 `text/event-stream`，帧以 `data: <JSON>\n\n` 分隔。文本片段示例：

```json
{"type": "response_chunk", "timestamp": 0, "data": {"chunk": "你好", "accumulated": "你好"}}
```

这是格式示例，不是执行证据。其他 Agent 事件结构见 [GeneralAgent](../../src/backend/agentruler/core/agents/general_agent.py)；流中模型错误可能转换为兜底文本，客户端收到文本不能单独证明任务成功。断连响应类会调用停止回调，但不保证所有下游模型、工具与任务都已取消。

### 工作台 SSE 与注册任务

`POST /api/v1/workspace/simple/chat` 使用 [WorkSpaceSimpleTask](../../src/backend/agentruler/schemas/workspace.py)：`query`、`model_id`、`session_id` 必填，`plugins`、`mcp_servers` 默认为空列表。模型、工具和会话数据需来自隔离测试环境。

工作台流中的 JSON 使用 `event`、`data`，与普通聊天的 `type` 格式不同。现有事件有 `reasoning_chunk`（`data.chunk`）、`task_result`（`data.message`）和 `mcp_tool`（执行状态等）；客户端按当前工作台实现消费，不应通用套用聊天解析器。会话在执行链中保存；独立 `POST /workspace/session` 当前为 `pass`。

注册任务 `/api/v1/mcp/register/completion` 及 HITL approve/reject 也返回 SSE，使用该模块自己的事件与结束处理。不要假定所有流都有同一个 DONE 帧，详见[注册流实现](../../src/backend/agentruler/api/v1/register_mcp_completion.py)。

## 业务路由清单

下表直接静态提取已聚合模块的装饰器、前缀和函数参数；不导入应用。响应栏只描述代码中可见的返回构造，具体 `data` 内容和边界需沿源码核实。

### completion

| 方法 | 完整路径 | 请求声明 | 响应约定 | 源定义 |
| --- | --- | --- | --- | --- |
| POST | `/api/v1/completion` | JSON `req: CompletionReq` | SSE；登录依赖 | [completion](../../src/backend/agentruler/api/v1/completion.py#L21) |

### dialog

| 方法 | 完整路径 | 请求声明 | 响应约定 | 源定义 |
| --- | --- | --- | --- | --- |
| GET | `/api/v1/dialog/list` | 无显式业务参数 | 业务 JSON；登录依赖 | [get_dialog](../../src/backend/agentruler/api/v1/dialog.py#L13) |
| POST | `/api/v1/dialog` | JSON `dialog_req: DialogCreateRequest` | 业务 JSON；登录依赖 | [create_dialog](../../src/backend/agentruler/api/v1/dialog.py#L34) |
| DELETE | `/api/v1/dialog` | JSON `dialog_id: str` | 业务 JSON；登录依赖 | [delete_dialog](../../src/backend/agentruler/api/v1/dialog.py#L52) |

### message

| 方法 | 完整路径 | 请求声明 | 响应约定 | 源定义 |
| --- | --- | --- | --- | --- |
| POST | `/api/v1/message/like` | 手工 JSON `user_input`、`agent_output`（request.json） | 业务 JSON | [insert_message_like](../../src/backend/agentruler/api/v1/message.py#L9) |
| POST | `/api/v1/message/down` | 手工 JSON `user_input`、`agent_output`（request.json） | 业务 JSON | [insert_message_down](../../src/backend/agentruler/api/v1/message.py#L21) |

### agent

| 方法 | 完整路径 | 请求声明 | 响应约定 | 源定义 |
| --- | --- | --- | --- | --- |
| POST | `/api/v1/agent` | JSON `req: AgentCreateReq` | 业务 JSON；登录依赖 | [create_agent](../../src/backend/agentruler/api/v1/agent.py#L13) |
| GET | `/api/v1/agent` | 无显式业务参数 | 业务 JSON；登录依赖 | [get_agent](../../src/backend/agentruler/api/v1/agent.py#L33) |
| DELETE | `/api/v1/agent` | JSON `req: AgentDeleteReq` | 业务 JSON；登录依赖 | [delete_agent](../../src/backend/agentruler/api/v1/agent.py#L45) |
| PUT | `/api/v1/agent` | JSON `agent_request: AgentUpdateReq` | 业务 JSON；登录依赖 | [update_agent](../../src/backend/agentruler/api/v1/agent.py#L64) |
| POST | `/api/v1/agent/search` | JSON `req: AgentSearchReq` | 业务 JSON；登录依赖 | [search_agent](../../src/backend/agentruler/api/v1/agent.py#L93) |

### history

| 方法 | 完整路径 | 请求声明 | 响应约定 | 源定义 |
| --- | --- | --- | --- | --- |
| GET | `/api/v1/history` | Query `dialog_id: str` | 业务 JSON；登录依赖 | [get_dialog_history](../../src/backend/agentruler/api/v1/history.py#L10) |

### user

| 方法 | 完整路径 | 请求声明 | 响应约定 | 源定义 |
| --- | --- | --- | --- | --- |
| POST | `/api/v1/user/register` | JSON `user_name: str`；JSON `user_email: Optional[str]`；JSON `user_password: str` | 业务 JSON | [register](../../src/backend/agentruler/api/v1/user.py#L22) |
| POST | `/api/v1/user/login` | JSON `user_name: str`；JSON `user_password: str` | 业务 JSON | [login](../../src/backend/agentruler/api/v1/user.py#L52) |
| PUT | `/api/v1/user/update` | JSON `user_id: str`；JSON `user_avatar: Optional[str]`；JSON `user_description: Optional[str]` | 业务 JSON | [update_user_info](../../src/backend/agentruler/api/v1/user.py#L81) |
| GET | `/api/v1/user/icons` | 无显式业务参数 | 业务 JSON | [get_select_user_avatar](../../src/backend/agentruler/api/v1/user.py#L89) |
| GET | `/api/v1/user/info` | Query `user_id: str` | 业务 JSON | [get_user_info](../../src/backend/agentruler/api/v1/user.py#L96) |

### tool

| 方法 | 完整路径 | 请求声明 | 响应约定 | 源定义 |
| --- | --- | --- | --- | --- |
| POST | `/api/v1/tool/create` | JSON `req: ToolCreateReq` | 业务 JSON；登录依赖 | [create_tool](../../src/backend/agentruler/api/v1/tool.py#L15) |
| POST | `/api/v1/tool/all` | 无显式业务参数 | 业务 JSON；登录依赖 | [get_all_tools](../../src/backend/agentruler/api/v1/tool.py#L38) |
| POST | `/api/v1/tool/user_defined` | 无显式业务参数 | 业务 JSON；登录依赖 | [get_user_defined_tools](../../src/backend/agentruler/api/v1/tool.py#L50) |
| POST | `/api/v1/tool/delete` | JSON `req: ToolDeleteReq` | 业务 JSON；登录依赖 | [delete_user_defined_tool](../../src/backend/agentruler/api/v1/tool.py#L62) |
| POST | `/api/v1/tool/update` | JSON `req: ToolUpdateReq` | 业务 JSON；登录依赖 | [update_user_defined_tool](../../src/backend/agentruler/api/v1/tool.py#L78) |
| GET | `/api/v1/tool/default_logo` | 无显式业务参数 | 业务 JSON；登录依赖 | [get_default_tol_logo](../../src/backend/agentruler/api/v1/tool.py#L100) |

### llm

| 方法 | 完整路径 | 请求声明 | 响应约定 | 源定义 |
| --- | --- | --- | --- | --- |
| POST | `/api/v1/llm/create` | JSON `req: LLMCreateReq` | 业务 JSON；登录依赖 | [create_llm](../../src/backend/agentruler/api/v1/llm.py#L12) |
| DELETE | `/api/v1/llm/delete` | JSON `req: LLMDeleteReq` | 业务 JSON；登录依赖 | [delete_llm](../../src/backend/agentruler/api/v1/llm.py#L27) |
| PUT | `/api/v1/llm/update` | JSON `req: LLMUpdateReq` | 业务 JSON；登录依赖 | [update_llm](../../src/backend/agentruler/api/v1/llm.py#L43) |
| GET | `/api/v1/llm/all` | 无显式业务参数 | 业务 JSON；登录依赖 | [get_all_llm](../../src/backend/agentruler/api/v1/llm.py#L59) |
| POST | `/api/v1/llm/personal` | 无显式业务参数 | 业务 JSON；登录依赖 | [get_personal_llm](../../src/backend/agentruler/api/v1/llm.py#L70) |
| POST | `/api/v1/llm/visible` | 无显式业务参数 | 业务 JSON；登录依赖 | [get_visible_llm](../../src/backend/agentruler/api/v1/llm.py#L81) |
| GET | `/api/v1/llm/agent/models` | 无显式业务参数 | 业务 JSON；登录依赖 | [get_all_agent_models](../../src/backend/agentruler/api/v1/llm.py#L92) |
| POST | `/api/v1/llm/search` | JSON `req: LLMSearchReq` | 业务 JSON；登录依赖 | [search_models](../../src/backend/agentruler/api/v1/llm.py#L102) |
| GET | `/api/v1/llm/schema` | 无显式业务参数 | 业务 JSON；登录依赖 | [get_llm_type](../../src/backend/agentruler/api/v1/llm.py#L114) |

### knowledge

| 方法 | 完整路径 | 请求声明 | 响应约定 | 源定义 |
| --- | --- | --- | --- | --- |
| POST | `/api/v1/knowledge/create` | JSON `knowledge_req: KnowledgeCreateRequest` | 业务 JSON；登录依赖 | [upload_knowledge](../../src/backend/agentruler/api/v1/knowledge.py#L15) |
| GET | `/api/v1/knowledge/select` | 无显式业务参数 | 业务 JSON；登录依赖 | [select_knowledge](../../src/backend/agentruler/api/v1/knowledge.py#L32) |
| PUT | `/api/v1/knowledge/update` | JSON `knowledge_req: KnowledgeUpdateRequest` | 业务 JSON；登录依赖 | [update_knowledge](../../src/backend/agentruler/api/v1/knowledge.py#L44) |
| DELETE | `/api/v1/knowledge/delete` | JSON `knowledge_id: str` | 业务 JSON；登录依赖 | [delete_knowledge](../../src/backend/agentruler/api/v1/knowledge.py#L62) |
| POST | `/api/v1/knowledge/retrieval` | JSON `query: str`；JSON `knowledge_id: Union[str, List[str]]` | 业务 JSON | [retrieval_knowledge](../../src/backend/agentruler/api/v1/knowledge.py#L77) |

### knowledge_file

| 方法 | 完整路径 | 请求声明 | 响应约定 | 源定义 |
| --- | --- | --- | --- | --- |
| GET | `/api/v1/knowledge_file/chunks` | Query `knowledge_file_id: str`；Query `page: int=1`；Query `page_size: int=10`；Query `search: str=''` | 业务 JSON；登录依赖 | [list_file_chunks](../../src/backend/agentruler/api/v1/knowledge_file.py#L43) |
| GET | `/api/v1/knowledge_file/chunks/vector` | Query `knowledge_file_id: str`；Query `record_id: str` | 业务 JSON；登录依赖 | [read_chunk_vector](../../src/backend/agentruler/api/v1/knowledge_file.py#L58) |
| GET | `/api/v1/knowledge_file/chunks/export` | Query `knowledge_file_id: str`；Query `format: Literal['txt', 'json']='txt'` | 文件下载；登录依赖 | [download_file_chunks](../../src/backend/agentruler/api/v1/knowledge_file.py#L73) |
| POST | `/api/v1/knowledge_file/create` | JSON `knowledge_id: str`；JSON `file_url: str` | 业务 JSON；登录依赖 | [upload_file](../../src/backend/agentruler/api/v1/knowledge_file.py#L100) |
| GET | `/api/v1/knowledge_file/select` | Query `knowledge_id: str` | 业务 JSON；登录依赖 | [select_knowledge_file](../../src/backend/agentruler/api/v1/knowledge_file.py#L133) |
| DELETE | `/api/v1/knowledge_file/delete` | JSON `knowledge_file_id: str` | 业务 JSON；登录依赖 | [delete_knowledge_file](../../src/backend/agentruler/api/v1/knowledge_file.py#L148) |
| GET | `/api/v1/knowledge_file/status` | JSON `knowledge_file_id: str` | 业务 JSON；登录依赖 | [get_knowledge_file_status](../../src/backend/agentruler/api/v1/knowledge_file.py#L162) |

### mcp_server

| 方法 | 完整路径 | 请求声明 | 响应约定 | 源定义 |
| --- | --- | --- | --- | --- |
| POST | `/api/v1/mcp_server` | JSON `req: MCPServerImportedReq` | 业务 JSON；登录依赖 | [create_mcp_server](../../src/backend/agentruler/api/v1/mcp_server.py#L20) |
| GET | `/api/v1/mcp_server` | 无显式业务参数 | 业务 JSON；登录依赖 | [get_mcp_servers](../../src/backend/agentruler/api/v1/mcp_server.py#L71) |
| DELETE | `/api/v1/mcp_server` | JSON `server_id: str` | 业务 JSON；登录依赖 | [delete_mcp_server](../../src/backend/agentruler/api/v1/mcp_server.py#L81) |
| GET | `/api/v1/mcp_tools` | JSON `server_id: str` | 业务 JSON；登录依赖 | [get_mcp_tools](../../src/backend/agentruler/api/v1/mcp_server.py#L97) |
| PUT | `/api/v1/mcp_server` | JSON `req: MCPServerUpdateReq` | 业务 JSON；登录依赖 | [update_mcp_server](../../src/backend/agentruler/api/v1/mcp_server.py#L113) |
| GET | `/api/v1/mcp_server/logo` | 无显式业务参数 | 业务 JSON；登录依赖 | [get_mcp_default_logo](../../src/backend/agentruler/api/v1/mcp_server.py#L181) |

### mcp_user_config

| 方法 | 完整路径 | 请求声明 | 响应约定 | 源定义 |
| --- | --- | --- | --- | --- |
| POST | `/api/v1/mcp_user_config/create` | JSON `config_request: MCPUserConfigCreateRequest` | 业务 JSON；登录依赖 | [create_mcp_user_config](../../src/backend/agentruler/api/v1/mcp_user_config.py#L12) |
| GET | `/api/v1/mcp_user_config/{config_id}` | Path `config_id: str` | 业务 JSON；登录依赖 | [get_mcp_user_config_by_id](../../src/backend/agentruler/api/v1/mcp_user_config.py#L27) |
| PUT | `/api/v1/mcp_user_config/update` | JSON `config_request: MCPUserConfigUpdateRequest` | 业务 JSON；登录依赖 | [update_mcp_user_config](../../src/backend/agentruler/api/v1/mcp_user_config.py#L37) |
| DELETE | `/api/v1/mcp_user_config/delete` | JSON `config_id: str` | 业务 JSON；登录依赖 | [delete_mcp_user_config](../../src/backend/agentruler/api/v1/mcp_user_config.py#L52) |
| GET | `/api/v1/mcp_user_config` | Query `server_id: str` | 业务 JSON；登录依赖 | [get_mcp_user_config](../../src/backend/agentruler/api/v1/mcp_user_config.py#L62) |

### mars

| 方法 | 完整路径 | 请求声明 | 响应约定 | 源定义 |
| --- | --- | --- | --- | --- |
| POST | `/api/v1/mars/chat` | JSON `user_input: str` | SSE；登录依赖 | [chat_mars](../../src/backend/agentruler/api/v1/mars.py#L28) |
| POST | `/api/v1/mars/example` | JSON `example_id: int` | SSE；登录依赖 | [chat_mars_example](../../src/backend/agentruler/api/v1/mars.py#L92) |

### workspace

| 方法 | 完整路径 | 请求声明 | 响应约定 | 源定义 |
| --- | --- | --- | --- | --- |
| GET | `/api/v1/workspace/plugins` | 无显式业务参数 | 业务 JSON；登录依赖 | [get_workspace_plugins](../../src/backend/agentruler/api/v1/workspace.py#L22) |
| GET | `/api/v1/workspace/session` | 无显式业务参数 | 业务 JSON；登录依赖 | [get_workspace_sessions](../../src/backend/agentruler/api/v1/workspace.py#L27) |
| POST | `/api/v1/workspace/session` | Query `title: str=''`；JSON `contexts: dict={}` | 占位实现（null）；登录依赖 | [create_workspace_session](../../src/backend/agentruler/api/v1/workspace.py#L33) |
| POST | `/api/v1/workspace/session/{session_id}` | Path `session_id: str` | 业务 JSON；登录依赖 | [workspace_session_info](../../src/backend/agentruler/api/v1/workspace.py#L40) |
| DELETE | `/api/v1/workspace/session` | Query `session_id: str` | 业务 JSON；登录依赖 | [create_workspace_session](../../src/backend/agentruler/api/v1/workspace.py#L49) |
| POST | `/api/v1/workspace/simple/chat` | JSON `simple_task: WorkSpaceSimpleTask` | SSE；登录依赖 | [workspace_simple_chat](../../src/backend/agentruler/api/v1/workspace.py#L59) |

### lingseek

| 方法 | 完整路径 | 请求声明 | 响应约定 | 源定义 |
| --- | --- | --- | --- | --- |
| POST | `/api/v1/workspace/lingseek/guide_prompt` | JSON `lingseek_info: LingSeekGuidePrompt` | SSE；登录依赖 | [generate_lingseek_guide_prompt](../../src/backend/agentruler/api/v1/lingseek.py#L15) |
| POST | `/api/v1/workspace/lingseek/guide_prompt/feedback` | JSON `feedback_guide_prompt: LingSeekGuidePromptFeedBack` | SSE；登录依赖 | [rebuild_generate_lingseek_guide_prompt](../../src/backend/agentruler/api/v1/lingseek.py#L34) |
| POST | `/api/v1/workspace/lingseek/task` | JSON `task: LingSeekTask` | SSE；登录依赖 | [generate_lingseek_tasks](../../src/backend/agentruler/api/v1/lingseek.py#L53) |
| POST | `/api/v1/workspace/lingseek/task_start` | JSON `task: LingSeekTask` | SSE；登录依赖 | [submit_lingseek_task](../../src/backend/agentruler/api/v1/lingseek.py#L68) |

### usage_stats

| 方法 | 完整路径 | 请求声明 | 响应约定 | 源定义 |
| --- | --- | --- | --- | --- |
| POST | `/api/v1/usage` | JSON `usage_stats: UsageStatsRequest` | 业务 JSON；登录依赖 | [get_agentruler_usage](../../src/backend/agentruler/api/v1/usage_stats.py#L11) |
| POST | `/api/v1/usage_count` | JSON `usage_stats: UsageStatsRequest` | 业务 JSON；登录依赖 | [get_agentruler_usage_count](../../src/backend/agentruler/api/v1/usage_stats.py#L26) |
| GET | `/api/v1/usage/models_list` | 无显式业务参数 | 业务 JSON；登录依赖 | [get_usage_models](../../src/backend/agentruler/api/v1/usage_stats.py#L42) |
| GET | `/api/v1/usage/agents_list` | 无显式业务参数 | 业务 JSON；登录依赖 | [get_usage_agents](../../src/backend/agentruler/api/v1/usage_stats.py#L52) |

### wechat

| 方法 | 完整路径 | 请求声明 | 响应约定 | 源定义 |
| --- | --- | --- | --- | --- |
| GET | `/api/v1/wechat` | Query `signature: str`；Query `timestamp: str`；Query `nonce: str`；Query `echostr: str` | 纯文本 | [wechat_verify](../../src/backend/agentruler/api/v1/wechat.py#L51) |
| POST | `/api/v1/wechat` | 原始 XML 请求体（request.body） | XML/字符串及错误分支（见实现） | [handle_wechat_message](../../src/backend/agentruler/api/v1/wechat.py#L65) |

### upload

| 方法 | 完整路径 | 请求声明 | 响应约定 | 源定义 |
| --- | --- | --- | --- | --- |
| POST | `/api/v1/upload` | File `file: UploadFile` | 业务 JSON；登录依赖 | [upload_file](../../src/backend/agentruler/api/v1/upload.py#L14) |

### agent_skill

| 方法 | 完整路径 | 请求声明 | 响应约定 | 源定义 |
| --- | --- | --- | --- | --- |
| POST | `/api/v1/agent_skill/create` | JSON `req: AgentSkillCreateReq` | 业务 JSON；登录依赖 | [create_agent_skill](../../src/backend/agentruler/api/v1/agent_skill.py#L13) |
| POST | `/api/v1/agent_skill/delete` | JSON `req: AgentSkillDeleteReq` | 业务 JSON；登录依赖 | [delete_agent_skill](../../src/backend/agentruler/api/v1/agent_skill.py#L27) |
| GET | `/api/v1/agent_skill/all` | 无显式业务参数 | 业务 JSON；登录依赖 | [get_agent_skills](../../src/backend/agentruler/api/v1/agent_skill.py#L40) |
| POST | `/api/v1/agent_skill/file/update` | JSON `req: AgentSkillFileUpdateReq` | 业务 JSON；登录依赖 | [update_agent_skill_file](../../src/backend/agentruler/api/v1/agent_skill.py#L52) |
| POST | `/api/v1/agent_skill/file/add` | JSON `req: AgentSkillFileAddReq` | 业务 JSON；登录依赖 | [add_agent_skill_file](../../src/backend/agentruler/api/v1/agent_skill.py#L69) |
| POST | `/api/v1/agent_skill/file/upload` | Form `agent_skill_id: str`；Form `path: str`；File `file: UploadFile` | 业务 JSON；登录依赖 | [upload_agent_skill_file](../../src/backend/agentruler/api/v1/agent_skill.py#L82) |
| POST | `/api/v1/agent_skill/file/delete` | JSON `req: AgentSkillFileDeleteReq` | 业务 JSON；登录依赖 | [delete_agent_skill_file](../../src/backend/agentruler/api/v1/agent_skill.py#L103) |

### register_task

| 方法 | 完整路径 | 请求声明 | 响应约定 | 源定义 |
| --- | --- | --- | --- | --- |
| GET | `/api/v1/mcp/register/task/list` | 无显式业务参数 | 业务 JSON；登录依赖 | [get_register_mcp_tasks](../../src/backend/agentruler/api/v1/register_task.py#L12) |
| POST | `/api/v1/mcp/register/task/create` | 无显式业务参数 | 业务 JSON；登录依赖 | [create_register_mcp_task](../../src/backend/agentruler/api/v1/register_task.py#L22) |
| POST | `/api/v1/mcp/register/task/delete` | JSON `req: DeleteMcpTaskRequest` | 业务 JSON；登录依赖 | [delete_register_mcp_task](../../src/backend/agentruler/api/v1/register_task.py#L31) |

### register_mcp

| 方法 | 完整路径 | 请求声明 | 响应约定 | 源定义 |
| --- | --- | --- | --- | --- |
| POST | `/api/v1/mcp/register` | JSON `req: RegisterMcpRequest` | 业务 JSON；登录依赖 | [register_mcp_server](../../src/backend/agentruler/api/v1/register_mcp.py#L15) |
| GET | `/api/v1/mcp/list` | 无显式业务参数 | 业务 JSON；登录依赖 | [get_all_register_mcps](../../src/backend/agentruler/api/v1/register_mcp.py#L29) |

### register_mcp_completion

| 方法 | 完整路径 | 请求声明 | 响应约定 | 源定义 |
| --- | --- | --- | --- | --- |
| POST | `/api/v1/mcp/register/completion` | JSON `req: CompletionReq` | SSE；登录依赖 | [completion](../../src/backend/agentruler/api/v1/register_mcp_completion.py#L57) |
| POST | `/api/v1/mcp/register/completion/hitl/approve` | JSON `req: HitlApproveReq` | SSE；登录依赖 | [hitl_approve](../../src/backend/agentruler/api/v1/register_mcp_completion.py#L98) |
| POST | `/api/v1/mcp/register/completion/hitl/reject` | JSON `req: HitlRejectReq` | SSE；登录依赖 | [hitl_reject](../../src/backend/agentruler/api/v1/register_mcp_completion.py#L139) |

## MCP 代理路由

MCP 使用独立 JSON-RPC 协议；当前凭据校验未启用。SSE transport 的消息入口使用 Query `sessionId`；Streamable HTTP 使用 `Mcp-Session-Id` Header，initialize 当前固定返回 JSON，并在响应 Header 返回 `Mcp-Session-Id`；其余 POST 请求要求该会话 Header，并根据 Accept 返回 JSON 或 SSE。GET 保持流，DELETE 关闭会话；健康接口不代表全部依赖或工具可用。两个 transport 存在相同的健康检查路径，聚合时 SSE 模块先注册；需核实路由顺序和预期行为。

### mcp_sse

| 方法 | 完整路径 | 请求声明 | 响应约定 | 源定义 |
| --- | --- | --- | --- | --- |
| GET | `/mcp/{server_key}/sse` | Path `server_key: str` | JSON-RPC / SSE / 状态响应 | [sse_endpoint](../../src/backend/agentruler/api/mcp_proxy/mcp_sse.py#L31) |
| POST | `/mcp/{server_key}/message` | Path `server_key: str`；Query `session_id: str（别名 sessionId）`；手工 JSON-RPC 请求体（request.body） | JSON-RPC / SSE / 状态响应 | [message_endpoint](../../src/backend/agentruler/api/mcp_proxy/mcp_sse.py#L70) |
| GET | `/mcp/{server_key}/health` | Path `server_key: str` | HealthResponse | [health_check](../../src/backend/agentruler/api/mcp_proxy/mcp_sse.py#L104) |

### mcp_streamable_http

| 方法 | 完整路径 | 请求声明 | 响应约定 | 源定义 |
| --- | --- | --- | --- | --- |
| POST | `/mcp/{server_key}` | Path `server_key: str`；手工 JSON-RPC 请求体（request.body） | JSON-RPC / SSE / 状态响应 | [streamable_http_endpoint](../../src/backend/agentruler/api/mcp_proxy/mcp_streamable_http.py#L40) |
| GET | `/mcp/{server_key}` | Path `server_key: str` | JSON-RPC / SSE / 状态响应 | [sse_listen_endpoint](../../src/backend/agentruler/api/mcp_proxy/mcp_streamable_http.py#L149) |
| DELETE | `/mcp/{server_key}` | Path `server_key: str` | JSON-RPC / SSE / 状态响应 | [close_session_endpoint](../../src/backend/agentruler/api/mcp_proxy/mcp_streamable_http.py#L219) |
| GET | `/mcp/{server_key}/health` | Path `server_key: str` | HealthResponse | [health_check](../../src/backend/agentruler/api/mcp_proxy/mcp_streamable_http.py#L259) |

## 常用请求模型

| 用途 | 字段与源定义 |
| --- | --- |
| 注册/登录 | 注册为 `user_name`、`user_email`、`user_password`；登录为 `user_name`、`user_password`。见 [user.py](../../src/backend/agentruler/api/v1/user.py)；当前没有启用注释中的验证码校验 |
| Agent 创建/更新 | 模型、提示词、工具/MCP、知识库、技能绑定和记忆开关；更新使用 `agent_id`。见 [schemas/agent.py](../../src/backend/agentruler/schemas/agent.py) |
| Skill 与文件 | 创建描述、Skill ID、路径和内容等；上传使用表单而非普通 JSON。见 [schemas/agent_skill.py](../../src/backend/agentruler/schemas/agent_skill.py) |
| 模型配置 | 模型、服务地址、密钥、提供方等字段；删除也是模型请求体，不能自行改成 Query。见 [schemas/llm.py](../../src/backend/agentruler/schemas/llm.py) |
| 知识库 | 创建/更新字段使用 `knowledge_name`、`knowledge_desc` 等，见 [schemas/knowledge.py](../../src/backend/agentruler/schemas/knowledge.py) |
| Chunk 查询/导出 | `knowledge_file_id`，分页 `page`/`page_size`，搜索 `search`；向量读取还需 `record_id`，导出格式 `txt`/`json`。仅当前 Chroma 分支支持，见 [knowledge_file.py](../../src/backend/agentruler/api/v1/knowledge_file.py) |
| MCP 用户配置 | 字段、传输与鉴权配置见 [schemas/mcp_user_config.py](../../src/backend/agentruler/schemas/mcp_user_config.py)及[MCP Server Schema](../../src/backend/agentruler/schemas/mcp_server.py)；配置不代表入口访问控制已完成 |
| 用量查询 | 请求模型仅接受 `agent`、`model`、`delta_days`；`user_id` 来自登录身份，不能由请求指定。字段及枚举见 [schemas/usage_stats.py](../../src/backend/agentruler/schemas/usage_stats.py) |
| 注册任务 | 注册流请求为 `query`、`task_id`；approve 为 `task_id`；reject 另有 `feedback`。与普通对话的 `CompletionReq` 同名但字段不同，见[注册模块](../../src/backend/agentruler/api/v1/register_mcp_completion.py) |

## 健康检查与验证边界

应用 lifespan 注册 `GET /health`，返回 `{"status":"OK"}`，不挂在 `/api/v1`。它仅描述探针处理结果，不证明数据库、对象存储、向量库或模型服务健康；静态源码也不能证明目标部署已经启动成功。

后续修改路由、参数、错误或 SSE 时同步本文及客户端，并按[测试计划](../test-plan.md)执行契约与权限验证；实际结果写入[验证报告](../verification-report.md)。本文没有记录任何真实 Token、API key 或私有请求数据。
