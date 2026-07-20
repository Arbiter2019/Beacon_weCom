# Retrospective — WeCom 同步服务 2026-07-17

## 背景

本次 retrospective 覆盖 2026-07-17 一天内完成的 WeCom 聊天同步服务上线调试全过程。
设计规格位于 `spec/`，前端原型位于 `demo/Web-Prototype/`，代码位于 `app/weCom/`。

---

## 一、问题清单与根因分析

### 1. 回调验证始终不通过

**现象：** 企业微信后台配置回调 URL 时，提示验证不通过。  
**代码问题：**
- `callback_crypto.py` 中 `decrypt_echo()` 是未实现的空 stub，有 AES key 时仍直接原样返回加密字符串
- `callbacks.py` 中 `verify_callback` 返回类型为 `-> str`，FastAPI 默认将 `str` 做 JSON 编码（加引号），而企业微信官方文档明确要求 **"不能加引号，不能带 BOM 头，不能带换行符"**

**根因：**  
Spec `Tech_weCom_sync_service.md` 第 7.2 节只列出了回调路径表，描述了"解密 echostr 并返回明文"，但**没有提供解密算法的具体实现细节**（AES-256-CBC、IV 为 key 前 16 字节、PKCS7 去填充、提取 msg 字段），也没有提到 FastAPI 返回类型陷阱。实现者写了占位 stub 未跟进实现，测试又没有覆盖真实加密场景（`test_callback_verify_echo` 仅测试了 token 为空的旁路路径），导致问题直到真实接入时才暴露。

---

### 2. 前端 Token 编译时未注入 → 静默回退 mock 数据

**现象：** 前端界面空白，看不到任何真实数据，但控制台无报错。  
**代码问题：**
- `vite.config.ts` 中 `proxy` 仅在 `vite dev` 开发服务器下生效，Nginx 容器不知道要把 `/api/*` 转发给后端
- `client.ts` 中 `VITE_INTERNAL_ADMIN_TOKEN` 是 Vite 编译时变量，Docker build 时未通过 build arg 传入，实际值为 fallback `"dev-admin-token"`，与 `.env` 中的长 token 不匹配，导致 API 返回 401，客户端 `catch` 静默返回 mock 数据

**根因：**
- **Nginx 反代缺失**：Spec 和 Implementation Plan 都只描述了服务架构，没有明确要求在 `Dockerfile.frontend` 的 Nginx 配置中加入 `/api/*` 反代规则，开发者只把 Vite dev proxy 当成最终方案
- **Vite 编译时变量认知陷阱**：Spec 和 plan 里对前端部署细节没有说明 "VITE 变量需要在 build 阶段注入"。这是 Vite 项目常见陷阱，但未在文档中预警
- **client.ts 的静默降级设计**：`getJson()` 函数在所有错误（401/404/网络异常）下都返回 mock 数据而不是显示错误提示，导致问题完全不可见。这是设计上的问题

---

### 3. SDK 与 SQLAlchemy OpenSSL 符号冲突 → Worker 进程崩溃

**现象：** Worker 启动后立即崩溃，输出 `free(): invalid pointer`，无 Python traceback。  
**根因：**
- `libWeWorkFinanceSdk_C.so` 内部依赖 OpenSSL；SQLAlchemy 的 C 扩展也会加载一份 OpenSSL。两套 OpenSSL 在同一进程内产生符号冲突，触发 glibc 的堆错误检测
- Spec 第 5 节已明确指出 "企业微信 Linux SDK 动态库只要求挂载到 Worker"，但**没有预警 ctypes 直接加载时的进程级符号冲突问题**，也没有给出推荐的隔离方案（subprocess、独立进程池等）

**修复方案：** 将 SDK 调用迁移到独立的 `sdk_worker.py` 子进程，通过 stdin/stdout JSON 通信实现隔离。

---

### 4. Apple Silicon (aarch64) 与 x86-64 SDK 不兼容

**现象：** Docker 容器内 SDK `.so` 文件无法加载（`not a dynamic executable`）。  
**根因：**
- SDK 文件名为 `sdk_x86_v3_20250205`，是 x86-64 架构二进制
- 开发机为 Apple Silicon（aarch64），Docker 容器默认架构为 arm64
- Spec 中提到 "SDK 依赖 Linux"，但**没有明确说明 Apple Silicon 开发环境需要在 docker-compose.yml 中指定 `platform: linux/amd64`**

