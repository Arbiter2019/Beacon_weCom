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

docker compose exec wecom-worker wecomctl sync external-contacts --userid XuWei --userid XuWei

curl -s -X POST http://localhost:8717/api/observable-employees \
  -H "Authorization: Bearer 19c1e264cc26ce38a763f07b3acff4c64a736c935d0b959bcb255f980767afa0" \
  -H "Content-Type: application/json" \
  -d '{"userid": "XuWei", "scope_status": "enabled"}'

export INTERNAL_ADMIN_TOKEN="19c1e264cc26ce38a763f07b3acff4c64a736c935d0b959bcb255f980767afa0"

curl -X POST http://101.132.83.149:8717/api/observable-employees/import \
  -H "Authorization: Bearer $INTERNAL_ADMIN_TOKEN" \
  -F "file=@test.csv"


docker compose exec wecom-api python -c "from sqlalchemy import select; from wecom_app.db.session import SessionLocal; from wecom_app.models import Attachment; from wecom_app.wecom.client import WeComArchiveClient; db=SessionLocal(); a=db.get(Attachment, 108169); print('try', a.id, a.msgid, len(a.sdkfileid or '')); c=WeComArchiveClient(); data=c.download_media(a.sdkfileid); print('downloaded bytes=', len(data)); c.close(); db.close()"

## 使用临时容器执行手动同步 CLI

用途：

- 临时补齐会话存档消息数据，例如调整企业微信会话存档范围后回补历史消息。
- 定向同步某个员工的外部联系人关系，例如 `XiaoHaiYan_3`。
- 手动同步客户群关系。
- 使用 `docker compose run --rm` 会创建一个一次性容器执行命令，执行结束后自动删除这个临时容器。不会删除镜像、代码、数据库或 volume。

前置命令：

```bash
cd /home/share-user/app/weCom

docker compose stop wecom-worker wecom-api

docker compose exec -T mysql sh -lc 'mysql -u"$MYSQL_USER" -p"$MYSQL_PASSWORD" "$MYSQL_DATABASE"' <<'SQL'
SELECT
  IS_FREE_LOCK('wecom_sync_messages') AS message_lock_free,
  IS_USED_LOCK('wecom_sync_messages') AS message_lock_conn_id,
  IS_FREE_LOCK('wecom_sync_external_contacts') AS contacts_lock_free,
  IS_USED_LOCK('wecom_sync_external_contacts') AS contacts_lock_conn_id,
  IS_FREE_LOCK('wecom_sync_customer_chats') AS chats_lock_free,
  IS_USED_LOCK('wecom_sync_customer_chats') AS chats_lock_conn_id;
SQL
```

正常情况下，三个 `*_lock_free` 都应为 `1`。如果某个锁仍为 `0`，先确认是否还有同步任务在跑，不要直接并发补数据。

回拨消息游标后补齐对话数据：

```bash
docker compose exec -T mysql sh -lc 'mysql -u"$MYSQL_USER" -p"$MYSQL_PASSWORD" "$MYSQL_DATABASE"' <<'SQL'
UPDATE sync_cursor
SET cursor_value = '43647720',
    last_error = NULL
WHERE cursor_type = 'message_seq';

SELECT cursor_type, cursor_value, last_run_at, last_success_at, last_error
FROM sync_cursor
WHERE cursor_type = 'message_seq';
SQL

docker compose run --rm wecom-worker wecomctl sync once --type message
```

如需连续补多轮：

```bash
for i in $(seq 1 10); do
  docker compose run --rm wecom-worker wecomctl sync once --type message
done
```

定向同步 `XiaoHaiYan_3` 的外部联系人关系：

```bash
docker compose run --rm wecom-worker wecomctl sync external-contacts --userid XiaoHaiYan_3
```

同步客户群关系：

```bash
docker compose run --rm wecom-worker wecomctl sync once --type customer-chat
```

如果当前镜像未安装 `wecomctl` 脚本，可使用兜底入口：

```bash
docker compose run --rm wecom-worker python -c "from wecom_app.cli import app; app()" sync once --type message
docker compose run --rm wecom-worker python -c "from wecom_app.cli import app; app()" sync external-contacts --userid XiaoHaiYan_3
docker compose run --rm wecom-worker python -c "from wecom_app.cli import app; app()" sync once --type customer-chat
```

不要使用 `python -m wecom_app.cli` 执行 CLI；当前模块没有 `__main__` 入口，会加载后直接退出，不会真正同步。

验证 `XiaoHaiYan_3` 是否已有私聊消息入库：

```bash
docker compose exec -T mysql sh -lc 'mysql -u"$MYSQL_USER" -p"$MYSQL_PASSWORD" "$MYSQL_DATABASE"' <<'SQL'
SET @observer = 'XiaoHaiYan_3';

SELECT m.seq, m.msgid, m.conversation_type, m.msg_type,
       DATE_ADD(m.msg_time, INTERVAL 8 HOUR) AS bj_time,
       m.sender_id, r.recipient_id, m.content_text
FROM message m
JOIN message_recipient r ON r.message_id = m.id
WHERE m.conversation_type = 'single'
  AND (
    m.sender_id = @observer
    OR r.recipient_id = @observer
  )
ORDER BY m.seq DESC
LIMIT 50;
SQL
```

补完后再次确认锁释放，并恢复服务：

```bash
docker compose exec -T mysql sh -lc 'mysql -u"$MYSQL_USER" -p"$MYSQL_PASSWORD" "$MYSQL_DATABASE"' <<'SQL'
SELECT
  IS_FREE_LOCK('wecom_sync_messages') AS message_lock_free,
  IS_USED_LOCK('wecom_sync_messages') AS message_lock_conn_id,
  IS_FREE_LOCK('wecom_sync_external_contacts') AS contacts_lock_free,
  IS_USED_LOCK('wecom_sync_external_contacts') AS contacts_lock_conn_id,
  IS_FREE_LOCK('wecom_sync_customer_chats') AS chats_lock_free,
  IS_USED_LOCK('wecom_sync_customer_chats') AS chats_lock_conn_id;
SQL

docker compose start wecom-api wecom-worker
```
