# 企业微信会话存档可视化后台与同步服务

本项目是企业微信会话内容存档的 v1 实现，代码集中在 `app/weCom/`。服务按 `spec/Tech_weCom_sync_service.md` 落地，包含 FastAPI 后端、DB 游标 Worker、React 可视化工作台、MySQL schema、Docker Compose 和 `wecomctl` CLI。

## 基本能力

- 接收通讯录、客户联系、客户群、会话存档同意和产生会话回调。
- 通过 Worker 框架按 `sync_cursor.message_seq` 进行会话拉取、转换和补偿。
- 保存 Raw 数据、处理状态和标准化业务数据到 MySQL。
- 支持通过 CSV 或 API 导入员工、部门和可观测员工名单，用于通讯录回调被占用或通讯录 API 尚未接入时先跑后台。
- 前端支持按企业通讯录配置观测员工、查看观测员工会话列表、聊天时间线、当前会话搜索、详情抽屉、撤回状态、不支持消息占位和图片附件下载/重试状态。
- 图片附件元数据会随消息解析入库，媒体二进制在前端点击下载后由后端上传到阿里云 OSS；浏览器不直接访问 OSS。
- 附件通过阿里云 OSS 内网 Endpoint 存储，通过后端鉴权 API 代理读取。
- CLI 输出回调地址、校验配置、检查健康状态和触发一次同步。

## 边界

Do:

- 单个企业微信主体。
- 内部固定管理员 token 鉴权。
- 支持文本、图片、链接、agree/disagree、撤回和不支持类型占位。
- 无 secret 时可用 stub 跑通 API、Worker、CLI 和前端演示。
- 通讯录回调不可用时，可以用 CSV 导入名单；后续再切换到通讯录 API 定时同步。

Don't do:

- 不做多企业微信主体隔离。
- 不接入飞书/SSO 或完整多用户权限。
- 不兼容历史本地附件卷；切换 OSS 后旧本地文件由运维清理。
- 不完整解析语音、视频、文件、小程序、会话记录等复杂类型。
- 不把 secret、私钥或 Linux SDK 提交进仓库。
- CSV 导入只维护本系统员工/部门/可观测名单，不会反向写入企业微信通讯录。
- 前端不会在接口无权限、后端不可用或没有同步数据时展示内置假会话；这些场景显示为空态。

## 本地开发

后端：

```bash
cd app/weCom/backend
python -m pip install -e ".[dev]"
pytest -q
uvicorn wecom_app.main:app --reload --port 8717
```

前端：

```bash
cd app/weCom/frontend
npm install
npm run dev
```

默认前端使用 `VITE_INTERNAL_ADMIN_TOKEN`，未配置时为 `dev-admin-token`。API 不可用、鉴权失败或没有同步数据时，前端展示空态；测试数据只用于自动化测试，不进入部署页面。

## Docker 部署

```bash
cd app/weCom
cp .env.example .env
cp .env.chatbi-mcp.example .env.chatbi-mcp
cp .env.echarts-mcp.example .env.echarts-mcp
docker compose up --build
```

服务器已有 `mysql`、`wecom-api`、`wecom-worker`、`wecom-frontend` 时，首次增加 ChatBI 两个 MCP 服务建议执行：

```bash
docker compose up -d --build wecom-api chatbi-mcp echarts-mcp
```

其中 `chatbi-mcp`、`echarts-mcp` 是新增服务；`wecom-api` 需要包含 `/api/chatbi/*` 接口。`mysql`、`wecom-worker`、`wecom-frontend` 通常不需要重启。后续只调整 MCP 配置时，重启对应 MCP 即可；如果只改 `CHATBI_TOKEN`，需要同时重启 `wecom-api` 和 `chatbi-mcp`。

服务端口：

- API: `http://localhost:8717`
- Frontend: `http://localhost:5173`
- MySQL: `localhost:3306`
- ChatBI MCP SSE: `http://localhost:8731/sse`
- ECharts MCP SSE: `http://localhost:8732/sse`

