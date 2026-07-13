def test_callback_verify_echo(client):
    response = client.get("/callbacks/wecom/contact?timestamp=1&nonce=2&echostr=hello")

    assert response.status_code == 200
    assert response.text == '"hello"'


def test_callback_post_persists_event(client):
    response = client.post("/callbacks/wecom/archive-event?timestamp=1&nonce=2", content="<xml />")

    assert response.status_code == 200
    assert response.json()["status"] == "accepted"
