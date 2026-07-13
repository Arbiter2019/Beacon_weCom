# 企业微信会话存档可视化后台与同步服务

本项目是企业微信会话内容存档的 v1 实现，代码集中在 `app/weCom/`。服务按 `spec/Tech_weCom_sync_service.md` 落地，包含 FastAPI 后端、DB 游标 Worker、React 可视化工作台、MySQL schema、Docker Compose 和 `wecomctl` CLI。

## 基本能力

- 接收通讯录、客户联系、客户群、会话存档同意和产生会话回调。
- 通过 Worker 框架按 `sync_cursor.message_seq` 进行会话拉取、转换和补偿。
- 保存 Raw 数据、处理状态和标准化业务数据到 MySQL。
- 前端支持观测员工、会话列表、聊天时间线、当前会话搜索、详情面板、撤回状态、不支持消息占位和图片附件状态。
- 附件以本地 Docker volume 为 v1 存储后端，通过后端鉴权 API 代理读取。
- CLI 输出回调地址、校验配置、检查健康状态和触发一次同步。

## 边界

Do:

- 单个企业微信主体。
- 内部固定管理员 token 鉴权。
- 支持文本、图片、链接、agree/disagree、撤回和不支持类型占位。
- 无 secret 时可用 stub 跑通 API、Worker、CLI 和前端演示。

Don't do:

- 不做多企业微信主体隔离。
- 不接入飞书/SSO 或完整多用户权限。
- 不在 v1 生产化对象存储，字段已预留 OSS/S3/MinIO 扩展。
- 不完整解析语音、视频、文件、小程序、会话记录等复杂类型。
- 不把 secret、私钥或 Linux SDK 提交进仓库。

## 本地开发

后端：

```bash
cd app/weCom/backend
python -m pip install -e ".[dev]"
pytest -q
uvicorn wecom_app.main:app --reload --port 8000
```

前端：

```bash
cd app/weCom/frontend
npm install
npm run dev
```

默认前端使用 `VITE_INTERNAL_ADMIN_TOKEN`，未配置时为 `dev-admin-token`。API 不可用时，前端会回退到内置 mock 数据，方便在 secret 未提供时先验收界面。

## Docker 部署

```bash
cd app/weCom
cp .env.example .env
docker compose up --build
```

服务端口：

- API: `http://localhost:8000`
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
- `WECOM_CONTACT_SECRET`
- `WECOM_CONTACT_CALLBACK_TOKEN`
- `WECOM_CONTACT_ENCODING_AES_KEY`
- `WECOM_CUSTOMER_SECRET`
- `WECOM_CUSTOMER_CALLBACK_TOKEN`
- `WECOM_CUSTOMER_ENCODING_AES_KEY`
- `WECOM_ARCHIVE_SECRET`
- `WECOM_ARCHIVE_CALLBACK_TOKEN`
- `WECOM_ARCHIVE_ENCODING_AES_KEY`
- `INTERNAL_ADMIN_TOKEN`
- `VITE_INTERNAL_ADMIN_TOKEN`

文件型密钥和 SDK 通过只读挂载：

```text
./secrets/wecom_archive_private_key.pem -> /run/secrets/wecom_archive_private_key.pem
./vendor/wecom_sdk -> /opt/wecom_sdk
```

当前企业微信 secret 未提供时，回调解密和 SDK 拉取使用本地 stub。接入真实企业微信时，需要在 `wecom_app/wecom/client.py` 内补齐 Linux SDK 调用，并在 `callback_crypto.py` 中替换为企业微信官方回调解密逻辑。

## CLI 使用

安装后端包后可使用：

```bash
wecomctl callback urls
wecomctl callback verify
wecomctl health
wecomctl sync once --type message
wecomctl sync once --type contacts
wecomctl sync once --type customer-chat
```

也可以用模块方式运行：

```bash
cd app/weCom/backend
python -m wecom_app.cli callback urls
```

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
