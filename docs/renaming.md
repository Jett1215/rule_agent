# AgentRuler（智治）名称变更

项目英文名称统一为 **AgentRuler**，中文名称统一为 **智治**。
界面、后端服务标题、启动横幅、依赖元数据、启动脚本和技术文档均使用新名称。

## 后端入口与配置

Python 包由 `agentchat` 改为 `agentruler`，源码目录现在是
`src/backend/agentruler/`。本机的 `config.yaml` 随目录一起移动，已有密钥和连接信息继续保留。
其他电脑升级时，如有旧目录下的私有配置，请先将其移动到新目录，避免重新填写或覆盖配置。

从 `src/backend` 启动：

```bash
uvicorn agentruler.main:app --port 7860 --host 0.0.0.0
```

自定义脚本、IDE 启动参数及外部代码中的 Python 导入也应使用 `agentruler`。
配置中的 `server.name` 应设为 `AgentRuler`；配置模板和本机现有配置已经同步修改。
Docker 配置挂载路径改为 `/app/agentruler/config.yaml`，升级后需要重新构建镜像：

```bash
docker compose -f docker/docker-compose.yml up -d --build
```

开发环境容器名和网络名使用 `agentruler-` 前缀；Compose 服务名仍为
`backend`、`frontend`、`mysql`、`redis`、`minio`。
生产环境按原部署命令使用 `docker/docker-compose.production.yml` 重新构建，
生产镜像名称改为 `agentruler-backend` 和 `agentruler-minio`。

## 已有数据与部署标识

本次只修改项目名称和代码引用，不迁移或重建数据库与文件数据。以下标识保留以兼容已有部署：

- MySQL 数据库 `agentchat` 和账号 `agentchat_user`。
- 对象存储桶 `agentchat`、其访问地址及已存储的文件 URL。
- MySQL / Redis 数据卷及本机 `docker/data/` 下的数据。
- 生产 Compose 项目标识 `rule-agent` 和服务器路径 `/opt/rule_agent`。

不要仅为统一名称修改这些数据标识，也不要删除数据卷。需要更改时，应单独备份、迁移数据，
并同步更新真实配置、Compose 和 Nginx。项目根目录的实际文件夹名称可以继续使用旧名；
代码不依赖根文件夹名称。已有部署若移动根目录，应继续使用原 Compose 项目标识以复用数据卷。

## 上游来源和外部资源

原项目 AgentChat 的仓库链接、帮助文档地址、MIT 版权声明及上游图标资源 URL 保留原样，
确保署名准确、链接有效。这些外部地址不代表本项目仍使用旧名称。
