# AgentRuler 前端开发

前端使用 Vue 3、TypeScript、Vite、Pinia、Vue Router 和 Element Plus，提供对话、Agent、技能、知识库、MCP、工作空间和用量统计等页面。工程规则见 [AGENTS.md](../../AGENTS.md)，完整文档见 [文档索引](../../docs/README.md)。

本页依据 2026-10-21 的源码和脚本静态整理；以下命令未在本轮文档整理中执行，不能视为构建或测试通过记录。

## 启动

使用 Node.js 20 和 npm，与当前 [前端 Dockerfile](../../docker/Dockerfile.frontend) 保持一致。首次安装和开发启动从项目根目录执行：

```bash
cd src/frontend
npm ci
npm run dev
```

默认地址为 `http://localhost:8090`；Vite 监听 `0.0.0.0`，端口被占用时应检查终端实际输出。先按 [后端说明](../backend/README.md) 配置并启动 `http://localhost:7860`。

开发服务器将 `/api` 代理到后端，代理目标依次取 `VITE_API_PROXY_TARGET`、`VITE_API_BASE_URL`、`http://localhost:7860`。需要修改代理目标时，在本目录创建不提交的 `.env.local`，例如：

```dotenv
VITE_API_PROXY_TARGET=http://localhost:7860
```

大部分 API 使用同源 `/api/v1/...`；`workspace.ts` 和 `lingseek.ts` 另读取 `VITE_API_BASE_URL`。因此推荐保持浏览器请求同源，开发时只调整 `VITE_API_PROXY_TARGET`。这些 `VITE_*` 值可进入浏览器构建产物，不得放入模型密钥或其他秘密。

## 目录与修改入口

| 路径 | 职责 |
| --- | --- |
| `src/pages/` | 各业务页面及页面逻辑 |
| `src/components/` | 通用组件、Agent 卡片和表单 |
| `src/apis/` | 按业务划分的接口和 SSE 调用 |
| `src/utils/request.ts` | Axios 封装、Bearer Token 和 401 处理 |
| `src/utils/session-id.ts` | 工作空间会话 ID 生成 |
| `src/store/` | Pinia 状态 |
| `src/router/index.ts` | 页面路由 |
| `src/assets/`、`src/style.css` 等 | 资源和界面样式 |
| `tests/` | 当前 Node 测试入口 |
| `vite.config.ts` | Vite 插件、开发端口和代理 |

对话流通过 `POST /api/v1/completion` 和 `fetch-event-source` 处理。修改流事件、取消请求或会话状态时，同时核对后端契约及 [API 参考](../../docs/reference/api.md)。认证 Token 保存在浏览器 `localStorage`，请求工具从中读取并设置 `Authorization`；前端路由检查不能替代后端权限检查。

## 构建与验证

以下命令均在 `src/frontend` 执行，依赖需先安装：

| 命令 | 实际作用 | 范围与限制 |
| --- | --- | --- |
| `npm run lint` | `vue-tsc --noEmit` | 当前根 references 配置下不遍历应用源码；未配置 ESLint；实际应用检查见下文 |
| `npm test` | `node --test tests/*.test.cjs` | UUID、会话历史与路由、配置继承/恢复和 SSE 契约；使用 TypeScript 转译与隔离桩，不包含真实服务端到端测试 |
| `npm run build` | `vite build`，生成 `dist/` | 构建脚本本身不执行 `vue-tsc`，类型检查需单独运行 |
| `npm run preview` | 本地预览 `dist/` | Vite 预览默认复用 `server.proxy`；仅供本地检查，不替代生产 Nginx 与真实环境联调 |

发布前应记录所用提交、Node/npm 版本、上述检查结果，并在连通测试后端的环境验证登录、聊天流、工作空间、文件上传和关键管理页面。现有 Node 测试不能证明这些用户流程可用；计划和记录分别维护在 [测试计划](../../docs/test-plan.md) 与 [验证报告](../../docs/verification-report.md)。

2026-10-27 CONV-001 核查：根 `tsconfig.json` 的 `files: []` 与 references 结构使当前 `npm run lint` 不遍历应用源码，退出 0 不能证明应用类型正确。实际应用检查使用 `./node_modules/.bin/vue-tsc --noEmit -p tsconfig.app.json`。任务前 `f3a4ffd` 与本次工作区均存在相同 24 项历史诊断，详见验证报告；本次未扩大修改其他管理页面或更改 lint 脚本。

会话模块主入口为 `/conversation`，`/workspace` 保持兼容。新日常对话可组合模型、工具、MCP 或带入智能体，配置仅作用于本次会话；历史记录聚合两种既有存储，旧智能体对话沿用原配置继续使用，亦可另开可配置的新日常会话。新增定向测试覆盖历史归一化、兼容路由、配置恢复、SSE 错误/完成标记与取消，隔离浏览器测试和真实服务的边界见验证报告。

## Docker 与生产部署

[开发 Compose](../../docker/README.md) 中的前端运行 Vite 开发服务器，端口 `8090`；镜像内默认没有源码热更新挂载，修改代码后需重新构建该服务。

[生产 Compose](../../docker/docker-compose.production.yml) 没有前端服务。生产前端在开发机执行 `npm ci`、类型检查、测试和构建后，将 `dist/` 交给 Nginx 静态托管；Nginx 负责 `/api/` 的 SSE 代理及 SPA 路由回退。具体发布、备份和回滚流程见 [云部署说明](../../docs/cloud-deployment.md)。
