# 阿里云单机部署

部署目录：`/opt/rule_agent`。面向少量用户的试用环境采用 Ubuntu 24.04 x86_64、
Docker Compose 和宿主机 Nginx。2GB 内存的机器配置 4GB swap；该配置需要观察
实际负载，避免同时解析大量文件。

本次部署使用 GitHub 提交 `633348d`，应用包名为 `agentchat`。
若后续更新代码将包名重命名，需同时调整 Dockerfile 的启动模块、配置挂载路径及
镜像内的配置模板路径，再构建镜像。

## 文件与服务

- `docker/Dockerfile.production`：Python 3.12、Chromium、Pandoc、锁定的 Python 依赖。
  依赖从 `uv.lock` 导出并校验哈希，通过阿里云 PyPI 镜像下载。
- `docker/Dockerfile.minio`：从 MinIO 官方仓库的固定发布标签构建文件存储镜像。
- `docker/docker-compose.production.yml`：MySQL、Redis、MinIO 和单进程后端。
  数据库不映射公网端口；后端与 MinIO API 仅绑定 `127.0.0.1`。
- `docker/nginx.production.conf`：静态前端、`/api/` 流式代理及只读文件入口。
- `docker/docker_config.prod.yaml`、`docker/.env`：服务器专用配置，不提交 Git。

Nginx 将 `/files/` 与 `/icons/` 映射到 MinIO 的 `agentchat` 桶。应用的 MinIO
`base_url` 应为站点根地址，例如 `http://SERVER_IP/`，以使上传后的 URL 路径与
知识库下载时使用的对象键一致。仅对这两个对象前缀设置公开读取策略，保持写入私有。
正式域名与 HTTPS 配置好后，同步更新 `base_url`。

## 首次配置

从配置模板创建 `docker/docker_config.prod.yaml` 和 `docker/.env`。
为数据库、MinIO 及 `AUTHJWT_SECRET_KEY` 生成独立随机值；YAML 中的连接凭据应与
`.env` 一致。应用可以使用 `agentchat_user` 连接已创建的 `agentchat` 数据库。
模型和工具密钥仅写入服务器配置。设置 `server.env: prod`，向量库使用 `chroma`，
未部署 Elasticsearch 时保持禁用。

```bash
cd /opt/rule_agent
chmod 600 docker/.env docker/docker_config.prod.yaml
docker compose -f docker/docker-compose.production.yml config --quiet
docker compose -f docker/docker-compose.production.yml build
docker compose -f docker/docker-compose.production.yml up -d
```

前端在开发机执行 `npm ci` 和 `npm run build`，将生成的 `src/frontend/dist`
上传到服务器同名目录，可减少服务器构建时的内存占用。将 Nginx 配置安装到
`/etc/nginx/sites-available/rule-agent`，启用站点并通过 `nginx -t` 检查。
首次启动时先通过服务器本机接口创建管理员，再启动 Nginx 对外服务。

## 查看状态与更新

```bash
cd /opt/rule_agent
docker compose -f docker/docker-compose.production.yml ps
docker compose -f docker/docker-compose.production.yml logs --tail=100 backend
docker stats --no-stream
```

后端代码更新：

```bash
cd /opt/rule_agent
git pull --ff-only
docker compose -f docker/docker-compose.production.yml build backend
docker compose -f docker/docker-compose.production.yml up -d backend
```

前端代码更新后需重新构建并上传 `dist`。仅更改 YAML 配置后可重启后端：

```bash
docker compose -f docker/docker-compose.production.yml restart backend
```

MySQL 和 Redis 使用 Docker 数据卷；文件、向量和记忆存放于 `docker/data/`。
更新代码不会迁移或备份这些数据，需要保留配置、数据库备份和文件数据。
不要使用 `docker compose down -v` 清理需要保留的数据。

原开发版 Compose 保持独立，生产命令始终指定 `docker-compose.production.yml`。

## 域名与 HTTPS

需要先拥有域名，将计划使用的主机名添加 A 记录并指向服务器公网 IP。
根域名的主机记录为 `@`；子域名如 `chat.example.com` 的主机记录为 `chat`。
内地网站的 ICP 备案按阿里云要求办理，并在安全组放行 TCP 443。

服务器已安装 Certbot 及 Nginx 插件，已启用 `certbot.timer`。HTTP 配置的
`/.well-known/acme-challenge/` 从 `/var/www/letsencrypt` 提供证书验证文件。
购买域名、解析生效后，再为实际使用的域名申请证书并配置 HTTPS；证书签发之前
保持现有 HTTP 服务。HTTPS 启用后还需同步更新应用的对象存储 `base_url`，
检查头像、文件下载和流式聊天，并通过续期演练验证自动续期。
