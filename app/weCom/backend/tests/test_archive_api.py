def test_requires_admin_token(client):
    response = client.get("/api/observable-employees")

    assert response.status_code == 401


def test_lists_observable_employees(client, auth_headers):
    response = client.get("/api/observable-employees", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["items"][0]["userid"] == "wang_teacher"


def test_imports_observable_employees_csv(client, auth_headers):
    response = client.post(
        "/api/observable-employees/import",
        headers=auth_headers,
        files={
            "file": (
                "employees.csv",
                "userid,name,department_id,department_name,scope_status\nli_teacher,李老师,101,高中部,enabled\n",
                "text/csv",
            )
        },
    )

    assert response.status_code == 200
    assert response.json()["imported"] == 1
    employees = client.get("/api/observable-employees", headers=auth_headers)
    userids = {item["userid"] for item in employees.json()["items"]}
    assert "li_teacher" in userids


def test_rejects_disabled_observed_user(client, auth_headers):
    response = client.get(
        "/api/observed-employees/disabled_teacher/conversations",
        headers=auth_headers,
    )

    assert response.status_code == 403


def test_lists_student_conversation_and_messages(client, auth_headers):
    conversations = client.get(
        "/api/observed-employees/wang_teacher/conversations?type=student",
        headers=auth_headers,
    )

    assert conversations.status_code == 200
    assert conversations.json()["items"][0]["display_name"] == "沈晓雨"

    messages = client.get(
        "/api/observed-employees/wang_teacher/student-conversations/external_xiaoyu/messages",
        headers=auth_headers,
    )
    assert messages.status_code == 200
    assert messages.json()["items"][0]["content"]["text"] == "先看交点"


def test_search_is_scoped_to_current_conversation(client, auth_headers):
    response = client.get(
        "/api/observed-employees/wang_teacher/conversations/student/external_xiaoyu/message-search?keyword=交点",
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.json()["items"][0]["msgid"] == "msg_text_1"
