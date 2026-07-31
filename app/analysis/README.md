# WeCom Analysis

## 背景

这个目录承载企业微信会话存档的离线分析能力，读取 `app/weCom/backend` 里的归档库数据，向独立的分析库写结果。

当前目标：

- 每日快照分析
- 基础统计
- 响应时间统计
- 群舆情分析
- 群热词分析
- 群问题分类

## 实施方案

### 数据流

1. 从归档库读取观测员工、私聊关系、群成员和标准化消息。
2. 按北京时间 `T+1` 构建当天会话快照。
3. 基础统计、响应统计、热词、舆情、问题分类按任务独立落库。
4. 每个任务支持按日期、员工、任务类型回滚重跑。

### 代码结构

- `analysis_app/models.py`: 分析库 ORM
- `analysis_app/services/`: 快照、统计、LLM、回滚、任务编排
- `analysis_app/prompts.py`: 舆情 / 问题分类 Prompt
- `analysis_app/question_categories.py`: 问题分类枚举配置
- `analysis_app/stopwords.py`: 热词停用词配置
- `analysis_app/cli.py`: CLI 入口

## 预留后续设计

后续可以继续补：

- 分析结果查询 API
- 前端结果页
- `raw_event` 历史关系回放
- 更细粒度的任务监控和失败重跑
- 更强的 LLM 错误恢复与批处理限流

## CLI 使用

在 `app/analysis` 下执行：

```bash
PYTHONPATH=.:../weCom/backend python -m analysis_app.cli run --start-date 2026-07-21 --end-date 2026-07-21
PYTHONPATH=.:../weCom/backend python -m analysis_app.cli run --start-date 2026-07-21 --end-date 2026-07-21 --userid wang_teacher --task basic --task response
PYTHONPATH=.:../weCom/backend python -m analysis_app.cli rollback --start-date 2026-07-21 --end-date 2026-07-21 --task sentiment
```

`analysisctl` 也可在安装后直接使用。

## 环境变量

分析模块启动时会自动读取 `app/analysis/.env`。进程里已经 `export` 的环境变量优先级更高，可以临时覆盖 `.env` 中的值。

`PYTHONPATH` 不放在 `.env` 里维护。它用于让 Python 在导入阶段找到 `analysis_app` 和现有后端的 `wecom_app.models`，需要继续放在 shell、cron 脚本或 systemd unit 中：

```bash
export PYTHONPATH="/home/share-user/app/analysis:/home/share-user/app/weCom/backend"
```

首次配置可从示例文件复制：

```bash
cd /home/share-user/app/analysis
cp .env.example .env
```

然后编辑 `app/analysis/.env`。不要提交真实 `.env`，仓库只提交 `.env.example`。

### 必填

```dotenv
ARCHIVE_DATABASE_URL=mysql+pymysql://wecom:<MYSQL_PASSWORD>@127.0.0.1:3306/wecom_archive
ANALYSIS_DATABASE_URL=mysql+pymysql://wecom:<MYSQL_PASSWORD>@127.0.0.1:3306/wecom_analysis
```

说明：

- `ARCHIVE_DATABASE_URL` 读取现有归档库。
- `ANALYSIS_DATABASE_URL` 写入独立分析库。
- `<MYSQL_PASSWORD>` 沿用 `app/weCom/.env` 中的 `MYSQL_PASSWORD`。
- 在宿主机执行时 MySQL host 使用 `127.0.0.1`；如果在 Docker 网络内执行，host 使用 `mysql`。
- 如果密码包含 `@`、`/`、`:`、`#`、`?` 等 URL 特殊字符，需要先做 URL encode 后再写入连接串。

### LLM 任务配置

如果执行默认全量任务，会包含舆情和问题分类，因此需要配置 `LLM_API_KEY`。如果暂时不配置 LLM，只运行 `snapshot/basic/response/hotwords` 即可。

```dotenv
LLM_PROVIDER=qwen
LLM_API_KEY=<你的阿里云DashScope API Key>
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_MODEL=kimi-k2.6
LLM_MAX_TOKENS=2048
LLM_TEMPERATURE=0.1
LLM_TIMEOUT_SECONDS=60
LLM_MAX_RETRIES=3
```

DashScope 返回 `403 Forbidden` 通常表示 `LLM_API_KEY` 未配置、Key 无效、账号无模型权限，或模型名当前账号不可用。此时可以先跑非 LLM 任务：

```bash
python -m analysis_app.cli run \
  --start-date 2026-07-28 \
  --end-date 2026-07-28 \
  --task snapshot \
  --task basic \
  --task response \
  --task hotwords
```

全量任务中单个 LLM 任务失败时，CLI 会在 JSON 结果里把对应任务标记为 `failed`，不会阻止已成功任务落库。

