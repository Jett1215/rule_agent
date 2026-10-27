# 数据库模型参考

更新日期：2026-10-21。依据 `src/backend/agentruler/database/models` 的当前 SQLModel 源码，以及 `database/__init__.py`、`init_data.py`。本轮未连接数据库、导出 DDL、运行建表或迁移；以下是代码模型基线，不是现存数据库结构证明。

## 连接、初始化与记法

连接由 `app_settings.mysql.endpoint`（同步）和 `async_endpoint`（异步）提供。引擎设置 `pool_pre_ping=True`、`pool_recycle=3600`，连接字符集为 utf8mb4，会话时区为 `+08:00`。具体数据库名从连接 URL 取得；现有部署中 `agentchat` 等历史数据库、用户、volume 与 bucket 标识有兼容价值，不能因产品改名直接替换。文档不保存真实连接串或口令。

启动的 `init_database()` 调用 `ensure_mysql_database()` 及 `SQLModel.metadata.create_all(engine)`：可尝试创建缺失数据库/表，**不会给既有表补列、修改字段、迁移数据或补齐既有表索引**。模型导入顺序决定 metadata 中包含哪些表；初始化还会同步默认模型和 MCP 元信息，不能视为只读操作。

字段表中的 `str/int/bool/datetime` 是源码类型，`TEXT/JSON/VARCHAR(n)/DateTime` 表示显式 SQLAlchemy 列声明。没有显式长度的字符串由 SQLModel/方言推导，实际长度与可空性需在后续 DDL 核对中确认。`Optional` 是 Python 注解，不单独作为数据库可空性证据；显式 `Column(nullable=...)` 优先。除特别列出的索引/唯一约束外，不推定其他关联列已经有索引。

通用记法：

- `PK`：源码声明的主键；`UUID hex` 指 `default_factory=lambda: uuid4().hex` 等逐次生成的值。
- `TS`：本表同时声明 `create_time`、`update_time` 两列，类型 DateTime、`nullable=False`、`server_default=CURRENT_TIMESTAMP`；后者另有 SQLAlchemy `onupdate=CURRENT_TIMESTAMP`。这是 ORM 更新表达式，不等同于已核实 MySQL DDL 中的 `ON UPDATE` 或触发器。
- `CT`：仅 `create_time`，DateTime、`nullable=False`、`server_default=CURRENT_TIMESTAMP`。
- `RT`：同时声明 `created_time`、`updated_time`，DateTime、`nullable=False`，用 `get_now_time()` 在应用端生成，后者配置应用端 `onupdate`；该函数返回东八区时间，DateTime 列本身未声明时区类型。

以下共 23 张业务表定义，包含一个未在中央数据库入口导入的历史 `mcp_agent` 模型。Role/UserRole 和注册 MCP 表直接继承 SQLModel；并非所有模型都继承 `SQLModelSerializable`。该基类提供序列化，不自动注入主键、时间戳、权限检查或敏感字段加密。

## 用户与角色

### `user` — `models/user.py::UserTable`

| 字段 | 类型/默认 | 声明与含义 |
|---|---|---|
| `user_id` | str | PK；用户标识 |
| `user_name` | str | 唯一索引；用户名 |
| `user_email` | str，默认 None | 邮箱，注解与默认不一致，DDL 待核对 |
| `user_avatar` | str | 头像 URL |
| `user_description` | str，默认“该用户很懒，没有留下一片云彩” | 用户简介 |
| `user_password` | str | 密码摘要字段；具体算法见用户服务，不能称为可逆加密 |
| `delete` | bool，默认 False | 删除标记 |
| `create_time`、`update_time` | TS | 另声明 `create_time` 索引 |

`SystemUser='0'`、`AdminUser='1'` 是代码常量，不证明这些用户行已在目标数据库存在。用户名有非空校验函数，但不能将它视为所有写入路径的数据库约束替代品。

### `role` — `models/role.py::Role`

