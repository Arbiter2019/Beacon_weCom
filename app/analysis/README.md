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

分析模块不会读取 `app/weCom/.env` 文件本身；部署时需要把下列环境变量导出到当前 shell、cron 脚本或 systemd unit 中。

### 必填

```bash
export PYTHONPATH="/home/share-user/app/analysis:/home/share-user/app/weCom/backend"

export ARCHIVE_DATABASE_URL="mysql+pymysql://wecom:<MYSQL_PASSWORD>@127.0.0.1:3306/wecom_archive"
export ANALYSIS_DATABASE_URL="mysql+pymysql://wecom:<MYSQL_PASSWORD>@127.0.0.1:3306/wecom_analysis"
```

说明：

- `PYTHONPATH` 需要同时包含分析模块和现有后端模块，因为分析代码复用 `wecom_app.models`。
- `ARCHIVE_DATABASE_URL` 读取现有归档库。
- `ANALYSIS_DATABASE_URL` 写入独立分析库。
- `<MYSQL_PASSWORD>` 沿用 `app/weCom/.env` 中的 `MYSQL_PASSWORD`。
- 在宿主机执行时 MySQL host 使用 `127.0.0.1`；如果在 Docker 网络内执行，host 使用 `mysql`。

### LLM 任务配置

如果执行默认全量任务，会包含舆情和问题分类，因此需要配置 `LLM_API_KEY`。如果暂时不配置 LLM，只运行 `snapshot/basic/response/hotwords` 即可。

```bash
export LLM_PROVIDER="qwen"
export LLM_API_KEY="sk-ws-H.EMDMXYE.VByF.MEYCIQDhkCyDWdho9oyNZgSQaTSwsi9UOjJfKAq_Ulq62M4BdQIhAPbZo3PCPq9_ALRmJpyp5VfEiLFUXYmS7SHw3DDojFhr"
export LLM_BASE_URL="https://dashscope.aliyuncs.com/compatible-mode/v1"
export LLM_MODEL="kimi-k2.6"
export LLM_MAX_TOKENS="2048"
export LLM_TEMPERATURE="0.1"
export LLM_TIMEOUT_SECONDS="60"
export LLM_MAX_RETRIES="3"
```

### 分析运行配置

```bash
export ANALYSIS_TIMEZONE="Asia/Shanghai"
export ANALYSIS_MAX_WORKERS="4"
export HOTWORD_STOPWORDS_PATH="/home/share-user/app/analysis/config/hotword_stopwords.txt"
```
> HOTWORD_STOPWORDS_PATH 可选

### 可复制示例

```bash
export PYTHONPATH="/home/share-user/app/analysis:/home/share-user/app/weCom/backend"
export ARCHIVE_DATABASE_URL="mysql+pymysql://wecom:<MYSQL_PASSWORD>@127.0.0.1:3306/wecom_archive"
export ANALYSIS_DATABASE_URL="mysql+pymysql://wecom:<MYSQL_PASSWORD>@127.0.0.1:3306/wecom_analysis"
export LLM_PROVIDER="qwen"
export LLM_API_KEY="<你的阿里云DashScope API Key>"
export LLM_BASE_URL="https://dashscope.aliyuncs.com/compatible-mode/v1"
export LLM_MODEL="kimi-k2.6"
export LLM_MAX_TOKENS="2048"
export LLM_TEMPERATURE="0.1"
export LLM_TIMEOUT_SECONDS="60"
export LLM_MAX_RETRIES="3"
export ANALYSIS_TIMEZONE="Asia/Shanghai"
export ANALYSIS_MAX_WORKERS="4"
export HOTWORD_STOPWORDS_PATH="/home/share-user/app/analysis/config/hotword_stopwords.txt"
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

4. 配置分析模块连接串。密码沿用 `app/weCom/.env` 中的 `MYSQL_PASSWORD`：

```bash
export ARCHIVE_DATABASE_URL="mysql+pymysql://wecom:<MYSQL_PASSWORD>@127.0.0.1:3306/wecom_archive"
export ANALYSIS_DATABASE_URL="mysql+pymysql://wecom:<MYSQL_PASSWORD>@127.0.0.1:3306/wecom_analysis"
```

如果在 Docker 网络内执行，host 使用 `mysql`；如果在宿主机执行，host 使用 `127.0.0.1`。

5. 安装并 smoke test：

```bash
cd app/analysis
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
python -m analysis_app.cli run --start-date 2026-07-21 --end-date 2026-07-21
```

如果 `python3 -m venv .venv` 提示缺少 `ensurepip` 或 `venv`，先安装系统 venv 包：

```bash
apt update
apt install -y python3-venv
```

### 日常部署 / 手动执行

如果从仓库根目录执行，也可以先设置：

```bash
export PYTHONPATH="/Users/xuwei/Desktop/morpheus/Projects/Beacon/WeCom/app/analysis:/Users/xuwei/Desktop/morpheus/Projects/Beacon/WeCom/app/weCom/backend"
```

热词停用词文件建议显式配置为项目内文件：

```bash
export HOTWORD_STOPWORDS_PATH="/home/share-user/app/analysis/config/hotword_stopwords.txt"
```

## Danger Zone

- `message.msg_time` 存的是 UTC naive 时间，不能直接按 `DATE(msg_time)` 当北京时间切天。
- 群聊统计允许重复计数，同一条群消息会归属到多个被观测员工。
- LLM 只接受结构化 JSON；不要把自然语言解释当作模型输出。
- `employee_external_contact` 和 `customer_chat_member` 是当前态表，不是历史快照表。
- `raw_event` 目前不能支撑历史关系回放。
- 不要把真实 API Key 写进代码、README 或测试。
- 不要直接复用 backend 的 `SessionLocal` 处理分析库，分析库和归档库是两套连接。
