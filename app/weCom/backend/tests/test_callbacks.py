def test_callback_verify_echo(client):
    # Token and AES key are empty in test config, so crypto is bypassed.
    # Response must be plain text (no JSON quotes) per WeCom spec.
    response = client.get("/callbacks/wecom/contact?timestamp=1&nonce=2&echostr=hello")

    assert response.status_code == 200
    assert response.headers["content-type"] == "text/plain; charset=utf-8"
    assert response.text == "hello"


def test_callback_post_persists_event(client):
    response = client.post("/callbacks/wecom/archive-event?timestamp=1&nonce=2", content="<xml />")

    assert response.status_code == 200
    assert response.json()["status"] == "accepted"