| 字段 | 类型/默认 | 声明与含义 |
|---|---|---|
| `id` | Optional[int]，默认 None | PK |
| `role_name` | str | 唯一约束 `group_role_name_uniq` |
| `remark` | Optional[str] | 角色备注 |
| `create_time`、`update_time` | TS | 另声明 `create_time` 索引 |

角色常量为字符串 `'0'/'1'/'2'`，而本表主键注解为 int；已有应用转换行为需核对，不能据此假定外键类型一致。

### `user_role` — `models/user_role.py::UserRole`

| 字段 | 类型/默认 | 声明与含义 |
|---|---|---|
| `id` | Optional[str]，默认 None | PK；此模型未配置 UUID factory |
| `user_id` | str | 索引；逻辑关联 `user.user_id` |
| `role_id` | str | 索引；逻辑关联角色标识 |
| `create_time`、`update_time` | TS | 另声明 `update_time` 索引 |

没有声明 `(user_id, role_id)` 联合唯一约束或数据库外键；角色表存在不等于所有 API 已统一执行 RBAC。

## Agent 与 Skill

### `agent` — `models/agent.py::AgentTable`

| 字段 | 类型/默认 | 声明与含义 |
|---|---|---|
| `id` | str，UUID hex | PK |
| `name` | str，空字符串 | Agent 名称 |
| `description` | str，空字符串 | 描述 |
| `logo_url` | str，来自 `default_config.agent_logo_url` | 图标 |
| `user_id` | Optional[str] | 索引；创建用户 |
| `is_custom` | bool，True | 是否自定义 |
| `system_prompt` | str，空字符串 | 系统提示词；当前源码未显式声明 TEXT |
| `llm_id` | str，空字符串 | 逻辑关联 `llm.llm_id` |
| `enable_memory` | bool，True | 记忆开关 |
| `mcp_ids` | JSON，默认 [] | 外部 MCP Server ID 列表 |
| `tool_ids` | JSON，默认 [] | 工具 ID 列表 |
| `agent_skill_ids` | JSON，默认 [] | Skill ID 列表 |
| `knowledge_ids` | JSON，默认 [] | 知识库 ID 列表 |
| `create_time`、`update_time` | TS | 创建/修改时间 |

这些 ID 列表不是数据库关联表，没有声明元素级外键或级联删除；删除后的引用一致性由应用处理。

### `agent_skill` — `models/agent_skill.py::AgentSkill`

| 字段 | 类型/默认 | 声明与含义 |
|---|---|---|
| `id` | str，UUID hex | PK |
| `name` | str | Skill 名称 |
| `description` | str | 描述 |
| `user_id` | str | 拥有者；当前未声明索引 |
| `as_tool_name` | Optional[str] | 暴露为工具时的名称 |
| `folder` | JSON，Optional[Dict] | Skill 目录与文件内容结构 |
| `create_time`、`update_time` | TS | 创建/修改时间 |

## 会话、消息与反馈

### `dialog` — `models/dialog.py::DialogTable`

| 字段 | 类型/默认 | 声明与含义 |
|---|---|---|
| `dialog_id` | str，UUID hex | PK |
| `name` | str | 会话名称 |
| `agent_id` | str | 逻辑关联 Agent |
| `agent_type` | str，`Agent` | 类型标识，注释含 Agent/MCPAgent；非数据库枚举 |
| `user_id` | str | 会话用户；未声明索引 |
| `summary` | TEXT，nullable=True | 对话摘要 |
| `summary_last_time` | DateTime，nullable=False | 默认 `1970-01-01 00:00:00`，已摘要上下文的截止时间 |
| `create_time`、`update_time` | TS | 创建/修改时间 |

### `history` — `models/history.py::HistoryTable`

