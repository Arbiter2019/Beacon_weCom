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