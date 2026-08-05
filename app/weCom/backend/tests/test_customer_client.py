from wecom_app.wecom import customer_client
from wecom_app.wecom.customer_client import WeComAPIError, WeComCustomerClient


def test_get_customer_chat_refreshes_expired_token_and_retries(monkeypatch):
    issued_tokens = ["old-token", "new-token"]
    posted_urls = []

    def fake_get(url):
        return {"access_token": issued_tokens.pop(0)}

    def fake_post(url, payload):
        posted_urls.append(url)
        if len(posted_urls) == 1:
            raise WeComAPIError(42001, "access_token expired")
        return {"group_chat": {"chat_id": payload["chat_id"], "name": "家辉2027中考相伴10"}}

    monkeypatch.setattr(customer_client, "_get", fake_get)
    monkeypatch.setattr(customer_client, "_post", fake_post)

    client = WeComCustomerClient("corp-id", "secret")
    result = client.get_customer_chat("wrcmgDCQAARFMQ70m06LXffYW6d8-xKQ")

    assert result["group_chat"]["name"] == "家辉2027中考相伴10"
    assert "access_token=old-token" in posted_urls[0]
    assert "access_token=new-token" in posted_urls[1]


def test_list_external_contacts_refreshes_expired_token_and_retries(monkeypatch):
    issued_tokens = ["old-token", "new-token"]
    requested_urls = []

    def fake_get(url):
        if "gettoken" in url:
            return {"access_token": issued_tokens.pop(0)}
        requested_urls.append(url)
        if len(requested_urls) == 1:
            raise WeComAPIError(42001, "access_token expired")
        return {"external_userid": ["wm_student"]}

    monkeypatch.setattr(customer_client, "_get", fake_get)

    client = WeComCustomerClient("corp-id", "secret")
    result = client.list_external_contacts("XiaoHaiYan_3")

    assert result == ["wm_student"]
    assert "access_token=old-token" in requested_urls[0]
    assert "access_token=new-token" in requested_urls[1]