| 字段 | 类型/默认 | 声明与含义 |
|---|---|---|
| `id` | str，UUID hex | PK |
| `content` | TEXT | 消息正文 |
| `dialog_id` | str | 逻辑关联会话；未声明索引 |
| `role` | str 注解 | 源码写法为 `role: str = Literal["assistant", "system", "user"]`，不是正确的 Literal 类型注解或数据库枚举，需单独验证 |
| `token_usage` | int，0 | 消息 Token 估算值 |
| `events` | JSON，默认 [] | Agent 流式事件列表 |
| `create_time`、`update_time` | TS | 创建/修改时间 |

### `workspace_session` — `models/workspace_session.py::WorkSpaceSession`

| 字段 | 类型/默认 | 声明与含义 |
|---|---|---|
| `session_id` | str，UUID hex | PK |
| `title` | str | 工作台会话标题 |
| `agent` | str | 选用的 Agent 标识/名称 |
| `user_id` | str | 用户标识；未声明索引 |
| `contexts` | JSON，默认 [] | 结构化工作台上下文；当前请求模型含 query、guide_prompt、task、task_graph、mcp_tool_calls、reasoning、answer 等 |
| `create_time`、`update_time` | TS | 创建/修改时间 |

### `message_like`、`message_down` — `models/message.py`

两表分别保存正面和负面反馈，字段定义相同，彼此独立。

| 字段 | 类型/默认 | 声明与含义 |
|---|---|---|
| `id` | str，UUID hex | 各表 PK |
| `user_input` | TEXT | 用户输入快照 |
| `agent_output` | TEXT | Agent 输出快照 |
| `create_time`、`update_time` | TS | 创建/修改时间 |

当前没有用户、消息或会话 ID 字段，不能描述成已经建立了每用户唯一反馈关系。

## 知识库与文件

### `knowledge` — `models/knowledge.py::KnowledgeTable`

| 字段 | 类型/默认 | 声明与含义 |
|---|---|---|
| `id` | str，`t_` + UUID hex 前 16 位 | PK；兼容向量库/全文索引命名 |
| `name` | str，max_length=128 | 唯一索引；当前约束是全表唯一，并非用户内唯一 |
| `description` | Optional[str]，None，max_length=1024 | 描述 |
| `user_id` | Optional[str]，None，max_length=128 | 索引；创建用户 |
| `create_time`、`update_time` | TS | 创建/修改时间 |

### `knowledge_file` — `models/knowledge_file.py::KnowledgeFileTable`

| 字段 | 类型/默认 | 声明与含义 |
|---|---|---|
| `id` | str，`default=uuid4().hex` | PK；此处不是 default_factory，见后文风险 |
| `file_name` | str | 索引；文件名 |
| `knowledge_id` | str | 索引；逻辑关联知识库 |
| `status` | str，`success` | 状态常量为 `fail/process/success` |
| `user_id` | str | 索引；用户标识 |
| `oss_url` | str，空字符串 | 对象存储 URL；名称不限定必须使用 OSS |
| `file_size` | int，0 | 字节数 |
| `create_time`、`update_time` | TS | 创建/修改时间 |

原文件、解析 Chunk、摘要、向量和全文索引不存储在这些关系表中；其元数据与 MySQL 行之间没有跨存储外键或统一事务。

## 模型与工具

### `llm` — `models/llm.py::LLMTable`

| 字段 | 类型/默认 | 声明与含义 |
|---|---|---|
| `llm_id` | str，UUID hex | PK |
| `llm_type` | str，`LLM` | 模型用途标识（注释含 LLM/Embedding/Rerank），非数据库枚举 |
| `model` | str | 模型名称 |
| `base_url` | str | 服务端点 |
| `api_key` | str | 凭据；模型未声明字段级加密 |
| `provider` | str | 提供商 |
| `user_id` | str | 创建用户；未声明索引 |
| `create_time`、`update_time` | TS | 创建/修改时间 |

### `tool` — `models/tool.py::ToolTable`

