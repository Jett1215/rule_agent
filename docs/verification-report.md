# 验证记录

本文件只记录实际执行结果及明确的未验证范围。测试方法见[测试计划](test-plan.md)，功能标准见[验收标准](acceptance-criteria.md)。没有结果记录不能推断功能通过。

## 2026-10-21 文档基线整理

范围：M-DOC / DOC-001～DOC-003。代码基点为本地 `main` 的 `acde86b` 加任务开始前已有工作区修改；未检查生产部署状态。环境为本地 macOS，日期按 Asia/Shanghai。

本轮使用文件读取、Git 状态/差异及不导入应用的静态脚本检查。系统 Python 3.9 不能解析项目部分 Python 3.12+ 语法，因此接口静态检查使用本机已安装的 Python 3.13；没有将旧解释器错误记为代码缺陷。未安装或更新项目依赖。

| 检查 ID | 目标 | 方法与命令 | 状态 | 结果与证据 |
| --- | --- | --- | --- | --- |
| DOC-CHECK-001 | 获批文档完整性 | 检查 11 份新增 Markdown 是否存在且非空 | PASS | 11 份新增、10 份修订文档均存在且非空；代码围栏闭合 |
| DOC-CHECK-002 | 本地引用 | 静态扫描本轮文档 Markdown 相对路径、源文件行号及 Markdown 标题锚点 | PASS | 349 处本地引用有效；未检查外部网站可达性 |
| DOC-CHECK-003 | API 与数据模型对应 | 不导入应用，对路由与 SQLModel 源文件进行静态对照 | PASS | 96 处路由声明（95 个唯一方法/路径，不含另述的应用健康探针）与清单一致；23 表的 188 个持久字段名逐表覆盖；10 个需求与 25 个验收 ID 引用有效 |
| DOC-CHECK-004 | 差异格式 | `git diff --check` 及本轮 Markdown 行尾检查 | PASS | 退出码 0；无行尾空白及未闭合代码围栏 |
| DOC-CHECK-005 | 既有非文档工作保护 | 对比任务开始前已修改/未跟踪非 Markdown 文件 SHA-256，并检查新增非文档改动 | PASS | 20 个既有非文档文件与开始时摘要一致，没有额外非文档变更；未提交或推送 Git |

实际检查工作目录为仓库根目录；本机 CPython 3.13.13 执行临时静态脚本 `/private/tmp/agentruler_docs_check.py`（退出码 0），另执行 `git diff --check`（退出码 0）。脚本与开始时摘要保存在本机临时目录，不作为仓库依赖；上表是持久化结果摘要。脚本只读仓库内容与 Git 状态，没有导入业务模块或访问网络。

接口检查验证路由清单覆盖，不证明所有请求、错误或输出行为都正确；字段检查验证模型字段名覆盖，不证明数据类型、索引与目标数据库实际 DDL 完全一致。初次检查时已排除基类的 `ClassVar` 和 ORM Relationship，它们不计入持久字段。

文档检查通过仅表示对应静态检查通过，不代表项目构建、功能、数据安全或发布验收通过。

## 2026-10-21 未执行的运行验证

| 验证范围 | 关联需求或计划 | 状态 | 原因与后续条件 |
| --- | --- | --- | --- |
| 前端 Node 测试、类型检查、构建 | TEST-FE-001 / QA-001 | NOT_RUN | 本轮仅改文档；后续在安装对应依赖的环境分别执行 |
| 后端定向 unittest | TEST-BE-001～005 / QA-002 | NOT_RUN | 未启动项目环境或加载业务模块；先审查导入副作用和测试配置 |
| Jev 三组自动化测试 | TEST-JEV-001～003 | NOT_RUN | 测试文件存在不等于已运行 |
| API、资源权限与真实数据持久化 | SEC-001、QA-003 | NOT_RUN | 需要隔离数据库、用户、存储及服务 |
| 用户端到端流程 | QA-003 | NOT_RUN | 需选定本期验收范围与工具、环境 |
| Jev 真实成本、速度、漏选评估 | JEV-001 | NOT_RUN | 需要允许真实服务调用、费用范围和对照任务集 |
| 生产部署、备份恢复、回滚 | DATA-001 | NOT_RUN | 本轮未访问云端、修改数据库或操作数据卷 |
| 性能、覆盖率、安全扫描和故障恢复 | 待确认非功能目标 | NOT_RUN | 尚无已确认目标及可复现测试条件 |

