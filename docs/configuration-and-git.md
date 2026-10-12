# 配置与 Git 提交

此版本基于 [AgentChat](https://github.com/Shy2593666979/AgentChat)，保留原项目的
[MIT 许可证及版权声明](../LICENSE)。

## 仓库与本机文件

仓库提交源代码、依赖锁文件、测试、部署脚本和脱敏配置模板。
真实配置文件、环境变量文件、上传文件、数据库数据、备份、日志及编译缓存不提交。

| 场景 | 提交的模板 | 本机配置，不提交 |
| --- | --- | --- |
| 本地 Python 后端 | `src/backend/agentchat/config.example.yaml` | `src/backend/agentchat/config.yaml` |
| Docker 后端 | `docker/docker_config.example.yaml` | `docker/docker_config.yaml` |
| Docker 数据库与存储凭据 | `docker/.env.example` | `docker/.env` |

模板中的 `CHANGE_ME_*` 和 `YOUR_WORKSPACE_ID` 必须按实际服务替换。
YAML 不会自动展开环境变量；模型密钥填写在本机 YAML 中。
`docker/.env` 由 Compose 读取，用于创建 MySQL 和 MinIO 服务。

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
`/app/agentchat/config.yaml`。修改 YAML 后重启后端即可读取新配置；修改代码时仍需
重新构建镜像。已有数据库的数据卷不会因为编辑 `.env` 自动更改数据库账号密码。

## 本地 Python 后端

```bash
cp src/backend/agentchat/config.example.yaml src/backend/agentchat/config.yaml
```

填写本机服务地址和密钥后，按原项目步骤从 `src/backend` 启动后端。
本地与云端分别创建配置，各自使用独立的数据库和文件存储。

## 数据与备份

`docker/data/` 下的 MinIO 文件、Chroma 数据和备份不进入 Git。
MySQL / Redis 使用独立的 Docker 数据卷，也不会随 Git 提交上传。
同步代码不能替代数据库备份或迁移，不要用 `docker compose down -v` 清理需要保留的数据。

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