| 字段 | 类型/默认 | 声明与含义 |
|---|---|---|
| `tool_id` | str，UUID hex | PK |
| `name` | Optional[str] | 模型调用的英文名称；旧文档的 `en_name` 不对应当前字段 |
| `display_name` | str | 用户展示名称；旧文档的 `zh_name` 不对应当前字段 |
| `user_id` | str | 创建用户；未声明索引 |
| `logo_url` | str | 图标 |
| `description` | TEXT | 工具描述 |
| `openapi_schema` | JSON，Optional[dict] | 自定义工具的 OpenAPI 定义 |
| `is_user_defined` | bool，False | 是否自定义 |
| `auth_config` | JSON，default_factory=dict | 鉴权参数；模型未声明字段级加密 |
| `create_time`、`update_time` | TS | 创建/修改时间 |

`ToolAuthType` 定义 Bearer/Basic 枚举供代码使用，本表没有独立的该枚举列。

## 外部 MCP 配置

### `mcp_server` — `models/mcp_server.py::MCPServerTable`

| 字段 | 类型/默认 | 声明与含义 |
|---|---|---|
| `mcp_server_id` | str，UUID hex | PK |
| `server_name` | str，`MCP Server` | 展示名称 |
| `user_id` | str | 创建用户 |
| `user_name` | str | 创建用户名快照 |
| `description` | str | 作为子 Agent 的描述 |
| `mcp_as_tool_name` | str | 子 Agent 工具名称 |
| `url` | str | MCP 连接地址 |
| `type` | VARCHAR(255)，nullable=False | 传输类型；注释只列 sse/websocket/stdio，底层客户端还存在 Streamable HTTP 支持，需按实际入口核对 |
| `logo_url` | str | 图标 |
| `config` | JSON，List[dict] | Server 配置字段定义 |
| `tools` | JSON，默认 [] | 工具名称列表 |
| `params` | JSON，List[dict] | 工具输入结构 |
| `imported_config` | JSON，Optional[dict] | 用户导入配置 |
| `config_enabled` | bool，False | 是否需要用户配置 |
| `create_time`、`update_time` | TS | 创建/修改时间 |

### `mcp_stdio_server` — `models/mcp_server.py::MCPServerStdioTable`

源码标注“目前暂时用不上”，中央数据库入口仍导入该模型；不据此推断现网数据或功能启用情况。

| 字段 | 类型/默认 | 声明与含义 |
|---|---|---|
| `mcp_server_id` | str，UUID hex | PK |
| `mcp_server_path` | str | 脚本路径 |
| `mcp_server_command` | str | 执行命令 |
| `mcp_server_env` | str | 环境配置文本 |
| `user_id` | str | 用户标识 |
| `name` | str，`MCP Server` | 名称 |
| `create_time` | CT | 没有 `update_time` |

### `mcp_user_config` — `models/mcp_user_config.py::MCPUserConfigTable`

| 字段 | 类型/默认 | 声明与含义 |
|---|---|---|
| `id` | str，UUID hex | PK |
| `mcp_server_id` | str | 逻辑关联 Server |
| `user_id` | str | 逻辑关联用户 |
| `config` | JSON，List[dict] | 用户参数/凭据，模型未声明字段级加密 |
| `create_time`、`update_time` | TS | 创建/修改时间 |

没有声明 `(mcp_server_id, user_id)` 联合唯一约束、索引或外键。

### `mcp_agent` — `models/mcp_agent.py::MCPAgentTable`（历史模型）

| 字段 | 类型/默认 | 声明与含义 |
|---|---|---|
| `mcp_agent_id` | str，UUID hex | PK |
| `mcp_server_id` | JSON，默认 []，注解 str | Server 关联；注解与实际列/默认值不一致 |
| `name` | str，空字符串 | 名称 |
| `description` | str，空字符串 | 描述 |
| `logo_url` | str，`img/mcp_openai/mcp_agent.png` | 图标 |
| `user_id` | Optional[str] | 索引 |
| `create_time`、`update_time` | TS | 创建/修改时间 |

