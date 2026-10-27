# 阿里云单机部署与恢复计划

本页保留历史部署背景，并给出当前仓库的部署、备份、恢复及回滚操作草案。工程规则见 [AGENTS.md](../AGENTS.md)，相关入口见 [文档索引](README.md) 和 [Docker 指南](../docker/README.md)。

2026-10-21 文档整理时仅静态核对仓库。2026-10-27 已按用户授权完成一次应用发布，实际连接、版本和备份范围见下文及[生产发布验证](verification-report.md#2026-10-27-生产发布)。通用恢复、回滚和证书操作仍为草案，没有通过本次发布完成演练。

## 历史记录与当前代码

### 已验证的服务器连接（2026-10-27）

用户确认的生产服务器为 `121.40.185.246`，SSH 用户为 `root`，端口为 `22`。本次已使用维护者本机已有的 `~/.ssh/agentruler_deploy` 密钥成功登录，并确认项目目录为 `/opt/rule_agent`。仅记录连接参数与密钥路径，不保存密码或私钥内容。

```bash
ssh -i ~/.ssh/agentruler_deploy -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes -p 22 root@121.40.185.246
```

该命令要求本机已有对应私钥和已核验的主机指纹；其他维护者应使用自己的获授权凭据。首次核实时服务器源码提交为 `df53c301cce956aa1d7ac5c2df3624dd94238170`，本次已更新为 `08f9b23bb50338a6403c6929d436a047eaff43f5`。这些是本次核实的快照，未来操作仍需重新检查运行状态。

### 已执行的应用发布（2026-10-27）

两次英文提交 `a0500b8`（文档与前端小改动）、`08f9b23`（Jev 模块）已推送至 `origin/main`。生产源码快进到后一提交；后端重建镜像并单独重建容器，前端在开发机完成检查和构建后发布到 `/opt/rule_agent/src/frontend/dist`。服务器 `docker/.env` 显式设置 `JEV_MODE=disabled`，运行容器已核实关闭；真实 YAML 与其他环境配置保持原样。

公网入口为 <http://121.40.185.246/>。MySQL、Redis、MinIO 容器 ID 和启动时间未变化；Nginx 配置未修改，也未重启。备份位于 `/var/backups/rule-agent/20261027T101329Z-08f9b23`，包含旧应用镜像、前端、配置、Nginx 站点、MySQL dump 和停后端后的向量/记忆目录；不包含 Redis/MinIO 数据全量备份，不等于完整灾备或恢复演练。旧前端还保留在该目录的 `frontend-directory-before/`。

本次完成健康、注册登录、鉴权、模型读取及一次无工具工作台 SSE 验证，临时账号与关联数据已清理；具体命令、校验和、证据及未验证范围统一见[验证报告](verification-report.md#2026-10-27-生产发布)。

2026-10-13 的部署记录使用 Git 提交 `633348d`、旧后端包名 `agentchat`，部署目录为 `/opt/rule_agent`，环境描述为 Ubuntu 24.04 x86_64、Docker Compose、宿主机 Nginx，2GB 内存配 4GB swap，面向少量用户试用。原记录称已安装 Certbot/Nginx 插件并启用 `certbot.timer`；这些是历史记录，本轮未核验其当前状态。

当前仓库包名是 `agentruler`：生产 Dockerfile 启动 `agentruler.main:app`，配置挂载到 `/app/agentruler/config.yaml`。不能据此推定云端已经更新。发布前必须对照实际运行镜像、启动模块和挂载目标，避免用当前配置覆盖仍在运行的旧镜像。

为兼容已有数据，以下标识继续保留：部署目录 `/opt/rule_agent`、生产 Compose 项目名 `rule-agent`、MySQL 库 `agentchat`、账号 `agentchat_user`、MinIO 桶 `agentchat`。名称变更不包含数据重建，详见 [名称变更说明](renaming.md)。

## 当前生产文件与服务

| 文件/服务 | 当前仓库行为 |
| --- | --- |
| `docker/Dockerfile.production` | Python 3.12、Chromium/Pandoc、基于 `uv.lock` 导出并校验哈希安装依赖，单个 Uvicorn worker |
| `docker/Dockerfile.minio` | 从固定发布标签构建 MinIO 镜像 |
| `docker/docker-compose.production.yml` | MySQL、Redis、MinIO、后端；无前端容器；固定项目名 `rule-agent` |
| 后端和 MinIO API | 分别绑定宿主机 `127.0.0.1:7860`、`127.0.0.1:9000` |
| MySQL、Redis | 无宿主机端口映射；使用命名卷，Redis 启用 AOF |
| `docker/nginx.production.conf` | 静态前端、SPA 回退、关闭缓冲的 `/api/` SSE 代理、只允许 GET/HEAD 的 `/files/` 与 `/icons/` 代理 |
| 真实配置 | `docker/docker_config.prod.yaml`、`docker/.env`；不提交 Git |

Nginx 静态目录仍为 `/opt/rule_agent/src/frontend/dist`，对象读取代理到 MinIO 的 `agentchat` 桶。此路由约定下 `storage.minio.base_url` 应为站点根 URL，例如 `https://chat.example.com/`；直接访问 MinIO 的开发配置则带桶路径。仅公开所需 `files/`、`icons/` 前缀的读取，写入保持私有。该策略需在真实 MinIO 上单独配置并验证，Nginx 配置不会自动修改桶策略。

## 首次配置与发布前检查

前提：已准备 Docker/Compose v2、宿主机 Nginx、所需下载网络、可用磁盘和运维权限；容量需依据真实负载验证。确认云端现状、维护窗口、恢复负责人及回退版本后，在部署目录准备配置。已有文件不要覆盖：

```bash
cd /opt/rule_agent
cp -n docker/docker_config.example.yaml docker/docker_config.prod.yaml
cp -n docker/.env.example docker/.env
chmod 600 docker/.env docker/docker_config.prod.yaml
```

按模板编辑真实配置并通过受控渠道注入秘密，不打印内容：

- `.env.example` 包含 MySQL/MinIO 变量及可选的 Jev 总开关 `JEV_MODE`；生产还必须在 `.env` 增加独立的 `AUTHJWT_SECRET_KEY`，因为生产 Compose 使用必填插值。
- MySQL、MinIO 的 YAML 凭据需与 `.env` 一致；使用 `agentchat_user` 时确认已有 `agentchat` 库及初始化所需权限。已有数据卷的密码不会随 `.env` 自动更改。
- 设置 `server.env: prod`，按已部署服务选择向量模式；当前单机 Compose 采用本地 `chroma`，未部署 Elasticsearch 时保持禁用。密钥和模型字段依模板填写。
- 配置浏览器可访问的存储 `base_url`；核对默认图标 URL、MCP 地址与生产网络，避免沿用测试端点。

下文在同一 Bash 会话使用此函数，明确环境文件与 Compose 文件：

```bash
dcprod() {
  docker compose --env-file docker/.env -f docker/docker-compose.production.yml "$@"
}
dcprod config --quiet
git rev-parse HEAD
git status --short
dcprod ps
```

不使用完整 `docker compose config` 或 `docker inspect` 环境输出排查秘密。确定提交与变更列表后，先在隔离环境验证后端初始化、权限、前端构建与核心回归，再执行下节备份。前端可在开发机按 [前端 README](../src/frontend/README.md) 完成 `npm ci`、类型检查、测试和构建，产物先上传到临时发布目录并核对提交及校验和。

已有部署先完成备份并确认恢复路径；全新空环境无需执行依赖现有容器的备份命令，但必须确认不会覆盖原部署。之后当前代码可用 `dcprod build` 构建并 `dcprod up -d` 启动。首次启动会创建表和默认数据，并可能调用模型/MCP、上传头像；不能把它当成无副作用的健康检查。Nginx 站点安装/启用与管理员初始化应在关闭公网入口或限制来源的条件下完成，完成后再对外开放。Nginx 变更先通过 `nginx -t`，再按宿主机服务管理方式 reload。

`/health` 仅返回固定进程响应；发布验收还应检查初始化日志、登录和权限、对话 SSE、工作空间、文件上传下载与知识库检索。命令输出或失败日志可能含敏感值，记录时脱敏。

## 备份计划与操作草案

以下草案适用于当前生产 Compose 和本机 MinIO/Chroma。若实际使用 OSS、Milvus、外部数据库或其他写入方，应先补齐对应快照/版本与一致性方案。备份频率、保留周期、异地位置、加密方式、RPO/RTO 由负责人确认，当前没有已验证目标。

需要维护窗口、足够磁盘，以及读取 Docker 数据和受保护配置的权限。先核对运行镜像对应源码提交，确认本机源码、Compose 与运行环境相符；未提交变更需另存受控源码快照，不能只记录 HEAD。先在站点入口暂停新请求、等待正在执行的对话/文件任务结束，并确认没有其他数据库或对象写入方。不要对共享 Nginx 实例盲目整机停服。以下在部署目录、已定义 `dcprod` 的 Bash 会话执行；任何一步失败都应停止并处理，不能把不完整目录标为成功备份：

```bash
set -euo pipefail
umask 077
TASK_BACKUP_DIR="/var/backups/rule-agent/$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$TASK_BACKUP_DIR/redis-data"
git rev-parse HEAD > "$TASK_BACKUP_DIR/commit.txt"
dcprod images > "$TASK_BACKUP_DIR/images.txt"
TASK_BACKEND_IMAGE="$(dcprod images -q backend)"
docker image inspect --format '{{.Id}}' "$TASK_BACKEND_IMAGE" > "$TASK_BACKUP_DIR/backend-image-id.txt"
tar -czf "$TASK_BACKUP_DIR/deployment.tgz" docker/.env docker/docker_config.prod.yaml docker/docker-compose.production.yml docker/nginx.production.conf
tar -czf "$TASK_BACKUP_DIR/frontend-dist.tgz" -C src/frontend dist
docker image save -o "$TASK_BACKUP_DIR/images.tar" "$(dcprod images -q mysql)" "$(dcprod images -q redis)" "$(dcprod images -q minio)" "$TASK_BACKEND_IMAGE"

dcprod stop backend minio
dcprod exec -T mysql sh -eu -c 'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" exec mysqldump --user=root --single-transaction --routines --triggers --events --databases agentchat' < /dev/null > "$TASK_BACKUP_DIR/mysql.sql"
dcprod exec -T redis redis-cli SAVE
dcprod stop redis
TASK_REDIS_CONTAINER="$(dcprod ps -a -q redis)"
docker cp -a "$TASK_REDIS_CONTAINER:/data/." "$TASK_BACKUP_DIR/redis-data"
tar -czf "$TASK_BACKUP_DIR/application-data.tgz" -C docker data
dcprod start redis minio backend
```

`deployment.tgz` 和 SQL 备份包含秘密及用户数据，只保存在受保护、加密并限制访问的备份系统中，不放入 Git、公开产物或聊天。上例通过容器环境向数据库客户端传递密码，避免把密码放进进程参数；不要开启 shell trace。若宿主机已安装的 Nginx 站点、证书或站点链接与仓库模板不同，应另行受控备份实际文件与权限，不能只依赖仓库模板。

在备份目录为各归档和 `mysql.sql` 计算 SHA-256，记录服务版本、UTC 时间、数据目录/卷归属、文件大小、备份窗口及成功/失败结果；将这些记录与备份一起异地保存。校验和只能确认文件完整性，必须通过下节恢复演练确认可用。重新开放入口前检查服务状态和关键业务；失败时由运维决定继续维护或回退。

## 恢复演练与恢复草案

恢复会写入数据库和数据目录，只能由负责人在确认目标与维护窗口后执行。优先在独立主机/VM 演练，使用独立网络与凭据、阻断真实模型/MCP/外发工具；当前 Compose 有固定项目名、回环端口和相对数据目录，不能仅复制到同一主机的新目录就认为已隔离。

1. 验证备份校验和、完整性及可用磁盘，取出 `commit.txt` 对应的源码快照及另存的本机变更，核对备份 Compose、配置挂载路径和镜像包名。历史 `agentchat` 镜像必须配套历史挂载路径，不能混用当前 `agentruler` 配置。
2. 在独立目标的 `/opt/rule_agent` 恢复 `deployment.tgz`，设置配置权限，检查目标数据目录和卷为空且没有生产数据。在本次恢复会话明确设置 `TASK_BACKUP_DIR` 为选定备份的绝对目录，切换到部署目录并重新定义上文的 `dcprod` 函数。根据演练网络替换真实外部凭据/地址后执行 `dcprod config --quiet`。通过 `docker image load -i "$TASK_BACKUP_DIR/images.tar"` 加载镜像；按 ID 保存的归档可能没有标签，须对照 `images.txt` 和备份 Compose，为 MySQL、Redis、MinIO、后端逐一恢复对应标签，避免启动时意外拉取其他版本。
3. 在后端、MinIO 和 Redis 均停止时，把 `application-data.tgz` 解压到目标 `docker/`，保留目录权限。该归档包含 MinIO、向量和 memory 数据，应作为同一时间点整体恢复；不要对运行中的数据目录覆盖解压。
4. 启动 MySQL 并等待健康，在隔离目标导入备份。当前 dump 含建库和表重建语句，不能导入仍需保留内容的生产库：

   ```bash
   dcprod up -d mysql
   dcprod exec -T mysql sh -eu -c 'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" exec mysql --user=root' < "$TASK_BACKUP_DIR/mysql.sql"
   ```

5. 在尚未启动 Redis 的目标创建容器/卷，再恢复其数据；这会覆盖隔离目标的 Redis 内容，需先确认该卷无须保留：

   ```bash
   dcprod create redis
   TASK_REDIS_CONTAINER="$(dcprod ps -a -q redis)"
   docker cp -a "$TASK_BACKUP_DIR/redis-data/." "$TASK_REDIS_CONTAINER:/data"
   dcprod up -d redis minio
   ```

6. 恢复 `frontend-dist.tgz` 到目标 `src/frontend/`，核对实际 Nginx 站点与对象读取策略。确认数据库、存储与网络均为演练目标，再启动备份后端镜像，检查初始化是否改写数据或触发外部请求。
7. 验证关键表计数与抽样记录、文件存在及下载、知识库索引与检索、头像、登录与权限、聊天/工作空间 SSE。记录实际恢复耗时、数据时间点和失败项，完成后清理演练资源并保护演练数据；只有留有这些证据才可标记演练通过。

正式灾难恢复沿用已通过的演练步骤，另需明确可接受的数据时间点、切换入口、旧主机写入隔离及恢复后数据核对；不能直接以文档草案取代实际演练。

## 更新与回滚

发布应指定已审核的提交，不将无约束 `git pull` 作为生产更新流程。保留发布前源码提交、Compose/配置、旧镜像、前端产物和成套数据备份。更新仅重建应用镜像和切换已验证前端产物；数据库结构和语义兼容性需单独评估。

应用更新示例，在已完成前置检查和备份后执行：

```bash
dcprod build backend
dcprod up -d --no-deps backend
dcprod ps
dcprod logs --tail=100 backend
```

生产 Compose 后端使用固定 `agentruler-backend:production` 标签，重建会覆盖标签，因此必须保留旧镜像 ID 或独立发布标签。前端在维护窗口将已校验的新 `dist` 与旧目录整体切换，保留旧目录，避免只覆盖文件留下混合资源。

若新版本仅应用层变化且确认数据库/对象数据仍与旧版兼容：暂停入口与后端；从备份加载旧镜像并将备份 ID 恢复到 Compose 使用的标签；恢复配套旧配置、旧 Compose 与前端目录；重新创建后端并执行相同验收。旧版包路径与挂载位置必须配套。不要只回退 Git 源码后继续使用新镜像。

若存在不兼容结构/数据变更或无法确定兼容性，先停写，按已演练的成套备份恢复数据库、对象、向量及必要的 Redis 状态；仅回退应用可能继续损坏数据。恢复意味着放弃备份时间点之后的写入，需由负责人确认影响和补偿方案。禁止通过 `docker compose down -v` 或删除卷实施回滚。

## 域名与 HTTPS

历史方案预留 Nginx 的 `/.well-known/acme-challenge/`，目录为 `/var/www/letsencrypt`。正式域名需完成解析及对应部署地区要求；安全组和防火墙按实际入口开放。先核实当前站点、证书及 Certbot timer，再针对真实主机名申请/续期证书，不依据历史记录推定有效。

启用 HTTPS 后同步更新对象存储 `base_url`，验证头像、文件下载、登录和 SSE，随后执行证书续期演练并记录结果。HTTP→HTTPS、Nginx 配置和证书变更同样需要保留可恢复的旧配置。验收证据统一写入 [验证报告](verification-report.md)。
