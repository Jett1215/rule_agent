# 配置与 Git 提交

此版本基于 [AgentChat](https://github.com/Shy2593666979/AgentChat)，保留原项目的
[MIT 许可证及版权声明](../LICENSE)。

项目现名为 **AgentRuler（智治）**。从旧版本升级时，先阅读
[名称变更说明](renaming.md)，确认后端包路径和现有数据配置。

## 仓库与本机文件

仓库提交源代码、依赖锁文件、测试、部署脚本和脱敏配置模板。
真实配置文件、环境变量文件、上传文件、数据库数据、备份、日志及编译缓存不提交。

| 场景 | 提交的模板 | 本机配置，不提交 |
| --- | --- | --- |
| 本地 Python 后端 | `src/backend/agentruler/config.example.yaml` | `src/backend/agentruler/config.yaml` |
| Docker 后端 | `docker/docker_config.example.yaml` | `docker/docker_config.yaml` |
| Docker 数据库与存储凭据 | `docker/.env.example` | `docker/.env` |

模板中的 `CHANGE_ME_*` 和 `YOUR_WORKSPACE_ID` 必须按实际服务替换。
YAML 不会自动展开环境变量；模型密钥填写在本机 YAML 中。
`docker/.env` 由 Compose 读取，用于创建 MySQL 和 MinIO 服务。

Jev 的可选工具门控与候选筛选默认关闭。`JEV_MODE=disabled|observe|enforce`
可同时控制两处能力：非空环境变量覆盖 YAML 的 `jev.mode`，未设置或空白则沿用 YAML。
非空值无效时仅告警并按 `disabled` 处理，不打印原值或阻断聊天。
`docker/.env` 中的 `JEV_MODE` 由开发和生产 Compose 传给后端；本地 Python 可在启动命令前设置。
它只覆盖模式，不改变 API key、独立能力开关、阈值和回退规则，也不是网页热切换。
配置根节点、对照命令及效果验证见[Jev 接入说明](jev-integration.md#用一个变量做对照测试)；
TypeSafe API key 同样只填写在本机 YAML 中。

## 首次配置 Docker

从项目根目录执行；已经存在的本机配置不要重新覆盖：

```bash
cp docker/docker_config.example.yaml docker/docker_config.yaml
cp docker/.env.example docker/.env
```

填写模型及工具密钥，配置存储和数据库：

- YAML 中 MySQL 连接地址的密码与 `.env` 的 `MYSQL_ROOT_PASSWORD` 一致。
- YAML 中 MinIO 的 `access_key_id` 与 `.env` 的 `MINIO_ROOT_USER` 一致。
- YAML 中 MinIO 的 `access_key_secret` 与 `.env` 的 `MINIO_ROOT_PASSWORD` 一致。
- `.env` 中 `MYSQL_PASSWORD` 用于 Compose 创建的 `agentchat_user`。

```bash
docker compose -f docker/docker-compose.yml config --quiet
docker compose -f docker/docker-compose.yml up -d --build
```

镜像只包含脱敏模板，真实 Docker 配置在容器启动时只读挂载到
`/app/agentruler/config.yaml`。修改 YAML 后重启后端即可读取新配置；修改代码时仍需
重新构建镜像。已有数据库的数据卷不会因为编辑 `.env` 自动更改数据库账号密码。

修改 `JEV_MODE` 等容器环境变量时，`restart backend` 不会更新已有容器环境。
从项目根目录执行 `docker compose --env-file docker/.env -f docker/docker-compose.yml up -d --no-deps --force-recreate backend`
使新变量生效；生产环境改用 `docker/docker-compose.production.yml`，并遵循已批准的部署流程。
仅更改变量无需重建镜像，完整示例见上述 Jev 接入说明。

## 本地 Python 后端

```bash
cp src/backend/agentruler/config.example.yaml src/backend/agentruler/config.yaml
```

填写本机服务地址和密钥后，按原项目步骤从 `src/backend` 启动后端。
本地与云端分别创建配置，各自使用独立的数据库和文件存储。

## 数据与备份

`docker/data/` 下的 MinIO 文件、Chroma 数据和备份不进入 Git。
MySQL / Redis 使用独立的 Docker 数据卷，也不会随 Git 提交上传。
同步代码不能替代数据库备份或迁移，不要用 `docker compose down -v` 清理需要保留的数据。

开发 Compose 的向量与记忆目录分别为 `docker/data/vector_db` 和 `docker/data/memory_db`。
记忆挂载于 2026-10-29 补充；升级旧本地容器前先停止后端并提取其 `/app/memory_db`，确认备份和目标目录后再替换容器，避免空目录遮住已有数据。具体更新边界见 [Docker 指南](../docker/README.md#持久化与更新边界)。

## 提交代码

```bash
git status --short
git add .
git diff --cached --stat
git commit -m "描述本次修改"
git push origin main
```

`.gitignore` 不会自动取消已被跟踪的文件；此版本已经将真实配置和 TypeScript
编译缓存从跟踪列表移除，但保留本机文件。

新仓库以整理后的代码快照作为初始提交，避免继承原项目历史中的未脱敏示例密钥。
原历史保留在本地 `upstream-history-local` 分支，原仓库保留为 `upstream`。
只推送 `main`，不要将保留原历史的分支或标签批量推送到新仓库。
