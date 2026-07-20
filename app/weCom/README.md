# 企业微信会话存档可视化后台与同步服务

本项目是企业微信会话内容存档的 v1 实现，代码集中在 `app/weCom/`。服务按 `spec/Tech_weCom_sync_service.md` 落地，包含 FastAPI 后端、DB 游标 Worker、React 可视化工作台、MySQL schema、Docker Compose 和 `wecomctl` CLI。

## 基本能力

- 接收通讯录、客户联系、客户群、会话存档同意和产生会话回调。
- 通过 Worker 框架按 `sync_cursor.message_seq` 进行会话拉取、转换和补偿。
- 保存 Raw 数据、处理状态和标准化业务数据到 MySQL。
- 支持通过 CSV 导入员工、部门和可观测员工名单，用于通讯录回调被占用或通讯录 API 尚未接入时先跑后台。
- 前端支持观测员工、会话列表、聊天时间线、当前会话搜索、详情面板、撤回状态、不支持消息占位和图片附件状态。
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

默认前端使用 `VITE_INTERNAL_ADMIN_TOKEN`，未配置时为 `dev-admin-token`。API 不可用时，前端会回退到内置 mock 数据，方便在 secret 未提供时先验收界面。

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

文件型密钥和 SDK 通过只读挂载：

```text
./secrets/wecom_archive_private_key.pem -> /run/secrets/wecom_archive_private_key.pem
./vendor/wecom_sdk -> /opt/wecom_sdk
```

兼容说明：旧变量 `WECOM_CUSTOMER_SECRET` 仍可作为 `WECOM_CUSTOMER_API_SECRET` 的兜底读取，但新部署建议统一使用 `WECOM_CUSTOMER_API_SECRET`，避免误解为企业微信后台存在独立的“客户联系 secret”入口。

当前企业微信 secret 未提供时，回调解密和 SDK 拉取使用本地 stub。接入真实企业微信时，需要在 `wecom_app/wecom/client.py` 内补齐 Linux SDK 调用，并在 `callback_crypto.py` 中替换为企业微信官方回调解密逻辑。

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

```bash
curl -X POST http://localhost:8717/api/observable-employees/import \
  -H "Authorization: Bearer $INTERNAL_ADMIN_TOKEN" \
  -F "file=@employees.csv"
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