静态发现及后续任务统一维护在[项目状态](project-status.md)和[任务清单](task-checklist.md)，避免在本报告复制第二套缺陷状态。

## 2026-10-27 Jev 单变量开关

任务：JEV-002；关联 REQ-009.1、REQ-010.2、AC-023，回归覆盖 AC-024、AC-025 的既有桩场景。用户要求用一个变量控制已接入的两处 Jev，以便对照测试。实现增加 `JEV_MODE` 对 YAML 共用模式的可选覆盖，开发/生产 Compose 后端透传该变量；未设置或空白沿用 YAML，无效值关闭 Jev，独立开关与缺 key 回退保持有效。

代码为本地 `main`（HEAD `acde86b`）的现有工作区加本轮增量，保留任务开始时全部暂存内容及无关文件；没有提交、推送、启动应用、连接实际数据库或调用真实模型服务。测试环境为 macOS、临时虚拟环境 `/tmp/agentruler-jev-switch-venv`、CPython 3.13.5、Docker Compose 5.5.1；必要依赖按 `uv.lock` 约束安装，使用 LangChain 1.2.15、langchain-core 1.2.28、LangGraph 1.1.6、Pydantic 2.12.5、httpx 0.28.1。官方包站下载先遇到 DNS/TLS 错误，随后从项目部署使用的阿里云镜像成功安装相同锁定版本；没有改动依赖声明或锁文件。

| 检查 ID | 目标 | 实际方法与命令 | 状态 | 结果与边界 |
| --- | --- | --- | --- | --- |
| JEV-SWITCH-001 | 两处共用开关与回退 | 在 `src/backend` 执行下方定向 unittest 命令 | PASS | 31 项测试通过，退出码 0；新增三模式统一控制、空值/未设回退、非法值关闭、显式配置及独立开关兼容；外部 TypeSafe/数据库隔离，LangChain 执行图真实运行但模型为桩 |
| JEV-SWITCH-002 | 开发/生产环境透传 | `docker compose --env-file <临时脱敏 env> -f <对应 compose> config --format json`，捕获 JSON 检查 `services.backend.environment.JEV_MODE` | PASS | 两份 Compose × disabled/observe/enforce/空值/未设置，10/10 通过；清除父进程相关覆盖，未读取真实 `.env`、打印完整配置或启动容器；只证明静态配置解析正确 |
| JEV-SWITCH-003 | 静态格式、文档与工作区保护 | Python 3.13 `ast.parse`、本轮文档相对文件链接检查、`git diff --check`、开始/结束 SHA-256 比较 | PASS | 修改的 Python 文件可解析、文件链接可定位、差异格式通过；暂存区摘要及无关文件保持不变 |

```bash
# 工作目录：src/backend；不读取真实后端 YAML 或启动应用
JEV_MODE= /tmp/agentruler-jev-switch-venv/bin/python -m unittest \
  agentruler.test.test_jev_decisions \
  agentruler.test.test_jev_middleware \
  agentruler.test.test_jev_workspace -q
```

测试返回 `Ran 31 tests`、`OK`（判别服务 20、中间件 6、工作台 5）。测试仅使用脱敏虚构 key、受控 HTTP 响应和临时配置；不能代表真实 Jev 的中文判断质量、净成本、端到端延迟或真实数据库/用户业务验收。未运行前端测试、类型检查、构建、全目录测试发现、生产部署或数据操作；本任务未修改前端、接口或数据库结构，也不宣称已有统一后端 Lint、类型检查或 CI 通过。

## 2026-10-27 生产发布