`database/__init__.py` 当前没有导入该模型，不能承诺启动 `create_all()` 会包含本表。旧 `dao/mcp_agent.py` 仍引用 `id`、`is_custom` 等本模型不存在的属性；当前运行中的 MCP 子 Agent 使用 `mcp_server` 配置，不应与本历史表混同。

## 对外 MCP 注册与任务

### `register_mcp_server` — `models/register_mcp.py::RegisterMcpServer`

| 字段 | 类型/默认 | 声明与含义 |
|---|---|---|
| `id` | str，UUID 字符串，max_length=64 | PK；`generate_uuid()` 返回带连字符的 UUID |
| `name` | str，max_length=255 | Server 名称 |
| `transport` | str，`sse` | 传输类型 |
| `remote_url` | Optional[str]，None | 远程地址 |
| `user_id` | Optional[str]，None | 创建用户 |
| `description` | TEXT，默认 None | 描述 |
| `created_time`、`updated_time` | RT | 应用端时间 |

`mcp_tools` 是 ORM Relationship，不是额外列；与工具表的 `mcp_server` 双向关联。

### `register_mcp_tool` — `models/register_mcp_tool.py::RegisterMcpTool`

| 字段 | 类型/默认 | 声明与含义 |
|---|---|---|
| `id` | str，UUID 字符串，max_length=64 | PK |
| `register_mcp_id` | str，max_length=64 | 索引；**显式外键**到 `register_mcp_server.id` |
| `name` | str，max_length=1024 | 工具名 |
| `description` | TEXT，默认 None | 描述 |
| `parameters` | TEXT，默认 None | 工具参数定义文本 |
| `api_info` | JSON，默认 None | API 执行信息 |
| `created_time`、`updated_time` | RT | 应用端时间 |

`mcp_server` 为 ORM Relationship；源码未为该外键声明 `ON DELETE CASCADE`，不能承诺数据库级级联删除。

### `register_mcp_task` — `models/register_task.py::RegisterMcpTask`

| 字段 | 类型/默认 | 声明与含义 |
|---|---|---|
| `id` | str，UUID 字符串，max_length=64 | PK |
| `name` | str，`注册MCP任务` | 任务标题 |
| `user_id` | Optional[str]，None | 用户标识 |
| `register_mcp_id` | Optional[str]，None | 逻辑关联注册 Server；未声明外键 |
| `messages` | MutableList(JSON)，default_factory=list | 交互消息，含 query/answer/events 等 |
| `created_time`、`updated_time` | RT | 应用端时间 |

MutableList 跟踪列表变更不等于任意深度嵌套字典修改都能自动触发落库，需按更新方式验证。

## 用量与记忆历史

### `usage_stats` — `models/usage_stats.py::UsageStats`

| 字段 | 类型/默认 | 声明与含义 |
|---|---|---|
| `id` | str，UUID hex | PK |
| `agent` | Optional[str] | Agent 名称/标识 |
| `model` | Optional[str] | 模型名称 |
| `user_id` | str | 发起用户；未声明索引 |
| `input_tokens` | int，0 | 输入 Token |
| `output_tokens` | int，0 | 输出 Token |
| `create_time` | CT | 没有 `update_time` |

统计依赖响应 usage 元数据及回调记录，不是计费账单完整性保证。

### `memory_history` — `models/memory_history.py::MemoryHistoryTable`

| 字段 | 类型/默认 | 声明与含义 |
|---|---|---|
| `id` | str，UUID hex | PK |
| `memory_id` | str | 向量记忆标识；无数据库外键 |
| `old_memory` | TEXT，默认 None | 旧内容 |
| `new_memory` | TEXT，默认 None | 新内容 |
| `event` | str | 事件类型 |
| `created_at` | DateTime，nullable=False，server_default=CURRENT_TIMESTAMP | 创建时间 |
| `updated_at` | DateTime，nullable=False，server_default/onupdate=CURRENT_TIMESTAMP | 更新时间；更新机制同 TS 说明 |
| `is_deleted` | Boolean，默认 False | 删除标记；显式 Column 未声明 nullable=False |
| `actor_id` | Optional[str]，None | 操作者 |
| `role` | Optional[str]，None | 角色 |

