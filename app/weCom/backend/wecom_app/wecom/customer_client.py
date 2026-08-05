"""WeCom REST API HTTP client (customer contact / directory APIs)."""
import json
import logging
import urllib.parse
import urllib.request

logger = logging.getLogger(__name__)
QYAPI = "https://qyapi.weixin.qq.com"


class WeComAPIError(Exception):
    def __init__(self, errcode: int, errmsg: str):
        super().__init__(f"WeCom API {errcode}: {errmsg}")
        self.errcode = errcode


def _get(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=10) as r:
        data = json.loads(r.read().decode())
    if data.get("errcode", 0) != 0:
        raise WeComAPIError(data["errcode"], data.get("errmsg", ""))
    return data


def _post(url: str, payload: dict) -> dict:
    body = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as r:
        data = json.loads(r.read().decode())
    if data.get("errcode", 0) != 0:
        raise WeComAPIError(data["errcode"], data.get("errmsg", ""))
    return data


class WeComCustomerClient:
    """Thin wrapper around WeCom customer-contact REST APIs."""

    def __init__(self, corp_id: str, secret: str) -> None:
        self._corp_id = corp_id
        self._secret = secret
        self._token: str = self._fetch_token()
        logger.info("WeComCustomerClient access_token acquired")

    def _fetch_token(self) -> str:
        url = (
            f"{QYAPI}/cgi-bin/gettoken"
            f"?corpid={urllib.parse.quote(self._corp_id)}"
            f"&corpsecret={urllib.parse.quote(self._secret)}"
        )
        return _get(url)["access_token"]

    def _refresh_token(self) -> None:
        self._token = self._fetch_token()
        logger.info("WeComCustomerClient access_token refreshed")

    def _url(self, path: str) -> str:
        sep = "&" if "?" in path else "?"
        return f"{QYAPI}{path}{sep}access_token={self._token}"

    def _get_with_token_retry(self, path: str) -> dict:
        try:
            return _get(self._url(path))
        except WeComAPIError as exc:
            if exc.errcode != 42001:
                raise
            self._refresh_token()
            return _get(self._url(path))

    def _post_with_token_retry(self, path: str, payload: dict) -> dict:
        try:
            return _post(self._url(path), payload)
        except WeComAPIError as exc:
            if exc.errcode != 42001:
                raise
            self._refresh_token()
            return _post(self._url(path), payload)

    def list_external_contacts(self, userid: str) -> list[str]:
        """Return list of external_userid for a given employee."""
        try:
            data = self._get_with_token_retry(
                f"/cgi-bin/externalcontact/list?userid={urllib.parse.quote(userid)}"
            )
            return data.get("external_userid", [])
        except WeComAPIError as e:
            if e.errcode in (84061, 84069):  # no external contacts
                return []
            raise

    def get_external_contact(self, external_userid: str) -> dict:
        """Return full detail of one external contact including follow_user list."""
        return self._get_with_token_retry(
            f"/cgi-bin/externalcontact/get?external_userid={urllib.parse.quote(external_userid)}"
        )

    def list_customer_chats(self, userid: str | None = None, cursor: str = "", limit: int = 1000) -> dict:
        payload: dict = {"status_filter": 0, "cursor": cursor, "limit": limit}
        if userid:
            payload["owner_filter"] = {"userid_list": [userid]}
        return self._post_with_token_retry("/cgi-bin/externalcontact/groupchat/list", payload)

    def get_customer_chat(self, chat_id: str, need_name: int = 1) -> dict:
        return self._post_with_token_retry(
            "/cgi-bin/externalcontact/groupchat/get",
            {"chat_id": chat_id, "need_name": need_name},
        )