任务：DEPLOY-001，关联 REQ-009、REQ-010。用户明确授权按推荐顺序更新服务器，并指定 `root@121.40.185.246:22`，要求成功连接后记录连接信息。使用本机已有 `~/.ssh/agentruler_deploy` 密钥和已核验主机指纹成功登录；连接命令已写入[部署说明](cloud-deployment.md#已验证的服务器连接2026-10-27)。没有在文档中保存密码、密钥内容、Token 或真实配置值。

已按用户要求创建并推送两次英文提交：`a0500b86094b566b8ca2dc2d8daf532c86cebd0c`（`docs: establish engineering documentation and refresh branding`）和 `08f9b23bb50338a6403c6929d436a047eaff43f5`（`feat(jev): add configurable tool gating and selection`）。生产 `/opt/rule_agent` 的 `main` 从 `df53c301cce956aa1d7ac5c2df3624dd94238170` 快进到 `08f9b23`；原有未跟踪目录 `src/frontend/.deploy-backups/` 保留，最终已跟踪工作区无修改。发布验证结束时运维文档尚未另行提交；其后用户已提交为 `5d67cc7`，该文档提交不属于本次已部署源码，收尾时的 Git 核对见下文。

环境：前端本机 macOS、Node `26.0.0`、npm `11.12.1`、Vite `5.4.19`，使用已有依赖，未新增或更新前端依赖；常见路径未找到 Node 20，未将本次构建称作 Node 20 验证。后端本机定向测试使用 `/tmp/agentruler-jev-switch-venv` 的 CPython `3.13.5`；服务器 Docker Compose `5.6.0`，生产镜像运行 Python `3.12.15`，依赖按 `uv.lock` 安装。未修改数据库模型、迁移脚本或基础服务版本。

| 检查 ID | 目标与实际方法 | 状态 | 结果与证据 |
| --- | --- | --- | --- |
| DEPLOY-CHECK-001 | SSH、Git、磁盘、Compose、卷与配置挂载核实，`nginx -t` | PASS | 成功登录用户指定主机；确认旧源码、4 个健康服务、固定项目 `rule-agent`、Nginx 静态目录和 API 代理；发布前约 20GB 可用磁盘 |
| DEPLOY-CHECK-002 | 在 `src/frontend` 执行 `npm test`、`npm run lint`、`npm run build` | PASS | 测试 2/2，`vue-tsc --noEmit` 和生产构建通过（28.38s）；205 个文件，共 9,126,978 字节；保留 Sass 弃用、既有 eval、重复导入和大 chunk 警告，未将警告修复扩大到本次发布 |
| DEPLOY-CHECK-003 | 本机及新镜像内运行 Jev 三组定向 unittest | PASS | 两个环境各 31 项通过；新镜像测试退出码 0（0.423s），使用 `--network none` 且不挂载生产配置，不代表真实 Jev 调用 |
| DEPLOY-CHECK-004 | 备份旧源码标识、配置、Nginx、前端、旧镜像、MySQL 与向量/记忆；最终执行 `sha256sum -c archives.sha256` | PASS | 6 项备份文件校验通过；旧镜像归档还通过 `gzip -t`；MySQL dump 在停止后端后以单事务导出，向量/记忆目录在后端停止期间归档；不包含 Redis/MinIO 全量数据备份 |
| DEPLOY-CHECK-005 | 构建后端并 `up -d --no-deps --force-recreate backend`，核对运行容器、初始化日志标记与配置字节 | PASS | 新后端 healthy、`/health` 返回 OK，日志有数据库及 runtime ready 标记且无对应初始化失败标记；运行环境 `JEV_MODE=disabled`；真实 YAML 与备份字节一致，`.env` 仅改变 Jev 总开关，配置权限均为 0600 |
| DEPLOY-CHECK-006 | 对照发布前容器元数据及 Nginx 站点 | PASS | MySQL、Redis、MinIO 仍健康，容器 ID、启动时间未变；Nginx 站点字节未变，未重启或重载 Nginx，也未重启宿主机 |
| DEPLOY-CHECK-007 | 上传前端归档，解压后逐文件 `sha256sum -c`，整体切换 dist，验证 Nginx 响应 | PASS | 全部 205 文件校验通过；旧 dist 保留；首页哈希与本机构建一致，2 个入口 JS/CSS 资源返回 200 且类型正确 |
| DEPLOY-CHECK-008 | 在运行容器执行受控注册、登录、鉴权、模型读取及一次无工具工作台 SSE | PASS | 健康 200；无令牌鉴权 401；注册及登录 HTTP/业务码 200；错误密码 HTTP 200、业务码 10600；模型读取 200；SSE HTTP 200 且收到 `task_result`，实际调用现有主模型；没有选择工具或 MCP，也未调用 Jev |
| DEPLOY-CHECK-009 | 精确清理临时普通账号及关联数据，并复查不存在 | PASS | 仅删除脚本随机创建账号对应的会话、用量、角色、Redis 登录 key 及账号；清理与复查成功，没有清理真实用户数据 |
| DEPLOY-CHECK-010 | 开发机以 `curl --noproxy '*'` 公网直连首页、入口资源及 `/api/` 代理 | PASS | 首页 HTTP 200 且哈希一致；入口 JS/CSS 均 HTTP 200，JS 完整下载哈希与本地产物一致；`/api/v1/user/icons` 业务码 200；无令牌 `/api/v1/llm/schema` HTTP 401（`curl --fail` 预期退出 22），证明公网静态与受保护 API 路径可达 |
| DEPLOY-CHECK-011 | 运维文档差异与本地引用检查 | PASS | `git diff --check` 退出 0；当时 6 份修改 Markdown 的 64 处本地引用与对应标题有效，代码围栏闭合；该检查点仅有文档修改，助手未创建第三次提交或推送；用户后续提交另记 |

关键执行命令如下。构建时后端仍运行，备份应用数据和切换时只停止后端；新前端校验后整体替换目录。所有涉及私有配置、容器环境和日志的检查只输出选定状态或脱敏摘要，没有输出完整值。

```bash
# 本机 src/backend；在新生产镜像内也执行相同三个模块
JEV_MODE= /tmp/agentruler-jev-switch-venv/bin/python -m unittest \
  agentruler.test.test_jev_decisions \
  agentruler.test.test_jev_middleware \
  agentruler.test.test_jev_workspace -q

# 服务器 /opt/rule_agent
docker compose --env-file docker/.env -f docker/docker-compose.production.yml build backend
docker run --rm --network none --entrypoint python agentruler-backend:production \
  -m unittest agentruler.test.test_jev_decisions \
  agentruler.test.test_jev_middleware agentruler.test.test_jev_workspace -q
docker compose --env-file docker/.env -f docker/docker-compose.production.yml \
  up -d --no-deps --force-recreate backend
```

第一次通过 SSH 标准输入执行切换脚本时，MySQL `exec -T` 消耗了后续脚本输入，流程停在后端停止之后，未执行容器重建。定位后为 dump 命令显式增加 `< /dev/null`，重新执行并完成数据备份、后端重建、前端切换和上述全部验证；不能把第一次提前结束记为发布成功。另在只读脚本复核中发现临时脚本后端错误处理缺少退出语句，已补充退出；本次成功发布未触发该回退分支，也未验证自动回滚。

公网检查时，本机默认代理返回 302，改为 `--noproxy '*'` 直连后首页返回 200。首次入口 JS 下载收到 200，但 6,520,615 字节文件在 15 秒上限时未接收完（退出 28）；将上限延长至 60 秒后，15.17 秒完成下载、退出 0，哈希与本机构建一致。这是本次链路的单次观测，不代表页面性能验收通过。

发布产物标识：

- 运行后端镜像 ID：`sha256:69ab2a46fde109b4c55e4ba63717ea45499d2477173c00ca9303148b0e08ef30`。
- 前端归档 SHA-256：`8e7b0a6b03a6e232a514d279684cd534ff7cf93ac6668ddc329fdb38f562a092`。
- 前端文件清单 SHA-256：`8e9dfa07d5734effae9052dce9da00991a1ab8b0bd930244eea0e32923fbbf23`。
- 首页 SHA-256：`39e600df63f4846507811a7a8702ef1fbe391ad0bdecbe4fdbf467b88aea8075`。

受控证据目录为服务器 `/var/backups/rule-agent/20261027T101329Z-08f9b23`，包含 `archives.sha256`、`containers-before.json`、`backend-after.json`、`frontend-after.json`、`image-tests.log`、`frontend-checksums.log` 和 `final-verification.json`。同目录的配置归档、SQL 和数据归档含秘密或用户数据，不放入 Git、聊天或公开附件。旧镜像独立标签为 `agentruler-backend:rollback-20261027T101329Z-08f9b23`，旧前端目录为 `frontend-directory-before/`。校验和通过只证明备份文件完整性；本次没有实际恢复或回滚演练，也未配置异地备份。

未验证范围：真实 Jev 调用、中文判别质量、成本与延迟收益；完整浏览器交互、多工具/MCP、文件上传下载、知识库检索、跨用户资源权限；公网 Nginx 路径下的 SSE 断连/重连；全目录后端测试、统一后端 Lint/类型检查、CI、性能和安全扫描。容器内真实 SSE 通过不能替代这些验收，JEV-001、DATA-001 和其他候选任务状态不因此完成。

## 2026-10-27 开发收尾

任务：CLOSE-001；关联 REQ-009.4。用户确认当前任务完成，要求依据本机《02-日常恢复Prompt.doc》收尾。使用 macOS `textutil -convert txt -stdout` 只读提取文档内容，按用户本轮请求落实规则加载、Git/实际代码核对、状态同步、验证复核及下一步交接；没有因文档中的“继续下一项开发任务”启动新的候选事项，也未修改原始 Word 文档。

收尾开始时 `git status --short` 无输出，分支为 `main`；HEAD 与本地 `origin/main` 跟踪引用同为 `5d67cc7b2402867e5dbe859fb08eb480fbbf1e87`，该用户提交标题为 `1`，仅包含上次六份运维文档。这里是本地 Git 事实，本轮没有重新联网查询 GitHub 或服务器，不能把跟踪引用视为实时远端验证；已部署应用版本仍引用 DEPLOY-001 的 `08f9b23` 验证记录。

| 检查 ID | 方法与范围 | 状态 | 实际结果与边界 |
| --- | --- | --- | --- |
| CLOSE-CHECK-001 | 读取根规则、项目状态、任务清单、实施计划及相关需求/架构/验收/测试计划；`git status --short --branch`、`git show --stat HEAD` | PASS | 当前任务及授权范围明确，开始时无工作区修改；确认用户已提交此前运维文档，修正“尚未提交”的过时描述，保留当时检查结果的历史语境 |
| CLOSE-CHECK-002 | `git diff --quiet 08f9b23 HEAD -- src docker pyproject.toml uv.lock AGENTS.md`，只读核对 Jev 服务、两处接入与 Compose | PASS | 退出 0，应用/部署树与已验证版本一致；共享模式、两处接入、模板默认关闭及 Compose 透传仍存在。本轮不重做已有开发、构建或部署 |
| CLOSE-CHECK-003 | `python3 /tmp/agentruler-close-check.py`、`git diff --check` | PASS | 9 份修改均为 Markdown，234 处本地引用、其中 9 处标题锚点有效；代码围栏闭合、差异格式通过，暂存区保持为空；任务清单 6 项已批准任务均为 DONE，候选任务未启动 |
| CLOSE-CHECK-004 | 复核既有测试/发布结果，人工审阅状态和文档差异 | PASS | 前端 2/2、类型检查、构建，后端 31 项定向测试、10 组 Compose 静态检查及部署最小链路仍按原环境和执行范围记录；本轮仅改交接文档，未将这些历史检查记为重新运行 |

本轮自动静态检查在本机 macOS、仓库根目录执行，使用 `python3`（CPython 3.9.6）；仅执行 Git/Markdown 静态脚本，不用该解释器导入或运行要求 Python 3.12+ 的后端。详细计数保存在本机 `/tmp/agentruler-close-check-result.json`；脚本不读取真实配置、不启动服务或调用外部 API。收尾改动同步项目状态、任务清单、需求、架构、验收、测试计划及相关参考文档，没有业务逻辑、接口、数据结构或依赖变化。收尾检查阶段未提交或推送 Git，九份文档修改留在工作区；用户随后明确授权以英文提交信息归档并推送这些修改，最终提交记录以 Git 历史为准。

首次收尾静态脚本将已批准任务行数误设为 7（实际为 6），计数断言失败、退出 1；核对任务 ID 后更正脚本，重跑通过。该问题属于临时检查脚本的计数修正，没有修改既有任务完成状态。

结论：本次已批准范围全部完成，无阻塞；真实 Jev/收益、完整跨模块及浏览器验收、访问控制专项、恢复/回滚等仍是后续候选和验证边界，不作为本轮未完成事项。下一轮先完成 BASE-001 的范围确认；若用户选择 JEV-001，再明确对照样本、数据发送范围、费用和环境。本轮没有启用 Jev、执行恢复、清理已有备份或删除本机配置/数据。

## 2026-10-27 会话模块合并

任务：CONV-001；需求 REQ-011，验收 AC-026～AC-028。用户确认合并方案并要求参考《02-日常恢复Prompt.doc》完成前置工作、开发、测试与项目状态更新。文档使用 `textutil -convert txt -stdout` 只读提取；按本次请求加载 AGENTS、状态、任务、计划及对应需求/架构/验收，不因通用恢复文档启动其他候选任务。开始时 `main` 工作区干净，HEAD 为 `f3a4ffd`。

已实现统一会话入口、日常/灵寻两模式、混合历史和旧路由；新日常会话选择模型/工具/MCP/智能体并保存和恢复本次配置；旧智能体会话沿原配置继续使用，提供另开可配置会话的入口。后端复用现有 Agent，配置使用已有 JSON 列，补充新旧会话所有者/资源检查、行锁内追加校验、完成标记及取消清理。没有修改表结构、项目依赖/锁文件、真实配置或生产数据，没有提交、推送或部署。长期兼容取舍见 [ADR 0001](adr/0001-conversation-module-compatibility.md)。

环境：本机 macOS；前端 Node `26.0.0`、npm `11.12.1` 与已安装锁文件依赖（未重装，未验证 Node 20）；后端临时环境 `/private/tmp/agentruler-jev-switch-venv`，Python `3.13.5`、FastAPI `0.121.0`、SQLModel `0.0.27`、LangChain `1.2.15`、langchain-core `1.2.28`、httpx `0.28.1`。补装的 FastAPI/SQLModel 仅用于临时隔离环境；未修改项目依赖。测试先检查导入边界，未启动正式 FastAPI lifespan 或连接真实数据库、模型、MCP、记忆存储。

| 检查 | 实际命令及工作目录 | 状态 | 结果和证据 |
| --- | --- | --- | --- |
| 前端定向测试 | `npm test`；`src/frontend` | PASS | 20/20：混合历史、来源 ID 冲突、排序、旧链接、历史响应竞争、配置继承和恢复、三类 SSE 的错误/取消，以及日常缺少 done 的截断流 |
| 现有 lint 脚本 | `npm run lint`；`src/frontend` | PASS（仅命令） | 退出 0；根 TS 配置 `files: []` + references 下没有遍历应用源码，不能称全量类型通过 |
| 实际应用类型检查 | `./node_modules/.bin/vue-tsc --noEmit -p tsconfig.app.json`；`src/frontend` | FAIL（既有问题） | 退出 2，共 24 项诊断；将 `f3a4ffd` 前端源码只读导出到临时目录，用同一依赖检查，诊断与当前逐字相同，无本次新增。日志 `/tmp/agentruler-conversation-types-baseline.txt`、`/tmp/agentruler-conversation-types-current.txt` |
| 前端构建 | `npm run build`；`src/frontend` | PASS | 最终退出 0，33.23 秒；日志 `/tmp/agentruler-conversation-build-final.log`。保留 Sass 旧接口、Mars eval 与包大小警告，未扩大为构建优化任务 |
| 后端定向和回归 | `/private/tmp/agentruler-jev-switch-venv/bin/python -m unittest agentruler.test.test_workspace_chat agentruler.test.test_jev_decisions agentruler.test.test_jev_middleware agentruler.test.test_jev_workspace`；`src/backend` | PASS | 53/53（22 项新增会话测试 + 31 项 Jev 回归）；最终日志 `/tmp/agentruler-conversation-backend-final.log` |
| Python 编译 | 同一 Python 对 13 个变更 `.py` 执行 `py_compile.compile(..., doraise=True)`；仓库根目录 | PASS | 退出 0；只编译，不导入应用或初始化数据库 |
| 构建产物浏览器冒烟 | `node /tmp/agentruler-conversation-ui/run.mjs`；本机临时目录 | PASS | 15/15，使用已有缓存 Playwright 和全新无头 Chrome context、自托管 dist 和同源 Mock API；拦截外部资源，不使用用户浏览器会话。最终构建复验及哈希见下文 |
| 文档和差异 | 临时 Python 静态脚本、`git diff --check`；仓库根目录 | PASS | 13 份变更 Markdown、263 处本地路径引用均存在，代码围栏闭合；差异检查退出 0。摘要 `/tmp/agentruler-conversation-doc-check.json` |

后端新增测试使用真实 Pydantic/SQLModel 请求与上下文模型、实际业务方法、FastAPI ASGI 路由，DAO、模型、MCP 和记忆使用受控桩。覆盖智能体定义不变、默认及空覆盖、配置 JSON 保存、历史输入、记忆命名空间、模型/工具/MCP/知识库/Skill 拒绝、本人对话关联他人智能体拒绝、旧对话所有权、列表字段不被智能体覆盖、事务内所有者复核、错误与关闭流不发 done、嵌套生成器和后台标题任务清理；另验证实际 MCP 参数合并与嵌套脱敏方法。Jev 回归保持原有禁用/观察/执行、上下文、候选与回退断言，不连接真实判别服务。

浏览器 15 组覆盖：单入口与两模式、历史来源冲突/排序/筛选、智能体继承和清空覆盖、刷新恢复/续聊、旧配置提示及新建重置、旧链接/旧智能体续聊、正确来源删除/删除当前、单源列表失败重试、HTTP 错误、业务 error、HTTP 200 非 SSE、无 done 截断、不可读历史与已删除模型阻止发送、停止生成、流中切历史隔离、LingSeek 指导手册/返回/旧历史。分组和逐项结果保存在临时报告，截图已检查可读性；这些是 Mock 界面验证，不是真实服务端到端。

最终产物复验为 15 PASS/0 FAIL、退出 0，Chrome `156.0.8078.48`；`/tmp/agentruler-conversation-ui/result.json` 的 `dist/index.html` SHA256 为 `5d60bd07eb356d4a013ec3e82b8b3d6d0d091de24f266efdc9d62fbc8601920c`，与最终构建一致。截图 `01-unified-module.png`、`02-agent-conversation.png`、`03-lingseek-history.png`、`04-mobile-module.png` 位于同目录，桌面及 390×844 下正文和配置可读。窄屏历史列表隐藏来自既有 `preview-theme.css`，已用 `git show HEAD` 核实，未将其写成此次回归修复。

保留的失败与修正：首个 npm 命令误在仓库根目录执行，因没有 package.json 退出 254，随后在正确前端目录通过；临时类型基线提取脚本最初使用系统 Python 3.9 不支持的 tarfile 参数，修正安全路径检查后成功。一次中间构建因新增样式位于 Sass `@use` 前失败，调整顺序后最终构建通过，原日志 `/tmp/agentruler-conversation-build-sass-failure.log`。浏览器夹具最初使用不存在头像导致加载等待，修正假图片后运行；首个可执行产物报告为 9 PASS/2 FAIL，分别是测试选到 Element Plus 隐藏菜单、过期产物尚无灵寻返回入口，修正选择器并重建后全通过，原报告 `/tmp/agentruler-conversation-ui/first-build-result.json`。额外尝试原 `test_workspace_mcp_arguments` 时，临时环境缺 `pytz` 导入失败，不记通过；最终新增隔离测试直接验证相同实际辅助方法。

未执行：真实数据库写入/并发/备份恢复，真实模型、MCP、知识库和长期记忆调用，生产浏览器回归、部署、性能或完整 SEC-001 权限矩阵。新前端依赖日常 SSE 的 done，后续发布须前后端配套；旧智能体历史可继续交流，模型/工具/MCP 的本次覆盖应用于新日常会话。现有 24 项应用类型诊断及 lint 入口问题单独跟踪，不将其记为已修复或通过。

## 2026-10-29 本地容器更新

任务：LOCAL-UPDATE-001，关联 REQ-009、REQ-011。用户发现 `http://localhost:8090` 仍为旧版后明确授权更新本地前后端。原因是 Docker 镜像包含旧源码且没有源码挂载；此前 CONV-001 的本地实现和隔离测试未替换运行容器。本次使用 `main` 的 `f3a4ffd` 加已有未提交工作区构建，没有提交、推送或访问生产服务器。

环境为本机 macOS、Docker Desktop、Compose `5.5.1`，沿用本地项目 `docker`。开始时 Docker 未运行，启动 Desktop 后记录五个既有容器快照；以下“基础服务未重启”指此快照至应用替换完成期间 MySQL、Redis、MinIO 的 ID、镜像、启动时间和挂载均未改变。后端为 `linux/amd64`，按现有 `uv.lock` 冻结安装；没有修改项目依赖、锁文件或真实配置。开发 Compose 新增 `/app/memory_db` 持久化挂载，替换前停止后端、提取旧容器数据到此前不存在的宿主机 `docker/data/memory_db`，核对逐文件哈希后再启动。

| 检查 ID | 实际方法与命令 | 状态 | 结果与边界 |
| --- | --- | --- | --- |
| LOCAL-CHECK-001 | 容器/挂载快照、配置 SHA-256、配置备份及旧镜像标签；`compose config --quiet` | PASS | 五个容器归属原项目 `docker`，真实 YAML 仍只读挂载；保存两份配置和两应用旧镜像标签，没有输出密钥 |
| LOCAL-CHECK-002 | `docker compose -p docker -f docker/docker-compose.yml build backend frontend`；仓库根目录 | PASS | 两应用镜像构建退出 0；后端依赖缓存未命中，重新按锁文件安装，未将构建时间当作运行性能结果；完整日志受控保存 |
| LOCAL-CHECK-003 | 新后端镜像 `docker run --rm --network none --entrypoint python docker-backend:latest -m unittest agentruler.test.test_workspace_chat agentruler.test.test_jev_decisions agentruler.test.test_jev_middleware agentruler.test.test_jev_workspace` | PASS | 53/53、退出 0（测试执行 1.011 秒）；不挂载真实配置/数据库，模型、工具、MCP 等仍为隔离桩 |
| LOCAL-CHECK-004 | 停止两应用；MySQL 单事务 dump、复制向量/记忆、核对哈希，再 `up -d --no-deps --no-build backend frontend` | PASS | MySQL 备份 426625 字节；记忆 1 文件、向量 5 文件；记忆复制到持久化目录后与备份一致。仅重建两应用，无表迁移或数据清理 |
| LOCAL-CHECK-005 | 逐文件 SHA-256、配置校验、容器 inspect、启动日志固定标记 | PASS | 134 个前端源文件及 401 个后端 Python 文件与工作区一致；配置字节未变，记忆挂载有效；两应用 healthy，数据库/runtime/ASGI startup 成功且无对应初始化失败标记；基础三服务快照一致 |
| LOCAL-CHECK-006 | 初始化后再次单事务 dump，仅在内存中比较各表 INSERT 内容 | PASS | 前后均有 16 张含数据的表，16/16 内容一致；不输出记录、密钥或消息，不将此比较视作恢复演练 |
| LOCAL-CHECK-007 | `node /tmp/agentruler-local-update-checks/check.mjs`；实际 8090/7860 HTTP 与全 Mock API 浏览器冒烟 | PASS | 6/6、退出 0；实际 Vite 代码含新菜单/路由/配置/完成标记，后端 health/OpenAPI 配套、无凭据历史请求被拒绝；浏览器验证两模式、旧 workspace 链接、Agent 继承及 Mock SSE done、LingSeek 进入/返回；无未模拟 API、无 pageerror |
| LOCAL-CHECK-008 | 临时 `docs-check.py`、Markdown 链接/围栏及 `git diff --check`；仓库根目录 | PASS | 15 份变更 Markdown 的相对路径/标题锚点及围栏检查通过，差异无空白错误；暂存区保持为空，详细计数见受控 `docs-check.json` |

本次运行前端镜像 `sha256:f22fc266c78b57c6e7c0609202d80b85f91acc09c0f3cdba5ad8d32ce7873a1b`、后端镜像 `sha256:78dde5900c64793868ae7f1a388c719fd7ec3a4caca24ea082694ed95f763c0d`。旧镜像标签为 `agentruler-frontend:local-before-20261029-1115` 和 `agentruler-backend:local-before-20261029-1115`，如需恢复应用，应备份新增数据并通过本地 Compose override 成对指定旧镜像，不删除数据卷或覆盖现有配置。本次没有执行回滚或数据库恢复。

受保护备份与证据目录为本机 `/private/tmp/agentruler-local-update-20261029-1115`（权限 0700），包括 `before.json`、`after.json`、`build.log`、`image-tests.log`、配置备份、SQL、向量/记忆、`data-manifests.json`、`backups-complete.json`、`startup-summary.json` 和 `mysql-row-comparison.json`。配置与数据含敏感信息，不进入 Git 或公开附件；临时目录不替代长期/异地备份。

浏览器证据位于 `/tmp/agentruler-local-update-checks/result.json`、`run.log` 和 `01-live-new-module.png`，使用 Node `26.0.0`、Chrome `156.0.8078.48` 的全新 context；截图已检查，新菜单、日常/灵寻切换及模型/工具/MCP/智能体选择可读。业务 API 全部拦截模拟，直接访问真实后端仅 GET 健康/OpenAPI 和无凭据拒绝检查，没有登录或业务写入。容器实际源码哈希与页面检查共同确认 8090 已更新，不能据此宣称真实模型/MCP 端到端通过。

过程中曾因 Docker 尚未启动而连接 socket 失败，启动后重试成功；一次临时脚本 `py_compile` 被系统缓存目录权限阻止，指定临时缓存后检查通过。两者不记作应用测试失败。前述 CONV-001 的 24 项既有应用类型诊断仍未修复，未重复宣称类型检查通过；本轮未进行真实账号登录、模型/MCP/知识库对话、恢复/回滚、生产部署或完整业务端到端验收。

## 后续记录模板

每次追加验证记录时写明日期、任务/需求/验收 ID、代码提交与工作区情况、工具版本、工作目录、实际命令、测试数据与预期、退出码及实际结果，附仓库内脱敏日志或受控证据位置。外部日志不得泄露凭据、原始用户消息或私有配置。

`PASS` 表示执行且符合本项预期；`FAIL` 表示执行但不符合；`BLOCKED` 表示明确条件阻止执行；`NOT_RUN` 表示尚未执行。执行失败后保留原记录并补充修复和重测结果，不把计划命令冒充执行证据。