## 索引与关系汇总

除各表主键外，当前显式声明的索引/唯一约束如下；没有找到复合索引声明，不能沿用旧文档“关联字段全部建索引”的说法。

| 表 | 索引/唯一约束 |
|---|---|
| `user` | `user_name` 唯一索引；`create_time` 索引 |
| `role` | `role_name` 唯一约束；`create_time` 索引 |
| `user_role` | `user_id`、`role_id`、`update_time` 各自索引 |
| `agent` | `user_id` 索引 |
| `knowledge` | `name` 唯一索引；`user_id` 索引 |
| `knowledge_file` | `file_name`、`knowledge_id`、`user_id` 各自索引 |
| `mcp_agent`（历史） | `user_id` 索引 |
| `register_mcp_tool` | `register_mcp_id` 索引及到 Server 的外键 |

主要逻辑关联为用户→Agent/Skill/模型/会话/知识库/MCP 配置、Agent→模型及 JSON ID 列表、会话→消息、知识库→文件、记忆→历史、注册 Server→注册工具/任务。除上述注册工具的外键外，其余模型没有声明这些关联的数据库外键。应用所有权校验、删除清理与引用完整性需分别验证。

## 已发现但未在本轮修复的模型问题

| 发现 | 影响及后续核对 |
|---|---|
| `agent.agent_skill_ids` 等字段已在代码存在，`create_all` 不会补现有列 | 在脱敏/隔离环境比对目标 DDL 与模型，建立版本化升级和回滚方案 |
| `KnowledgeFileTable.id` 使用类定义时求值的 `default=uuid4().hex` | 未显式传 ID 时可能复用默认值；核对服务是否覆盖 ID，再用隔离测试验证并修复 |
| `HistoryTable.role` 将 Literal 类型对象赋为 str 默认值 | 不能视为角色枚举约束，需核对构造、序列化及写入行为 |
| `mcp_agent` 未中央导入，旧 DAO 与模型字段不一致 | 核实保留/迁移/废弃策略，不能直接清表 |
| `role.id` 与 `user_role.role_id` 类型不同 | 核实真实 DDL 和应用转换；若调整需兼容现有数据 |
| 多处 Optional/默认 None 与 str 注解、显式 Column 可空性不一致 | 以实际 DDL 与受控构造验证为准，避免直接据注解发布迁移 |
| 凭据字段是普通字符串/JSON | 需另行核对返回脱敏、存储保护和访问控制，不在文档保留凭据值 |
| `test/test_sqlmodel.py` 定义另一 `User`（默认表名同为 `user`），模块顶层执行建表和插入 | 这是历史示例脚本，不计入上述业务表；不能批量导入后连接真实数据库，可能产生 metadata 冲突或写入副作用 |

## 数据库变更约定

1. 先区分代码模型、目标数据库实际 DDL 与既有数据；本文件目前只记录第一项，后两项为待核实。
2. 变更方案写明目标版本、受影响列/索引/约束、数据回填、兼容窗口、失败处理、备份及恢复步骤。涉及删除、重命名、类型收窄或凭据数据时列出数据影响。
3. 在隔离副本验证升级、旧数据读写及恢复流程，保存真实命令、环境和结果；未执行项目标记 `NOT_RUN`，写入[验证报告](../verification-report.md)。
4. 本轮未引入数据库迁移工具或执行 SQL。后续选择迁移机制后按[ADR 规范](../adr/README.md)记录，并同步[任务清单](../task-checklist.md)、[测试计划](../test-plan.md)及部署指南。

框架迁移的历史说明见 [migration.md](migration.md)，与数据库结构迁移无关；跨存储备份/恢复入口见[Docker 指南](../../docker/README.md)和[云部署说明](../cloud-deployment.md)。