### LLM 连通性测试

不要把真实 API Key 发到聊天窗口，也不要写进代码或 README。服务器上把 `LLM_API_KEY` 写入 `app/analysis/.env` 后执行：

```bash
python -m analysis_app.cli llm-smoke
```

成功时会输出类似：

```json
{
  "ok": true,
  "provider": "qwen",
  "model": "kimi-k2.6",
  "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
  "response": {
    "ok": true,
    "message": "pong"
  }
}
```

失败时会输出 `ok: false`、当前 provider/model/base_url 和错误信息，并以非 0 状态退出。常见原因是 `LLM_API_KEY` 未导出、Key 无效、模型名不可用、账号没有模型权限，或服务器网络无法访问 `LLM_BASE_URL`。

### 分析运行配置

```dotenv
ANALYSIS_TIMEZONE=Asia/Shanghai
ANALYSIS_MAX_WORKERS=4
HOTWORD_STOPWORDS_PATH=/home/share-user/app/analysis/config/hotword_stopwords.txt
```

### 可复制示例

```dotenv
ARCHIVE_DATABASE_URL=mysql+pymysql://wecom:<MYSQL_PASSWORD>@127.0.0.1:3306/wecom_archive
ANALYSIS_DATABASE_URL=mysql+pymysql://wecom:<MYSQL_PASSWORD>@127.0.0.1:3306/wecom_analysis
LLM_PROVIDER=qwen
LLM_API_KEY=<你的阿里云DashScope API Key>
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_MODEL=kimi-k2.6
LLM_MAX_TOKENS=2048
LLM_TEMPERATURE=0.1
LLM_TIMEOUT_SECONDS=60
LLM_MAX_RETRIES=3
ANALYSIS_TIMEZONE=Asia/Shanghai
ANALYSIS_MAX_WORKERS=4
HOTWORD_STOPWORDS_PATH=/home/share-user/app/analysis/config/hotword_stopwords.txt
```

## 部署命令

### 首次部署

分析模块默认沿用 `app/weCom/docker-compose.yml` 中已经部署的 MySQL 容器，不需要新增 MySQL 容器。

首次部署前需要先创建独立分析库 `wecom_analysis`。分析代码会自动创建表，但不会自动创建 database。

1. 确认现有 MySQL 容器已启动：

```bash
cd /Users/xuwei/Desktop/morpheus/Projects/Beacon/WeCom/app/weCom
docker compose ps mysql
```

2. 从 `app/weCom/.env` 读取 MySQL 配置：

```bash
cd /Users/xuwei/Desktop/morpheus/Projects/Beacon/WeCom/app/weCom
grep -E '^(MYSQL_USER|MYSQL_PASSWORD|MYSQL_DATABASE)=' .env
```

3. 使用 MySQL root 用户创建分析库，并授权给现有 `MYSQL_USER`。

`MYSQL_USER=wecom` 默认只会被授权访问初始化时指定的 `MYSQL_DATABASE=wecom_archive`，没有权限创建或访问新的 `wecom_analysis`。因此首次建库必须使用 `MYSQL_ROOT_PASSWORD`。

先确认 root 密码：

```bash
cd /Users/xuwei/Desktop/morpheus/Projects/Beacon/WeCom/app/weCom
grep -E '^(MYSQL_ROOT_PASSWORD)=' .env
```

再创建库并授权：

```bash
cd /Users/xuwei/Desktop/morpheus/Projects/Beacon/WeCom/app/weCom
docker compose exec mysql sh -lc 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" -e "CREATE DATABASE IF NOT EXISTS wecom_analysis CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci; GRANT ALL PRIVILEGES ON wecom_analysis.* TO '\''$MYSQL_USER'\''@'\''%'\''; FLUSH PRIVILEGES;"'
```

4. 配置分析模块 `.env`。密码沿用 `app/weCom/.env` 中的 `MYSQL_PASSWORD`：

```bash
cd /home/share-user/app/analysis
cp .env.example .env
vim .env
```

至少需要填入 `ARCHIVE_DATABASE_URL`、`ANALYSIS_DATABASE_URL`。如果要跑 LLM 任务，还需要填入 `LLM_API_KEY`。

如果在 Docker 网络内执行，host 使用 `mysql`；如果在宿主机执行，host 使用 `127.0.0.1`。

5. 安装并 smoke test：

```bash
cd /home/share-user/app/analysis
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
export PYTHONPATH="/home/share-user/app/analysis:/home/share-user/app/weCom/backend"
python -m analysis_app.cli llm-smoke
python -m analysis_app.cli run --start-date 2026-07-21 --end-date 2026-07-21
```

如果 `python3 -m venv .venv` 提示缺少 `ensurepip` 或 `venv`，先安装系统 venv 包：

