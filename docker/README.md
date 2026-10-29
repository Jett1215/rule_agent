# AgentRuler Docker 指南

本目录同时提供开发 Compose 与生产 Compose。两套配置的端口、镜像、数据目录及前端部署方式不同，所有命令应明确指定文件。工程入口见 [AGENTS.md](../AGENTS.md) 与 [文档索引](../docs/README.md)。

本页最初依据 2026-10-21 的仓库文件静态整理；2026-10-29 本地前后端更新及记忆目录持久化的执行结果见[验证报告](../docs/verification-report.md#2026-10-29-本地容器更新)。生产历史和备份恢复计划见 [云部署说明](../docs/cloud-deployment.md)。

## 两种部署

| 项目 | 开发 `docker-compose.yml` | 生产 `docker-compose.production.yml` |
| --- | --- | --- |
| 后端 | Python 3.12、`uv sync --frozen`；Chrome/ChromeDriver linux64 | Python 3.12、从 `uv.lock` 导出并校验哈希安装；Chromium/Pandoc；单 Uvicorn worker |
| 前端 | Node 20、Vite 开发服务器，`8090:8090` | Compose 不含前端；宿主机 Nginx 托管 `dist/` |
| 后端端口 | `7860:7860` | `127.0.0.1:7860:7860` |
| MySQL | MySQL 8，`127.0.0.1:3307:3306` | MySQL 8，无宿主机端口映射 |
| Redis | Redis 7，`6379:6379` | Redis 7、AOF、无宿主机端口映射 |
| MinIO | 2023-03-20 发布镜像，`9000:9000`、`9001:9001` | 从固定 2025-09-06 发布标签构建，仅 `127.0.0.1:9000:9000` |
| Compose 项目 | 默认由目录/运行参数决定 | 固定 `name: rule-agent`，用于沿用现有数据卷 |

需准备 Docker Engine、Compose v2、构建依赖下载网络及足够的磁盘空间。开发后端明确指定 `linux/amd64`；ARM 主机需要可用的 amd64 模拟环境，性能和工具兼容性需实测。仓库没有通用最低容量验证，生产配置中的内存上限也不代表已经通过负载测试。

开发 Compose 的多个端口面向所有宿主机网络接口，不适合直接公开到互联网；按实际开发网络限制访问。生产入口和 TLS 另由 Nginx 管理。

## 开发配置与启动

从项目根目录执行；已有配置不要重复覆盖：

```bash
cp -n docker/docker_config.example.yaml docker/docker_config.yaml
cp -n docker/.env.example docker/.env
chmod 600 docker/.env docker/docker_config.yaml
```

本机编辑配置，字段以 [Docker YAML 模板](docker_config.example.yaml) 与 [Compose 环境模板](.env.example) 为准：

- YAML 的 MySQL 同步/异步连接主机均为 `mysql:3306`，库名保留 `agentchat`。默认模板使用 root，其密码对应 `.env` 的 `MYSQL_ROOT_PASSWORD`；改用 `agentchat_user` 时对应 `MYSQL_PASSWORD`，并核查初始化权限。
- Redis 使用 `redis:6379`；MinIO endpoint 使用 `minio:9000`。MinIO 的 YAML access key/secret 分别对应 `.env` 的 `MINIO_ROOT_USER` / `MINIO_ROOT_PASSWORD`。
- `storage.mode` 选择 `minio` 或 `oss`，不是旧的 `aliyun_oss` 根节点。MinIO 的 `base_url` 是浏览器可访问的对象地址，远程访问时不能保持浏览器自己的 `127.0.0.1`。
- 按实际功能填入 `multi_models`、`tools`；不部署 Elasticsearch 时保持禁用。当前 Compose 没有 Milvus/Elasticsearch 服务，`chroma` 使用挂载的本地目录。
- 应用只读挂载 YAML；YAML 不会展开环境变量。`.env` 只供 Compose 插值，不会自动变成所有容器的环境。
- 自有 JWT 模块读取 `AUTHJWT_SECRET_KEY`。生产 Compose 强制要求此值，但开发 Compose 尚未传入，`.env.example` 也没有该项。若需安全的开发登录凭据，应在本地 override 的后端 `environment` 中显式传入独立值；只把值写入 `.env` 不够。

配置、真实数据和备份不提交，详见 [配置与 Git](../docs/configuration-and-git.md)。只执行安静的配置检查，避免完整 `config` 输出展开后的秘密：

```bash
docker compose --env-file docker/.env -f docker/docker-compose.yml config --quiet
docker compose --env-file docker/.env -f docker/docker-compose.yml up -d --build
docker compose --env-file docker/.env -f docker/docker-compose.yml ps
```

也可以在配置完成后从根目录运行 `bash docker/start_linux.sh`，脚本会切换到 `docker/` 再执行 Compose。脚本仅等待 10 秒并展示状态，不代表首次初始化完成；后端 healthcheck 另有 180 秒启动宽限期。

访问前端 `http://localhost:8090`、后端 `http://localhost:7860`、API 文档 `http://localhost:7860/docs`；MinIO 控制台为 `http://localhost:9001`。前端通过 Vite 将同源 `/api` 请求代理到容器内后端。

首次启动可能创建数据库/表、写默认数据、上传头像并访问模型和 MCP。`/health` 只检查进程能否返回固定响应，不能验证这些依赖可用。应核查初始化日志并执行隔离环境业务验收。

## 管理与调试

以下命令均从项目根目录执行，操作开发环境：

```bash
docker compose --env-file docker/.env -f docker/docker-compose.yml ps
docker compose --env-file docker/.env -f docker/docker-compose.yml logs --tail=100 backend
docker compose --env-file docker/.env -f docker/docker-compose.yml restart backend
docker compose --env-file docker/.env -f docker/docker-compose.yml up -d --build backend frontend
docker compose --env-file docker/.env -f docker/docker-compose.yml stop
```

更改挂载 YAML 后重启后端；更改 Python/Vue 代码后重新构建对应镜像。当前默认 Compose 没有启用源码挂载或热更新。前端镜像使用 `npm install`，本地可重复安装则按 [前端 README](../src/frontend/README.md) 使用 `npm ci`。

已有本地项目 `docker` 只更新前后端时，先备份配置与应用数据，再使用以下命令；其他部署应保留其原有项目名。`--no-deps` 避免顺带重建 MySQL、Redis 和 MinIO。仅在宿主机编辑源码不会改变 8090 内的页面。

```bash
docker compose -p docker --env-file docker/.env -f docker/docker-compose.yml build backend frontend
docker compose -p docker --env-file docker/.env -f docker/docker-compose.yml up -d --no-deps backend frontend
```

后端远程调试可叠加 `docker-compose.debug.yml`：

```bash
docker compose --env-file docker/.env -f docker/docker-compose.yml -f docker/docker-compose.debug.yml up -d --build backend
```

调试 overlay 在容器启动时安装 `debugpy`，需要下载网络，并将调试端口绑定到宿主机 `127.0.0.1:5678`。退出调试后使用基础开发 Compose 重新创建后端。

容器内查询 MySQL 可用 `docker compose --env-file docker/.env -f docker/docker-compose.yml exec mysql mysql -u root -p`，密码交互输入。不要在命令行参数、聊天或日志中填写密码；不要通过打印 YAML、`.env` 或容器环境排查密钥问题。

## 持久化与更新边界

| 数据 | 开发持久化位置 | 生产持久化位置 |
| --- | --- | --- |
| MySQL | `mysql_data` 命名卷 | `rule-agent_mysql_data`（默认固定项目名） |
| Redis | `redis_data` 命名卷 | `rule-agent_redis_data`；配置 AOF |
| MinIO | `${DOCKER_VOLUME_DIRECTORY:-.}/data/minio_data`，默认 `docker/data/minio_data` | `docker/data/minio_data` |
| Chroma | `docker/data/vector_db` | `docker/data/vector_db` |
| Memory | `docker/data/memory_db` | `docker/data/memory_db` |

开发 Redis 挂载了数据卷但没有显式开启 AOF，其耐久性需核实。2026-10-29 开发 Compose 增加了 `/app/memory_db` 挂载；从此前容器更新时，先停止后端并备份/提取容器中该目录，确认宿主机目标目录没有需要保留的其他内容后再恢复到 `docker/data/memory_db`，否则空挂载会遮住原记忆数据。不要默认替换目录或项目名：这可能使 Compose 使用全新数据卷，表现为“数据丢失”。

更新镜像不会迁移已有表字段，也不会备份数据；修改 `.env` 不会自动修改已有 MySQL 卷中的账号密码。不要用 `down -v`、`docker volume rm` 或清空数据目录处理常规连接问题。生产发布前先完成 [备份及恢复演练](../docs/cloud-deployment.md#备份计划与操作草案)，然后按同页流程发布或回滚。

## 排查入口

连接失败时先核对对应 Compose 文件和服务状态，再检查容器内主机名、宿主机端口、账号一致性与已存在卷的历史凭据。工具失败时核对系统依赖、API 权限和外部网络；SSE 断流时核对代理缓冲和超时。只分享脱敏后的最小日志片段。

工程验证步骤见 [后端 README](../src/backend/README.md)、[前端 README](../src/frontend/README.md) 和 [测试计划](../docs/test-plan.md)。本页的静态核对不构成部署成功或恢复成功证据。
