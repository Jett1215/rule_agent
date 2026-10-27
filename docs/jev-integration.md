# Jev 工具门控与候选筛选

本项目使用 TypeSafe 的 Jev 判断是否需要工具、哪些工具可能相关，原有模型继续生成回答和工具参数，工具仍由现有执行链调用。本次接入覆盖工作台 `WorkSpaceSimpleAgent` 的工具门控和普通聊天 `GeneralAgent` 的逐轮工具候选筛选，不涉及数据库迁移。

## 调用方式

Jev 使用 TypeSafe 的独立 HTTP API。后端复用现有 `httpx` 依赖，向配置的 `base_url` 下的 `/v1/systemone` 发起请求，通过 Bearer API key 认证，提交 `state`、`model` 和 `questions`，读取 `answers` 与 `usage`。接口规范见 [TypeSafe 官方 API 文档](https://docs.typesafe.ai/api)。

Jev 不注册为 `ChatOpenAI` 对话模型，也不替换用户选择的主模型。用于判别的上下文和工具描述会发送到配置的 TypeSafe 服务；API key 保留在后端本机配置中。

## 两个接入点

### 工作台：是否需要执行工具

`WorkSpaceSimpleAgent` 在工具执行分支前询问 Jev：结合当前上下文与已绑定工具，本轮是否需要工具。该问题使用 Noul，返回肯定答案的概率 `needs_tools`。

在 `enforce` 模式中，只有概率小于或等于 `skip_tools_probability` 时才跳过工具分支，后续回答仍由原有模型生成。例如默认阈值 `0.05` 表示仅在非常倾向于“不需要工具”时跳过。其他结果、判别失败或输入超限时继续原工具流程。

### 普通聊天：每次模型调用前筛选候选工具

`GeneralAgent` 在工具数量达到 `min_tools_for_selection` 时，根据当前对话状态为已绑定工具评估相关性。每轮都重新判断，以便上一轮工具返回的信息可以影响下一轮选择。

在 `enforce` 模式中，至少一个工具的相关性概率达到 `1 - tool_relevance_threshold` 才应用筛选；默认需要至少一个概率不低于 `0.85` 的工具。满足该条件后，保留所有概率不低于 `tool_relevance_threshold`（默认 `0.15`）的工具，并保持原列表顺序。

若合格候选超过 `max_selected_tools`（默认 5 个），整轮回到原工具列表，不按分数截断，避免漏掉多步任务需要的工具。没有高置信候选、筛选失败或输入超限时也保留原列表；工具数量较少时直接使用原列表。

筛选只缩小本轮提供给模型的候选集合，不能添加尚未绑定的工具。主模型仍负责决定是否真正调用、生成参数和组织多步任务；用户标识、MCP 用户配置、鉴权与执行中间件继续按原流程处理。相关性判断不会扩大用户授权范围。

## 配置

在本机 YAML 根节点填写 `jev`。本地后端使用 `src/backend/agentruler/config.yaml`，开发 Docker 使用 `docker/docker_config.yaml`，生产 Docker 使用 `docker/docker_config.prod.yaml`；真实配置及密钥不要提交到 Git。完整配置管理说明见[配置与 Git 提交](configuration-and-git.md)。

```yaml
jev:
  mode: disabled
  api_key: ''
  base_url: https://api.typesafe.ai
  model: jev-1.13.0
  timeout_seconds: 1.5
  tool_gate_enabled: true
  tool_selector_enabled: true
  min_tools_for_selection: 10
  max_selected_tools: 5
  skip_tools_probability: 0.05
  tool_relevance_threshold: 0.15
  max_context_chars: 12000
  max_tools: 100
```

| 配置项 | 作用 |
| --- | --- |
| `mode` | `disabled` 关闭，`observe` 仅观察，`enforce` 应用判别结果；可由非空 `JEV_MODE` 环境变量覆盖。 |
| `api_key` | 自己的 TypeSafe API key。缺失时回到原流程。 |
| `base_url` / `model` | TypeSafe API 根地址与模型标识。 |
| `timeout_seconds` | Jev HTTP 请求超时时间。 |
| `tool_gate_enabled` | 控制工作台是否需要工具的门控。 |
| `tool_selector_enabled` | 控制 GeneralAgent 的工具候选筛选。 |
| `min_tools_for_selection` | 工具数达到此值才尝试候选筛选。 |
| `max_selected_tools` | 应用筛选允许的候选数量上限；超过此值时回到原列表。 |
| `skip_tools_probability` | 允许跳过工具分支的 `needs_tools` 概率上限。 |
| `tool_relevance_threshold` | 候选概率下限；同时要求至少一个工具概率达到 `1 - 此值`。 |
| `max_context_chars` | 送入判别的上下文字符数上限；超限回到原流程。 |
| `max_tools` | 可评估的工具数量上限；超限回到原流程。 |

这些阈值是初始配置，概率也不是执行正确率。应使用本项目的中文请求评估后再调整。

## 用一个变量做对照测试

`JEV_MODE` 是两处已接入能力共用的总开关。配置好自己的 API key 后，可只改变这一个变量运行同一组请求：

| `JEV_MODE` | 对照用途 |
| --- | --- |
| `disabled` | 基线组，两处都不请求 Jev，使用原流程。 |
| `observe` | 观察组，两处按各自条件请求 Jev，但不应用判别结果。 |
| `enforce` | 实验组，两处按各自条件应用 Jev 判别。 |

配置优先级为：非空 `JEV_MODE` → YAML 的 `jev.mode` → 默认 `disabled`。未设置变量或值为空白时沿用 YAML，空值不代表关闭；需要明确关闭时设为 `disabled`。这项覆盖在默认创建 `JevDecisionService(config=None)` 时读取；测试或调用方显式传入 `config` 时，仍使用传入配置。

非空 `JEV_MODE` 不属于 `disabled`、`observe`、`enforce` 时，服务只记录不包含原始值的告警，并按 `disabled` 处理；两处均保留原流程，不抛错阻断聊天。

总开关不覆盖两个独立开关：`tool_gate_enabled` 和 `tool_selector_enabled` 默认均为 `true`；其中某项已设为 `false` 时，`enforce` 不会强制开启它。API key、阈值、最少工具数量与回退规则继续生效，因此 `enforce` 也不保证每个请求都会调用 Jev 或缩小工具列表。

### 本地 Python

在 `src/backend` 目录、项目 Python 3.12+ 环境中启动后端。下面命令每次选择一条；结束当前进程后再切换下一组：

```bash
JEV_MODE=disabled python -m uvicorn agentruler.main:app --host 127.0.0.1 --port 7860
JEV_MODE=observe python -m uvicorn agentruler.main:app --host 127.0.0.1 --port 7860
JEV_MODE=enforce python -m uvicorn agentruler.main:app --host 127.0.0.1 --port 7860
```

这是启动环境变量，不是网页上的热切换按钮。修改终端变量不会改变已运行后端进程的环境，需要用新值重新启动后端。

### Docker

从项目根目录操作。可在已有的本机 `docker/.env` 中设置 `JEV_MODE=observe`，需要基线或应用结果时分别改为 `disabled`、`enforce`；留空则沿用挂载 YAML 中的 `jev.mode`。不要覆盖已有 `.env` 或把其中的真实凭据提交到 Git。

修改变量后，开发环境重新创建后端容器：

```bash
docker compose --env-file docker/.env -f docker/docker-compose.yml up -d --no-deps --force-recreate backend
```

也可以只给这次 Compose 命令传值，shell 中的值优先于 `.env`：

```bash
JEV_MODE=disabled docker compose --env-file docker/.env -f docker/docker-compose.yml up -d --no-deps --force-recreate backend
```

生产环境使用对应的 Compose 文件，按已批准的部署流程执行：

```bash
JEV_MODE=enforce docker compose --env-file docker/.env -f docker/docker-compose.production.yml up -d --no-deps --force-recreate backend
```

更改容器环境变量后，`docker compose restart backend` 不会更新已有容器的环境；以上 `up -d --no-deps --force-recreate backend` 使用新环境重新创建后端容器，`--no-deps` 仅表示不启动依赖服务。只改 `JEV_MODE` 无需重新构建镜像，也没有数据库迁移；首次部署这项代码仍应按正常流程构建包含新代码的镜像。

## 运行模式与回退

- `disabled`：不请求 Jev，保持原有工具选择流程。默认使用此模式。
- `observe`：请求 Jev 并记录判别摘要，不改变工具分支或候选列表；仍会产生 Jev 请求用量和等待时间。
- `enforce`：应用工具门控与候选筛选；各项开关可单独关闭。

判别上下文包含可完整容纳的历史与系统消息。输入过大或包含多模态内容时回到原流程，不静默截断上下文后继续判别。

未配置 key、网络错误、超时、限流、无效响应、概率不可靠或输入超过限制时，回到原流程。这样可以保留原有完成任务的机会；Jev 未返回有效决策不代表本轮不需要工具。

填写自己的 key 后，建议先使用 `observe` 收集表现，再改为 `enforce`。这是上线使用建议；切换模式不需要数据库变更。直接修改本机 YAML 后重启后端读取；若已设置非空 `JEV_MODE`，模式继续以环境变量为准，更新方式见上节。

## 日志、用量与效果验证

Jev 判别日志仅记录模式、场景、概率、耗时、候选数量、选中工具在原列表中的索引和回退原因；不记录工具名称、API key、原始消息、工具参数或工具结果。`usage` 通过现有统计服务主动写入 `usage_stats`，沿用用户与模型维度，无需新增表。统计写入有独立的 100ms 超时预算，失败会告警，不影响已完成的决策；统计异常时可能缺少部分用量记录。现有统计记录 token 用量，金额需结合实际服务价格计算。

使用同一组中文请求对比 `disabled`、`observe` 和 `enforce`，至少覆盖寒暄、一般问答、明确需要单个工具的任务、多工具任务，以及依赖上一轮工具结果的后续操作。

重点记录：

1. **净成本**：原主模型和工具调用的费用变化，加上 Jev 新增请求费用；不能仅比较主模型 token 数。
2. **端到端延迟**：从用户发出请求到首段有效回复及任务完成的时间，覆盖多轮工具链；不能用 Jev 单次 HTTP 耗时代替整体收益。
3. **漏选情况**：需要工具却跳过、关键工具未入选、后续步骤无法继续，以及最终任务完成率。对多工具请求单独检查候选上限的影响。
4. **回退情况**：超时、限流、缺少候选、输入超限等原因的出现频率，确认回退后仍能按原流程完成任务。

`observe` 可帮助判断决策分布和观察新增开销；实际节省与漏选影响仍需通过 `enforce` 与基线对照验证。默认保持关闭，不对成本或速度给出未经验证的节省比例。