如果 OpenClaw 部署在同一台服务器的另一个 Docker Compose 里，推荐把两个 compose 接到同一个 Docker external network，而不是让 OpenClaw 走公网域名访问 MCP。

先创建共享网络：

```bash
docker network create openclaw-shared
```

在本项目 `app/weCom/docker-compose.yml` 中把 `chatbi-mcp` 和 `echarts-mcp` 接入该网络：

```yaml
services:
  chatbi-mcp:
    networks:
      - default
      - openclaw-shared

  echarts-mcp:
    networks:
      - default
      - openclaw-shared

networks:
  openclaw-shared:
    external: true
```

OpenClaw 所在 compose 也接入同一个 `openclaw-shared` 网络后，可使用容器内地址：

```text
http://chatbi-mcp:8731/sse
http://echarts-mcp:8732/sse
```

如果 WeCom 和 OpenClaw 都已经在服务器上跑起来，不想立即改 compose，也可以把已运行的 MCP 容器临时接入 OpenClaw 网络：

```bash
cd app/weCom

# 先找到 OpenClaw 所在 Docker network，例如 openclaw_default。
docker network ls

# 再找到两个 MCP 容器名。
docker compose ps chatbi-mcp echarts-mcp

# 把 MCP 容器接入 OpenClaw network，并设置稳定别名。
docker network connect --alias chatbi-mcp <openclaw-network> <chatbi-mcp-container>
docker network connect --alias echarts-mcp <openclaw-network> <echarts-mcp-container>
```

接入后，在 OpenClaw 容器内应能访问：

```bash
curl http://chatbi-mcp:8731/health
curl http://echarts-mcp:8732/health
```

临时 `docker network connect` 在容器重建后需要重新执行；长期部署建议把两个 compose 都显式接入同一个 external network。

如果暂时不改 Docker 网络，也可以通过宿主机端口访问，例如 Linux Docker 中配置 `host.docker.internal` 到 host gateway 后访问 `http://host.docker.internal:8731/sse` 和 `http://host.docker.internal:8732/sse`。

数据库迁移：

```bash
cd app/weCom/backend
alembic upgrade head
```

## Secret 与 SDK 配置

`.env` 中配置非文件密钥：

- `WECOM_CORP_ID`
- `WECOM_CONTACT_SECRET`: 通讯录 API 拉取员工/部门时需要；只使用 CSV 导入名单时可暂时留空。
- `WECOM_CONTACT_CALLBACK_TOKEN`: 通讯录变更回调使用；被其他项目占用时可留空，改用 CSV 导入或后续通讯录 API 定时同步。
- `WECOM_CONTACT_ENCODING_AES_KEY`: 通讯录变更回调使用；被其他项目占用时可留空。
- `WECOM_CUSTOMER_API_SECRET`: 客户联系 API access_token 使用的 secret。通常填写企业微信后台中已配置为客户联系“可调用应用”的自建应用 Secret；如果你的企业后台仍提供客户联系 API Secret，也可填该值。
- `WECOM_CUSTOMER_CALLBACK_TOKEN`
- `WECOM_CUSTOMER_ENCODING_AES_KEY`
- `WECOM_ARCHIVE_SECRET`
- `WECOM_ARCHIVE_CALLBACK_TOKEN`
- `WECOM_ARCHIVE_ENCODING_AES_KEY`
- `INTERNAL_ADMIN_TOKEN`
- `VITE_INTERNAL_ADMIN_TOKEN`
- `MESSAGE_SYNC_BATCH_LIMIT`: SDK 单批拉取上限，默认 `1000`。
- `MESSAGE_BOOTSTRAP_MAX_BATCHES`: 首次没有 `message_seq` 游标时最多连续拉取批次数，默认 `200`。
- `MESSAGE_SYNC_NEWEST_FIRST`: 已拉取 Raw 消息是否按消息时间从新到旧优先解析，默认 `true`。
- `ATTACHMENT_STORAGE_BACKEND`: 附件存储后端，目前仅支持 `aliyun_oss`。
- `ALIYUN_OSS_ACCESS_KEY_ID`
- `ALIYUN_OSS_ACCESS_KEY_SECRET`
- `ALIYUN_OSS_BUCKET`
- `ALIYUN_OSS_PREFIX`: bucket 下的对象前缀，默认 `wecom/`；实际对象会继续按类型分层，例如 `wecom/image/YYYY/MM/DD/...`。
- `ALIYUN_OSS_INTERNAL_ENDPOINT`: 后端访问 OSS 的内网 Endpoint，例如 `oss-cn-shanghai-internal.aliyuncs.com`。
- `ALIYUN_OSS_PUBLIC_BASE_URL`: Infra 提供的 HTTPS 访问地址，当前仅保留为配置，不返回给前端。
- `ALIYUN_OSS_CONNECT_TIMEOUT_SECONDS`: OSS 连接超时，默认 `10`。
- `ALIYUN_OSS_READ_TIMEOUT_SECONDS`: OSS 读取超时，默认 `60`。
- `CHATBI_TOKEN`: ChatBI 专用接口静态 token，BE 和 `chatbi-mcp` 需保持一致。
- `APT_MIRROR`: Docker 构建 `echarts-mcp` 时使用的 Debian apt 镜像域名，默认 `mirrors.aliyun.com`。
- `NPM_REGISTRY`: Docker 构建两个 MCP 时使用的 npm registry，默认 `https://registry.npmmirror.com`。