**修复方案：** 在 `docker-compose.yml` 中为 `wecom-worker` 添加 `platform: linux/amd64`，利用 Docker Desktop 的 Rosetta 2 模拟层运行。

---

### 5. `pyproject.toml` 包发现问题 → Docker build 失败

**现象：** `docker compose build` 时 pip install 报错：`Multiple top-level packages discovered in a flat-layout: ['alembic', 'wecom_app']`  
**根因：**
- `backend/` 目录同时包含 `alembic/`（迁移目录）和 `wecom_app/`（应用包），setuptools 的自动包发现将两者都识别为顶层包
- Spec 第 4 节描述了 Alembic 的使用，但**没有明确指出 pyproject.toml 需要通过 `[tool.setuptools.packages.find]` 限定只包含 `wecom_app*`**

---

### 6. 消息解密后从未写入数据库 → 数据管道断裂

**现象：** Worker 日志显示 `fetched=100` 但数据库 `raw_message` 表始终为 0。  
**这是本次最严重的 bug。**

**代码问题：** `sync_jobs.py` 的 `sync_messages_once()` 函数：
```python
fetched_messages, max_seq = client.get_chat_data(seq)
# ...（cursor 更新）
processed = transform_pending_messages(db)  # 从 raw_message 读但没有人写入
db.commit()
return SyncResult(fetched=len(fetched_messages), ...)
# fetched_messages 在这里被直接丢弃！
```
`fetched_messages` 列表解密完成后没有被持久化，直接超出作用域丢弃。

**根因：**
- Spec 第 9.1 节描述了 `raw_message` 表的字段，也描述了 Extract → Transform → Load 的三层架构。但**没有在 Worker 流程伪代码中明确写出 "解密后写入 raw_message" 这一步**
- Implementation Plan 的 Task 描述了 Transform 层，但对 Extract 层（`sync_jobs.py` 调用 SDK → 写 raw_message）的职责边界描述模糊
- 测试 `test_callbacks.py` 只测试了回调路径，没有 Worker 数据管道的集成测试

---

### 7. `SessionLocal` 的 `autoflush=False` 导致同批次 transform 看不到新记录

**现象：** 修复写入逻辑后，`fetched=100` 但 `processed=0`，数据延迟一个周期才被 transform。  
**根因：** `session.py` 创建 SessionLocal 时设置了 `autoflush=False`，`_save_raw_messages` 用 `db.add()` 添加记录后，没有显式调用 `db.flush()`，导致在同一事务内 `transform_pending_messages` 的 `SELECT` 查不到这些新记录。需要在 `_save_raw_messages` 后加 `db.flush()`。

---

### 8. AES key 长度校验过严 → ver=2 消息全部被过滤

**现象：** 解密 ver=2 消息时，RSA 解密成功但日志显示 "Decrypted key length 88 != 32"，消息被跳过。  
**根因：** 实现中假设 AES-256 key 必须是 32 原始字节，但企业微信 ver=2 的 `encrypt_random_key` 解密后得到的是一个 88 字节的中间格式（进一步 base64 编码或其他封装），需要直接传给 SDK 的 `DecryptData()`，不应强行校验为 32 字节。**Spec 中没有描述 `publickey_ver` 对应的解密中间格式差异**。

---

### 9. 外部联系人表为空 → Conversations API 始终返回空列表

**现象：** 数据库有 500 条消息，但前端会话列表为空。  
**根因：** `conversations.py` 的会话列表 API 通过 JOIN `employee_external_contact` 和 `external_contact` 表构建会话。这两张表需要通过外部联系人同步 API 填充，但**初始化流程没有包含这一步，也没有文档说明这是数据显示的前提条件**。消息表里其实已有对应的外部联系人 ID（来自 `message_recipient`），但 conversations API 不从消息直接推导会话。

---

## 二、问题分类统计

| 分类 | 问题数 | 占比 |
|------|--------|------|
| Spec 缺少实现细节 | 5 | 56% |
| 平台/环境约束未预警 | 3 | 33% |
| 数据管道逻辑错误 | 2 | 22% |
| 测试覆盖不足 | 4 | 44% |
| 前端部署知识盲区 | 2 | 22% |