```bash
apt update
apt install -y python3-venv
```

### 日常部署 / 手动执行

日常只需要维护 `app/analysis/.env`，并在启动 shell、cron 或 systemd unit 里保留 `PYTHONPATH`：

```bash
export PYTHONPATH="/home/share-user/app/analysis:/home/share-user/app/weCom/backend"
cd /home/share-user/app/analysis
. .venv/bin/activate
python -m analysis_app.cli run --start-date 2026-07-21 --end-date 2026-07-21
```

热词停用词文件建议在 `.env` 里显式配置为项目内文件：

```dotenv
HOTWORD_STOPWORDS_PATH=/home/share-user/app/analysis/config/hotword_stopwords.txt
```

### Cron 定时任务

推荐每天北京时间凌晨 1 点跑昨天的分析任务，并把 stdout/stderr 追加到按日期拆分的日志文件：

```bash
crontab -e
```

写入：

```cron
SHELL=/bin/bash
CRON_TZ=Asia/Shanghai

0 1 * * * cd /home/share-user/app/analysis && mkdir -p logs && export PYTHONPATH="/home/share-user/app/analysis:/home/share-user/app/weCom/backend" && . /home/share-user/app/analysis/.venv/bin/activate && YDAY=$(/bin/date -d yesterday +\%F) && { echo "===== analysis start $(date '+\%F \%T') target=${YDAY} ====="; python -m analysis_app.cli run --start-date "${YDAY}" --end-date "${YDAY}"; status=$?; echo "===== analysis end $(date '+\%F \%T') target=${YDAY} exit=${status} ====="; exit ${status}; } >> "logs/analysis-${YDAY}.log" 2>&1
```

说明：

- `app/analysis/.env` 会由程序自动读取，cron 里不需要重复写数据库密码或 LLM Key。
- `PYTHONPATH` 仍需要在 cron 命令里显式设置。
- crontab 中 `date +%F` 的 `%` 必须写成 `\%`，否则 cron 会把它当成换行。
- 日志路径示例：`/home/share-user/app/analysis/logs/analysis-2026-07-29.log`。
- 上面的命令默认跑全量任务，包括 `sentiment` 和 `question` 两个 LLM 任务。

如果 LLM 暂时没有调通，可以先配置非 LLM 定时任务：

```cron
SHELL=/bin/bash
CRON_TZ=Asia/Shanghai

0 1 * * * cd /home/share-user/app/analysis && mkdir -p logs && export PYTHONPATH="/home/share-user/app/analysis:/home/share-user/app/weCom/backend" && . /home/share-user/app/analysis/.venv/bin/activate && YDAY=$(/bin/date -d yesterday +\%F) && { echo "===== analysis start $(date '+\%F \%T') target=${YDAY} tasks=non-llm ====="; python -m analysis_app.cli run --start-date "${YDAY}" --end-date "${YDAY}" --task snapshot --task basic --task response --task hotwords; status=$?; echo "===== analysis end $(date '+\%F \%T') target=${YDAY} exit=${status} ====="; exit ${status}; } >> "logs/analysis-${YDAY}.log" 2>&1
```

手动验证 cron 同款命令时，不需要转义 `%`：

```bash
cd /home/share-user/app/analysis
mkdir -p logs
export PYTHONPATH="/home/share-user/app/analysis:/home/share-user/app/weCom/backend"
. /home/share-user/app/analysis/.venv/bin/activate
YDAY=$(/bin/date -d yesterday +%F)
{
  echo "===== analysis start $(date '+%F %T') target=${YDAY} ====="
  python -m analysis_app.cli run --start-date "${YDAY}" --end-date "${YDAY}"
  status=$?
  echo "===== analysis end $(date '+%F %T') target=${YDAY} exit=${status} ====="
  exit ${status}
} >> "logs/analysis-${YDAY}.log" 2>&1
```

## Danger Zone

- `.env` 会包含数据库密码和 LLM Key，只保留在线上机器，不要提交真实 `.env`。
- `.env` 不负责 `PYTHONPATH`，cron/systemd/shell 仍需要设置 `PYTHONPATH`。
- `message.msg_time` 存的是 UTC naive 时间，不能直接按 `DATE(msg_time)` 当北京时间切天。
- 群聊统计允许重复计数，同一条群消息会归属到多个被观测员工。
- LLM 只接受结构化 JSON；不要把自然语言解释当作模型输出。
- `employee_external_contact` 和 `customer_chat_member` 是当前态表，不是历史快照表。
- `raw_event` 目前不能支撑历史关系回放。
- 不要把真实 API Key 写进代码、README 或测试。
- 不要直接复用 backend 的 `SessionLocal` 处理分析库，分析库和归档库是两套连接。