ChatBI MCP 配置写入 `app/weCom/.env.chatbi-mcp`：

- `CHATBI_BE_BASE_URL`: `chatbi-mcp` 调用 BE 的地址，Docker 内默认 `http://wecom-api:8717`。
- `CHATBI_TOKEN`: 透传到 BE 的静态 token，需与 BE `.env` 中的 `CHATBI_TOKEN` 一致。
- `CHATBI_MCP_PORT`: `chatbi-mcp` 监听端口，默认 `8731`。

示例：

```env
CHATBI_BE_BASE_URL=http://wecom-api:8717
CHATBI_TOKEN=<same-static-token-as-wecom-api>
CHATBI_MCP_PORT=8731
```

注意：`CHATBI_TOKEN` 必须配置两处，且值完全一致：

- `app/weCom/.env`: 给 `wecom-api` 校验 `X-ChatBI-Token` 使用。
- `app/weCom/.env.chatbi-mcp`: 给 `chatbi-mcp` 调用 BE 时透传 header 使用。

ECharts MCP 配置写入 `app/weCom/.env.echarts-mcp`：

- `ECHARTS_MCP_PORT`: `echarts-mcp` 监听端口，默认 `8732`。
- `CHART_OSS_ACCESS_KEY_ID`
- `CHART_OSS_ACCESS_KEY_SECRET`
- `CHART_OSS_BUCKET`
- `CHART_OSS_PREFIX`: bucket 下的对象前缀，例如 `wecom/`；图表对象会写到 `wecom/charts/YYYY/MM/DD/...`。
- `CHART_OSS_ENDPOINT`: 例如 `oss-cn-shanghai.aliyuncs.com`。
- `CHART_OSS_REGION`: 例如 `oss-cn-shanghai`。
- `CHART_OSS_PUBLIC_BASE_URL`: 图表图片对 OpenClaw/飞书可访问的 HTTPS 前缀；如果 `CHART_OSS_PREFIX=wecom/`，这里建议写到同一层公开前缀，例如 `https://res.jhpy.com/wecom/`；为空时使用 OSS SDK 返回的 URL。

示例：

```env
ECHARTS_MCP_PORT=8732
CHART_OSS_ACCESS_KEY_ID=<aliyun-oss-access-key-id>
CHART_OSS_ACCESS_KEY_SECRET=<aliyun-oss-access-key-secret>
CHART_OSS_BUCKET=jhjy-prod
CHART_OSS_PREFIX=wecom/
CHART_OSS_ENDPOINT=oss-cn-shanghai-internal.aliyuncs.com
CHART_OSS_REGION=oss-cn-shanghai
CHART_OSS_PUBLIC_BASE_URL=https://res.jhpy.com/wecom/
```

