# 把 ZhangSan 改为你从后台复制的 userid
curl -s -X POST http://localhost:8717/api/observable-employees \
  -H "Authorization: Bearer 19c1e264cc26ce38a763f07b3acff4c64a736c935d0b959bcb255f980767afa0" \
  -H "Content-Type: application/json" \
  -d '{"userid": "XuWei", "scope_status": "enabled"}'

TOKEN="tPjUMV6RFCTFWMXR558TtpdnsNAjFjub-erzPsb67_7G4cZiry4Z0JNRxfwk2tHptJZdoxIF5loHo61ltoRIrUovdGbBzDOP__kYov7hSbConywwovCKcjxdZANxsIIPLzyYXsSgjB9_e2x0iGTYGRNwXuZc_UbRKtS66BnWfHt0EG1a_O1bZal0XWDEoc-tbjDsvMIXF9OS-VbQlkcXvw"

curl -s -X POST \
  "https://qyapi.weixin.qq.com/cgi-bin/msgaudit/check_single_agree?access_token=$TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "info": [{"userid": "XuWei", "exteranalopenid": ""}]
  }'
TOKEN="tPjUMV6RFCTFWMXR558TtpdnsNAjFjub-erzPsb67_7G4cZiry4Z0JNRxfwk2tHptJZdoxIF5loHo61ltoRIrUovdGbBzDOP__kYov7hSbConywwovCKcjxdZANxsIIPLzyYXsSgjB9_e2x0iGTYGRNwXuZc_UbRKtS66BnWfHt0EG1a_O1bZal0XWDEoc-tbjDsvMIXF9OS-VbQlkcXvw"

curl -s "https://qyapi.weixin.qq.com/cgi-bin/msgaudit/get_permit_user_list?access_token=$TOKEN&type=1"


curl -s -X POST http://localhost:8717/api/observable-employees \
  -H "Authorization: Bearer 19c1e264cc26ce38a763f07b3acff4c64a736c935d0b959bcb255f980767afa0" \
  -H "Content-Type: application/json" \
  -d '{"KeLe": "JiaHuiWangXiaoXiaoHuiLaoShiQiuJiXuBaoing", "scope_status": "enabled"}'

["ZhouWeiWei","XiaoTao","ShenQingWen","JiaHuiPeiYouXiaoZhouLaoShi","JiaHuiWangXiaoXiaoHuiLaoShiQiuJiXuBaoing","KeLe","XuWei"]

docker compose exec wecom-worker python -m wecom_app.cli sync external-contacts --userid XuWei --userid XuWei


## 查看日志同步进度
docker compose exec -T wecom-api python -c 'from sqlalchemy import text; from wecom_app.db.session import SessionLocal; db=SessionLocal(); print(db.execute(text("select cursor_value,last_success_at,last_error from sync_cursor where cursor_type=\"message_seq\"")).fetchone()); print(db.execute(text("select count(*), max(seq), max(msg_time) from raw_message")).fetchone()); db.close()'

## CLI命令
docker compose exec wecom-api <README.md中的cli>

## Docker 日志排查

> 以下命令都在 `/home/share-user/app/weCom` 或本项目 `app/weCom` 目录下执行。

### 查看服务状态

```bash
docker compose ps
```

### 查看所有服务日志

```bash
docker compose logs --tail=200
docker compose logs -f --tail=200
```

### 查看 API 服务日志

```bash
docker compose logs wecom-api --tail=200
docker compose logs -f wecom-api --tail=200
```

### 查看后台 worker 同步日志

```bash
docker compose logs wecom-worker --tail=200
docker compose logs -f wecom-worker --tail=200
```

### 查看 MySQL 日志

```bash
docker compose logs mysql --tail=200
docker compose logs -f mysql --tail=200
```

### 查看最近报错

```bash
docker compose logs --tail=500 wecom-api | grep -iE "error|exception|traceback|failed"
docker compose logs --tail=500 wecom-worker | grep -iE "error|exception|traceback|failed"
```

### 查看锁等待/数据库问题

```bash
docker compose logs --tail=500 mysql | grep -iE "lock|timeout|deadlock|error"
```

```bash
docker compose exec -T mysql mysql -uroot -p"$MYSQL_ROOT_PASSWORD" -e "SHOW PROCESSLIST;"
docker compose exec -T mysql mysql -uroot -p"$MYSQL_ROOT_PASSWORD" -e "SHOW ENGINE INNODB STATUS\G"
```

## Docker CLI 常用指令

### 启动、停止、重启

```bash
docker compose up -d
docker compose down
docker compose restart
docker compose restart wecom-api
docker compose restart wecom-worker
docker compose restart mysql
```

### 重新构建并启动

```bash
docker compose build
docker compose up -d --build
docker compose up -d --build wecom-api wecom-worker
```

### 进入容器

```bash
docker compose exec wecom-api bash
docker compose exec wecom-worker bash
docker compose exec mysql bash
```

### 在容器内执行 Python/SQL 排查

```bash
docker compose exec -T wecom-api python -c 'from wecom_app.core.config import get_settings; s=get_settings(); print(s.api_base_url); print(s.effective_database_url)'
```

```bash
docker compose exec -T wecom-api python -c 'from sqlalchemy import text; from wecom_app.db.session import SessionLocal; db=SessionLocal(); print(db.execute(text("select cursor_value,last_run_at,last_success_at,last_error from sync_cursor where cursor_type=\"message_seq\"")).fetchone()); print(db.execute(text("select count(*), max(seq), max(msg_time) from raw_message")).fetchone()); db.close()'
```

```bash
docker compose exec -T wecom-api python -c 'from sqlalchemy import text; from wecom_app.db.session import SessionLocal; db=SessionLocal(); print(db.execute(text("select process_status,count(*) from raw_message group by process_status")).fetchall()); db.close()'
```

### 查看容器资源占用

```bash
docker stats
docker compose top
```

### 清理无用镜像/容器

```bash
docker system df
docker image prune
docker container prune
```

## wecomctl CLI 常用指令

### 健康检查

```bash
docker compose exec wecom-api wecomctl health
```

### 查看回调地址

```bash
docker compose exec wecom-api wecomctl callback urls
```

### 校验回调配置

```bash
docker compose exec wecom-api wecomctl callback verify
```

### 手动同步消息

```bash
docker compose exec wecom-api wecomctl sync once --type message
```

如果后台 `wecom-worker` 正在同步，可能会返回：

```text
message sync skipped: another sync is running
```

这表示已有同步任务在跑，稍后重试即可。

### 手动同步客户联系人

```bash
docker compose exec wecom-api wecomctl sync once --type contacts
docker compose exec wecom-api wecomctl sync external-contacts
docker compose exec wecom-api wecomctl sync external-contacts --userid XuWei
docker compose exec wecom-api wecomctl sync external-contacts --userid XuWei --userid KeLe
```

### 手动同步客户群

```bash
docker compose exec wecom-api wecomctl sync once --type customer-chat
```

### 手动同步附件

```bash
docker compose exec wecom-api wecomctl sync once --type attachments
```

### 导入员工 CSV

```bash
docker compose exec wecom-api wecomctl import employees --file /path/in/container/employees.csv
```
