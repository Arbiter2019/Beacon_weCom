# 企业微信会话存档可视化后台与同步服务

本项目是企业微信会话内容存档的 v1 实现，代码集中在 `app/weCom/`。服务按 `spec/Tech_weCom_sync_service.md` 落地，包含 FastAPI 后端、DB 游标 Worker、React 可视化工作台、MySQL schema、Docker Compose 和 `wecomctl` CLI。

## 基本能力

- 接收通讯录、客户联系、客户群、会话存档同意和产生会话回调。
- 通过 Worker 框架按 `sync_cursor.message_seq` 进行会话拉取、转换和补偿。
- 保存 Raw 数据、处理状态和标准化业务数据到 MySQL。
- 支持通过 CSV 或 API 导入员工、部门和可观测员工名单，用于通讯录回调被占用或通讯录 API 尚未接入时先跑后台。
- 前端支持按企业通讯录配置观测员工、查看观测员工会话列表、聊天时间线、当前会话搜索、详情抽屉、撤回状态、不支持消息占位和图片附件状态。
- 附件以本地 Docker volume 为 v1 存储后端，通过后端鉴权 API 代理读取。
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
- 不在 v1 生产化对象存储，字段已预留 OSS/S3/MinIO 扩展。
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
docker compose up --build
```

服务端口：

- API: `http://localhost:8717`
- Frontend: `http://localhost:5173`
- MySQL: `localhost:3306`

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

文件型密钥和 SDK 通过只读挂载：

```text
./secrets/wecom_archive_private_key.pem -> /run/secrets/wecom_archive_private_key.pem
./vendor/wecom_sdk -> /opt/wecom_sdk
```

兼容说明：旧变量 `WECOM_CUSTOMER_SECRET` 仍可作为 `WECOM_CUSTOMER_API_SECRET` 的兜底读取，但新部署建议统一使用 `WECOM_CUSTOMER_API_SECRET`，避免误解为企业微信后台存在独立的“客户联系 secret”入口。

回调模块已支持企业微信加密 XML 的 `msg_signature` 校验、`Encrypt` 字段解密、CorpID 校验和基础事件字段解析。会话内容拉取依赖企业微信会话存档 Linux SDK；`./vendor/wecom_sdk` 未挂载或会话存档 Secret/私钥缺失时，Worker/API 无法拉取真实消息。

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
7. 图片消息会打开预览弹窗；文件、语音、视频等尚未完整解析的类型会以“不支持消息”占位显示，Raw 数据仍保留在后端。

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