`CHART_OSS_ENDPOINT=oss-cn-shanghai-internal.aliyuncs.com` 只适用于 `echarts-mcp` 所在服务器可访问阿里云上海地域 OSS 内网 Endpoint 的场景；否则改用公网 Endpoint `oss-cn-shanghai.aliyuncs.com`。OSS 不需要访问 `8732`，`8732` 只需要对 OpenClaw 容器可达。

文件型密钥和 SDK 通过只读挂载：

```text
./secrets/wecom_archive_private_key.pem -> /run/secrets/wecom_archive_private_key.pem
./vendor/wecom_sdk -> /opt/wecom_sdk
```

兼容说明：旧变量 `WECOM_CUSTOMER_SECRET` 仍可作为 `WECOM_CUSTOMER_API_SECRET` 的兜底读取，但新部署建议统一使用 `WECOM_CUSTOMER_API_SECRET`，避免误解为企业微信后台存在独立的“客户联系 secret”入口。

回调模块已支持企业微信加密 XML 的 `msg_signature` 校验、`Encrypt` 字段解密、CorpID 校验和基础事件字段解析。会话内容拉取依赖企业微信会话存档 Linux SDK；`./vendor/wecom_sdk` 未挂载或会话存档 Secret/私钥缺失时，Worker/API 无法拉取真实消息或下载图片媒体。

附件存储说明：

- `wecom-worker` 只自动解析文本、撤回、链接和图片元数据，不自动下载图片二进制。
- 前端对未下载图片显示 `下载图片`，对失败图片显示 `重试下载图片`，对过期媒体显示 `文件已过期/无法下载`。
- `POST /api/attachments/{id}/download` 会在后端认领单个下载任务，未完成时返回 `202 Accepted` 和 `downloading` 状态；重复请求同一附件不会创建重复下载任务。
- 下载任务完成后，附件状态变为 `downloaded`，前端使用 `/api/attachments/{id}/content` 获取内容。
- 由于 OSS bucket 限内网访问，`/api/attachments/{id}/content` 会由 API 服务从 OSS 内网 Endpoint 读取并流式返回，不会把 OSS URL 暴露给浏览器。
- 新上传对象只写阿里云 OSS，不兼容本地附件卷。

消息同步说明：

- 首次没有 `sync_cursor.message_seq` 游标时，Worker 会按 SDK 的 `seq` 正向连续拉取当前可用历史窗口，并在本地优先从最近消息开始解析。
- 后续已有游标时，Worker 按游标增量拉取。
- 企业微信“产生会话回调”不会直接携带消息正文；本服务收到 `/callbacks/wecom/archive-event` 后会异步触发一次 SDK 拉取，用于降低新消息进入系统的延迟。
- 消息同步在 MySQL/MariaDB 下使用数据库互斥锁，避免 Worker 轮询和回调触发同时拉取同一段 `seq`；Raw 消息按 `seq` 和 `msgid` 双重幂等跳过重复数据。
- SDK `GetChatData` 本身按 `seq` 游标拉取，不支持真正的远端倒序分页；“从最近开始”是在本地解析与展示层优先处理最新消息。
- 如果群消息先于客户群资料同步到达，服务会从消息 `roomid` 创建最小客户群会话和内部成员关系，保证前端先有群入口；后续客户群 API 同步可补全群名、群主和成员信息。

## CLI 使用

安装后端包后可使用：

```bash
wecomctl callback urls
wecomctl callback verify
wecomctl health
wecomctl import employees --file employees.csv
wecomctl sync once --type message
wecomctl sync once --type contacts
wecomctl sync once --type customer-chat
wecomctl sync once --type attachments
```

也可以用模块方式运行：

```bash
cd app/weCom/backend
python -m wecom_app.cli callback urls
```

员工名单 CSV 支持字段：