（部分问题多分类，合计超过 100%）

---

## 三、深度分析：为什么会出现这些问题

### 3.1 Spec 是架构级而非实现级

当前 `Tech_weCom_sync_service.md` 描述了系统架构、表结构、回调路径、CLI 命令，但对关键算法细节（AES 解密、echostr 格式、AES key 格式差异）只有一句话概述。**开发者在缺乏文档指引时倾向于先写 stub，但没有设置 TODO 标记或测试来防止 stub 流入生产**。

### 3.2 "第三方 SDK + 平台 = 地雷区"未被识别

企业微信 Linux SDK 是一个高风险依赖，涉及：
- 平台架构（x86-64 only）
- C 库符号全局污染
- 加密算法的私有格式

这些在 spec 里被简单归为 "SDK 相关逻辑只在 Docker Linux 容器中执行"，**没有被识别为需要专项 spike 的技术风险**，导致整个调试过程花费了大量时间。

### 3.3 数据管道没有端到端的 "smoke test"

ETL 管道（SDK拉取 → 写 raw_message → transform → 写 message）是系统核心，但测试只覆盖了各层的单元逻辑，**没有一个 "输入序列号，验证 message 表有记录" 的端到端 smoke test**。如果有，写入缺失的问题在开发阶段就会被发现。

### 3.4 前端部署架构在 spec 中是隐性的

Spec 只描述了 API 契约，没有描述 "前端 Docker 容器如何访问后端 API"。开发者沿用了 Vite dev proxy 的思维模式，没有意识到 Nginx 生产容器需要独立的反代配置。**这是一个在 spec 里显而易见、但在 implementation plan 里被忽视的部署细节**。

### 3.5 初始化依赖关系没有被文档化

"看到会话" 的前提链是：
1. 员工在 observable_employee_scope 中
2. 外部联系人在 employee_external_contact 中  
3. 消息在 message 中  
4. 前端 token 正确

这 4 个前提缺任何一个，前端就完全空白，且没有错误提示（client.ts 静默降级）。**没有"环境就绪清单"（readiness checklist）文档，导致 debug 过程是逐层剥洋葱式的，效率很低**。

---

## 四、改善建议

### 4.1 Spec 改善

#### A. 为关键加密接口提供伪代码或参考实现
对于回调验证、echostr 解密、AES key 解密等涉及私有协议的关键函数，在 spec 中添加伪代码：

```
# 回调 URL 验证 (GET) 处理流程
1. AES_KEY = base64decode(EncodingAESKey + "=")  # 43字符 + "=" padding
2. ciphertext = base64decode(echostr)
3. plaintext = AES_CBC_decrypt(key=AES_KEY, iv=AES_KEY[:16], data=ciphertext)
4. plaintext = PKCS7_unpad(plaintext)
5. msg = plaintext[20 : 20 + big_endian_uint32(plaintext[16:20])]
6. HTTP Response: 200, Content-Type: text/plain, Body: msg  # 不能有引号！
```

#### B. 在"技术风险"章节明确标注高风险依赖
新增 `## 技术风险与 Spike 建议` 章节，至少覆盖：
- 第三方 C SDK 的平台约束（架构、符号冲突、隔离方案）
- 需要在特定环境验证才能确认的关键假设（如 AES key 格式）

#### C. 添加数据初始化依赖说明
在 spec 中明确说明各 API 的数据前提：

> **会话列表 API 前提：** `employee_external_contact` 非空（需运行 `sync external-contacts`）。`employee_external_contact` 为空时 API 返回空列表，不报错。

#### D. 前端部署补充 Nginx 反代要求
在前端相关章节明确：

> 生产 Nginx 容器需要配置 `/api/*`、`/callbacks/*`、`/health` 的反代规则，指向 `wecom-api:PORT`。Vite dev proxy 只在本地开发有效。

---

### 4.2 Demo 改善

#### A. 错误状态应明确展示，不应静默降级
Demo 中 `client.ts` 的 `getJson()` 在 401/404/网络错误时返回 mock 数据，这在展示阶段是合理的，但需要在 demo 旁注明 "生产环境 API 错误应显示错误状态，不应返回 mock"，并在 demo 代码中用 `// TODO: 生产环境需要处理错误状态` 注释标记。

