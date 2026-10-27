# 服务模块参考

更新日期：2026-10-21。范围为当前工作区的 `src/backend/agentruler/services`；仅静态核对，未连接外部服务或执行功能测试。业务 CRUD 与权限编排另在 `api/services`，数据库访问在 `database/dao`。全栈关系见[当前架构](../architecture.md)。

## RAG 与文件处理

| 模块 | 当前职责 |
|---|---|
| `rag/parser.py`、`rag/doc_parser` | 按文件类型解析、切块；按配置可生成摘要，摘要流程使用局部并发限制 |
| `rag/handler.py` | 索引写入/删除、查询改写、混合召回、去重、重排与过滤的编排入口 |
| `rag/retrieval.py` | 向量和 Elasticsearch 的召回组合 |
| `rag/embedding.py`、`rag/rerank.py` | 向量化与重排适配 |
| `rag/vector_stores` | Chroma、Milvus 和 `lite` 分支；统一导出兼容名称 `milvus_client` |
| `rag/es_client.py` | Elasticsearch 索引和查询适配；当前内部仍使用同步客户端 |
| `rag/chunk_browser.py` | Chroma Chunk 分页、向量读取与导出辅助 |
| `convert_files` | DOCX/PDF 等辅助转换，具体可用性依赖相应运行时与外部解析配置 |

`rag.enable_elasticsearch` 控制部分写入/召回路径是否组合全文检索；它不表示所有文档都已双写成功。`rag.vector_db.mode="chroma"` 使用本地 Chroma 实现，`"lite"` 选择 `MilvusLiteClient`，其他值进入 Milvus 实现。`lite` 实现仍出现 host/port 连接代码，部署前需核对实际依赖。Chunk 管理 API 当前仅支持 Chroma。

知识库文件流程在 `api/services/knowledge_file.py`，状态值为 `process`、`success`、`fail`。MySQL 元数据、对象文件、向量及可选全文索引分步写入；没有跨组件原子事务。解析失败、部分索引写入、删除残留和重试均需验证。文件创建路由直接等待该流程，不能描述成已经具备独立后台任务队列。

## 记忆

`memory/client.py` 提供 `add/search/get/update/delete/history` 等操作；`AsyncMemory` 当前固定调用 `get_chroma_vector()`，不跟随 RAG 存储模式切换，`get_milvus_vector()` 仍为占位，Graph 记忆关闭。`database/dao/memory_history.py` 保存变更历史。部分同步调用使用 `asyncio.to_thread`，部分并发操作使用 `gather`。

普通会话用 `run_id=dialog_id` 搜索和添加记忆。接口支持其他过滤标识，不代表当前普通会话已使用用户级或 Agent 级跨会话记忆。长期记忆、对话短期历史和摘要是三条不同的数据路径，分别由 memory、HistoryService、DialogService 管理。

## MCP 客户端与对外代理

`mcp/manager.py::MCPManager` 提供工具发现、元信息展示和批量调用；`multi_client.py` 管理多个 Server，`sessions.py` 实现 stdio、SSE、Streamable HTTP、websocket 连接，`load_mcp` 适配工具、资源和提示词。实际管理 API、配置转换和第三方 Server 的能力仍需分别核对。

`core/agents/mcp_agent.py` 将外部 MCP Server 作为子 Agent，并通过 `MCPUserConfigService` 将用户配置合入工具调用参数。客户端配置可能包含敏感值，文档示例只使用占位符。

对外 MCP 位于相邻的 `mcp_proxy` 与 `api/mcp_proxy`，不是这里的客户端实现。前者维护注册工具/API 适配和 JSON-RPC，会话元数据用 Redis；活动 SSE 通知队列仍在进程内。`check_auth()` 当前直接返回 `True`，未实施凭据检查；不能以外部客户端支持鉴权推导对外入口已有鉴权。路径与已知路由重叠见[API 参考](api.md)。

## 对象存储与 Redis

`storage/__init__.py` 按 `storage.mode` 选择 `MinioClient` 或 `OSSClient`，用于上传、下载、头像和文件资产。`oss_url` 等历史字段名继续存在，并不限定存储一定是阿里云 OSS。配置说明见[配置与仓库管理](../configuration-and-git.md)。

`redis.py` 是同步缓存封装，使用 pickle 序列化，当前构造入口只支持单机 URL；代码中的集群类型/辅助方法不能证明 Redis Cluster 或 Sentinel 部署已实现。`main.py` 另外创建异步 Redis 客户端供 MCP SessionManager 使用，生命周期不同。

## 工作台、决策与扩展服务

| 模块 | 当前用途/边界 |
|---|---|
| `workspace/simple_agent.py` | 工作台任务、工具调用、引导提示和回答；Jev 工具门控的接入位置 |
| `workspace/wechat_agent.py` | 微信相关工作流实现，依赖对应配置和业务入口 |
| `decision/jev.py` | 可选 Jev 决策客户端；`disabled/observe/enforce` 与超时/无效响应回退，详见[Jev 接入](../jev-integration.md) |
| `rewrite` | 查询/Markdown 改写辅助，可被 RAG 等调用 |
| `deepsearch`、`mars`、`lingseek` | 专用检索与 Agent 工作流；外部搜索/模型/网络依赖按具体实现启用 |
| `autobuild` | 构建客户端及编排，依赖外部构建运行环境 |
| `sandbox/pyodide.py` | Pyodide 代码执行适配，不能从模块名称直接推导安全隔离已验收 |

Jev 启用时会向配置端点发送有长度约束的对话文本、工具名和工具描述；日志设计避免输出响应体、凭据和对话正文，但这不等于其他模块日志均已脱敏。远程连通性、工具选择质量、开关状态和故障回退均未在本次文档工作中验证。

## 并发、失败与维护

各模块使用局部信号量、线程卸载或 `asyncio.gather`，不构成系统级容量与限流承诺。许多异常分支会返回空列表、错误文本或状态标记；调用方需要区分“确实没有结果”与“依赖调用失败”。同步 SDK/数据库调用仍可能阻塞异步链路，超时、取消和失败后清理以实际调用链为准。

修改服务时同时核对对应 `api/services` 调用方、配置结构、外部依赖和数据清理范围；新增可运行验证后写入[验证报告](../verification-report.md)。测试范围见[测试计划](../test-plan.md)，待办及优先级见[任务清单](../task-checklist.md)。