```csv
userid,name,alias,mobile,email,avatar,position,status,department_id,department_name,scope_status,scope_reason
li_teacher,李老师,,,,,,1,101,高中部,enabled,initial import
```

最小必填字段是 `userid`。如果提供 `department_id` 和 `department_name`，会创建或更新部门；如果提供 `scope_status`，会写入可观测名单，取值只能是 `enabled` 或 `disabled`。

也可以通过 HTTP 上传：
enable
```bash
curl -X POST http://101.132.83.149:8717/api/observable-employees/import \
  -H "Authorization: Bearer $INTERNAL_ADMIN_TOKEN" \
  -F "file=@test.csv"
```

CSV 导入入口不放在前端主界面。它是通讯录回调/API 暂不可用时的 CLI 或 HTTP 备用能力。

## GUI 使用手册

访问前端：

```text
http://localhost:5173
```

如果通过 Docker 或反向代理部署，请使用实际前端域名；后端 API 默认由前端开发服务代理到 `http://localhost:8717`，生产部署时按你的网关配置转发 `/api`、`/callbacks` 和 `/health`。

### 配置观测人员

1. 打开左侧菜单 `会话消息 -> 配置观测员工账号`。
2. 在左侧 `企业通讯录` 面板按员工姓名、userid 或部门搜索。
3. 点击未观测员工行进行选择；已在观测范围内的员工会显示 `已观测`，不能重复添加。
4. 点击中间 `添加`，把选中的员工加入观测范围。
5. 右侧 `已观测员工` 会显示当前可在消息主流程里查看的员工账号。
6. 如需移出，点击右侧员工行选中，再点击 `移出`。

说明：

- 观测范围只控制前端可查看入口，不会删除已经同步的通讯录、客户、客户群或消息数据。
- 如果企业微信通讯录回调被其他项目占用，可以继续使用 CLI 或 HTTP CSV 导入维护员工与观测范围。
- 没有通讯录数据时，配置页会显示空态，需要先完成通讯录同步或导入员工名单。

### 查看消息

1. 打开左侧菜单 `会话消息 -> 消息存档`。
2. 在 `观测员工范围` 中选择员工；也可以用姓名、userid、部门搜索。
3. 在中间会话列表中按 `全部`、`学员`、`学员群` 过滤会话。后端的 `customer_chat` 会在界面展示为 `学员群`。
4. 选择一个会话后，右侧聊天区展示当前会话的消息时间线。
5. 点击聊天区右上角搜索图标，打开 `搜索对话消息` 抽屉，可按文本、发送人、开始时间、结束时间检索。搜索范围只限当前已打开会话，不跨员工或其他会话。
6. 点击聊天区右上角详情图标，打开会话详情抽屉，查看学员/群信息和当前查看上下文。
7. 图片消息初始展示下载按钮；点击后后端下载企业微信媒体并上传 OSS，期间展示下载中，成功后展示图片并可打开预览弹窗。
8. 图片下载失败时可点击重试；如果企业微信媒体已过期，界面会提示文件已过期/无法下载。
9. 文件、语音、视频等尚未完整解析的类型会以“不支持消息”占位显示，Raw 数据仍保留在后端。

说明：

- 如果当前管理员 token 没权限、后端不可用、观测范围为空或同步数据为空，页面展示空态，不展示假会话。
- 无权限或无数据不是前端错误；请先检查 `INTERNAL_ADMIN_TOKEN` / `VITE_INTERNAL_ADMIN_TOKEN`、后端健康状态、数据库迁移和同步任务。
- 移动端顶部有 `员工`、`会话`、`聊天` 三段切换，按主流程逐级查看。

## 回调路径

```text
通讯录回调: /callbacks/wecom/contact
客户联系回调: /callbacks/wecom/customer
客户群回调: /callbacks/wecom/customer-chat
会话存档同意回调: /callbacks/wecom/archive-consent
产生会话回调: /callbacks/wecom/archive-event
```

## 验证

```bash
cd app/weCom/backend
pytest -q
ruff check .

cd ../frontend
npm run lint
npm test
npm run build
```