#### B. 添加"环境就绪"界面状态
Demo 只展示了有数据的理想状态。建议增加以下空状态设计：
- `employee_external_contact` 为空时："暂无客户数据，请先同步外部联系人"
- API token 无效时：不静默降级为 mock，而是显示"请检查配置"
- Worker 未运行时：health endpoint 提示

---

### 4.3 Workflow 改善

#### A. 引入"技术风险 Spike" 阶段
对于涉及第三方 SDK / 特殊加密协议 / 平台约束的任务，在 Implementation Plan 中增加 spike 任务，要求**在编写完整实现前先验证关键假设**：

```
### Task X.0: Spike — SDK 平台兼容性验证
- [ ] 在目标 Docker 容器内验证 SDK .so 可加载
- [ ] 验证 ctypes 调用 Init/GetChatData 无崩溃
- [ ] 验证 AES key 长度和格式
- [ ] 记录验证结果到 spike_notes.md
```

#### B. 禁止 stub 流入主流程
当前代码中 `decrypt_echo()` 是 stub，但测试没有检测到这一点。建议：
- 所有 stub/placeholder 函数必须 `raise NotImplementedError("stub: 需实现 XXX")`，而不是返回原样数据
- CI 可以用 `grep -r "raise NotImplementedError"` 检测遗留 stub

#### C. 端到端 Smoke Test
在 Implementation Plan 中明确要求一个 "数据管道 smoke test"：
```python
def test_message_pipeline_end_to_end(client, db):
    """
    验证从 Worker 写入到前端 API 可见的完整路径：
    raw_message → transform → message → API
    """
    # 1. 直接插入一条 raw_message (pending)
    # 2. 调用 transform_pending_messages
    # 3. 验证 message 表有对应记录
    # 4. 调用 /api/observed-employees/{userid}/conversations 验证有返回
```

#### D. 提供"就绪检查脚本"
在 README 或 CLI 中提供 `wecomctl readiness-check`，输出：

```
✅ MySQL 连通
✅ observable_employee_scope: 6 条记录
⚠️  external_contact: 0 条 (需运行 sync external-contacts)
✅ sync_cursor: message_seq = 42709000
✅ message: 500 条
❌ VITE token 与 API token 是否匹配：无法检测（编译时变量）
```

#### E. Apple Silicon 开发环境声明
在 README 中添加 "macOS Apple Silicon 注意事项"：

> 企业微信会话存档 SDK 为 x86-64 二进制。在 Apple Silicon Mac 上运行 Worker 容器需要：
> 1. 在 `docker-compose.yml` 的 `wecom-worker` 中添加 `platform: linux/amd64`
> 2. Docker Desktop 开启 Rosetta 2 模拟（Settings → Features in development → Use Rosetta for x86/amd64 emulation）
> 3. Worker 容器内 HTTP 调用（如外部联系人同步）会因模拟层较慢，建议在宿主机直接运行

#### F. 敏感配置 env config 文件与代码隔离
`spec/env config.md` 中包含真实的密钥、token、数据库密码。建议：
- 配置文件应使用 `.env.example` 格式，不存放真实值
- 真实配置在运行时注入，不进入 spec 文件
- 在 `.gitignore` 或 spec 说明中标注 `env config.md` 不得提交

---

## 五、总结

| 改善点 | 目标文件 | 优先级 |
|--------|----------|--------|
| 加密算法伪代码 | `spec/Tech_weCom_sync_service.md` | P0 |
| 数据管道 smoke test | `app/weCom/backend/tests/` | P0 |
| 禁止 stub 流入主流程（NotImplementedError） | 编码规范 | P0 |
| Nginx 反代要求 | spec + Dockerfile | P1 |
| Apple Silicon 开发说明 | README | P1 |
| 技术风险 Spike 任务模板 | Implementation Plan | P1 |
| API 错误状态（不静默降级） | frontend/client.ts | P1 |
| 就绪检查脚本 | CLI `wecomctl` | P2 |
| 数据初始化依赖说明 | spec | P2 |
| env config 敏感信息隔离 | spec + .gitignore | P1 |

> 本次开发花费了约一个工作日完成本应在数小时内完成的接入工作，其中约 60% 时间消耗在以上问题的排查与修复上。通过以上改善措施，类似接入工作的风险可以显著降低。
