from datetime import date, datetime, timedelta

from analysis_app.models import (
    HotwordDailyStats,
    MessageDailyStats,
    QuestionDetail,
    SentimentDailyStats,
)
from wecom_app.models import Message, RawMessage


def add_raw_message(db, seq: int, msgid: str) -> RawMessage:
    raw = RawMessage(seq=seq, msgid=f"raw_{msgid}", decrypt_payload={"msgtype": "text"})
    db.add(raw)
    db.flush()
    return raw


def add_room_message(db, seq: int, msgid: str, sender_id: str, sender_type: str, msg_time: datetime) -> None:
    raw = add_raw_message(db, seq, msgid)
    db.add(
        Message(
            raw_message_id=raw.id,
            seq=seq,
            msgid=msgid,
            action="send",
            msg_type="text",
            conversation_type="room",
            roomid="chat_math",
            sender_id=sender_id,
            sender_type=sender_type,
            sender_name=sender_id,
            content_text=f"{msgid} content",
            msg_time_ms=1784700000000 + seq,
            msg_time=msg_time,
            raw_payload={"roomid": "chat_math", "msgtype": "text"},
        )
    )


def seed_analysis_rows(db) -> None:
    rows = [
        MessageDailyStats(
            analysis_date=date(2026, 7, 23),
            observer_userid="wang_teacher",
            conversation_type="single",
            external_userid="external_xiaoyu",
            display_name="沈晓雨",
            member_count=1,
            received_count=2,
            sent_count=1,
            received_type_counts={"text": 2, "image": 0, "voice": 0, "video": 0, "emotion": 0, "file": 0, "weapp": 0},
            sent_type_counts={"text": 1, "image": 0, "voice": 0, "video": 0, "emotion": 0, "file": 0, "weapp": 0},
        ),
        MessageDailyStats(
            analysis_date=date(2026, 7, 23),
            observer_userid="wang_teacher",
            conversation_type="room",
            roomid="chat_math",
            display_name="初三数学群",
            member_count=2,
            received_count=5,
            sent_count=3,
            received_type_counts={"text": 4, "image": 1, "voice": 0, "video": 0, "emotion": 0, "file": 0, "weapp": 0},
            sent_type_counts={"text": 2, "image": 0, "voice": 1, "video": 0, "emotion": 0, "file": 0, "weapp": 0},
        ),
        MessageDailyStats(
            analysis_date=date(2026, 7, 24),
            observer_userid="wang_teacher",
            conversation_type="room",
            roomid="chat_math",
            display_name="初三数学群",
            member_count=2,
            received_count=1,
            sent_count=2,
            received_type_counts={"text": 1, "image": 0, "voice": 0, "video": 0, "emotion": 0, "file": 0, "weapp": 0},
            sent_type_counts={"text": 2, "image": 0, "voice": 0, "video": 0, "emotion": 0, "file": 0, "weapp": 0},
        ),
        SentimentDailyStats(
            analysis_date=date(2026, 7, 23),
            observer_userid="wang_teacher",
            roomid="chat_math",
            room_name="初三数学群",
            member_count=2,
            positive_count=1,
            neutral_count=2,
            negative_count=1,
            total_count=4,
        ),
        HotwordDailyStats(
            analysis_date=date(2026, 7, 23),
            observer_userid="wang_teacher",
            roomid="chat_math",
            room_name="初三数学群",
            member_count=2,
            hotwords=[{"word": "作业", "count": 3}, {"word": "课程", "count": 2}],
        ),
        HotwordDailyStats(
            analysis_date=date(2026, 7, 24),
            observer_userid="wang_teacher",
            roomid="chat_math",
            room_name="初三数学群",
            member_count=2,
            hotwords=[{"word": "作业", "count": 4}, {"word": "退款", "count": 1}],
        ),
        QuestionDetail(
            analysis_date=date(2026, 7, 23),
            observer_userid="wang_teacher",
            roomid="chat_math",
            room_name="初三数学群",
            member_count=2,
            msgid="question_true_course",
            content_text="直播课几点开始？",
            sender_external_userid="external_math",
            sender_wechat_name="数学家长",
            sender_group_remark="张同学",
            is_question=True,
            question_category="course",
            llm_output={},
        ),
        QuestionDetail(
            analysis_date=date(2026, 7, 23),
            observer_userid="wang_teacher",
            roomid="chat_math",
            room_name="初三数学群",
            member_count=2,
            msgid="question_false_content",
            content_text="资料已经收到了。",
            sender_external_userid="external_math",
            sender_wechat_name="数学家长",
            sender_group_remark=None,
            is_question=False,
            question_category="content",
            llm_output={},
        ),
        QuestionDetail(
            analysis_date=date(2026, 7, 23),
            observer_userid="wang_teacher",
            roomid="chat_math",
            room_name="初三数学群",
            member_count=2,
            msgid="question_uncategorized",
            content_text="嗯嗯。",
            sender_external_userid="external_math",
            sender_wechat_name="数学家长",
            sender_group_remark=None,
            is_question=True,
            question_category="uncategorized",
            llm_output={},
        ),
    ]
    db.add_all(rows)

    base = datetime(2026, 7, 23, 1, 0)
    samples = [60, 120, 180, 240, 300]
    for index, seconds in enumerate(samples):
        external_time = base + timedelta(hours=index)
        add_room_message(db, 500 + index * 2, f"response_external_{index}", "external_math", "external_contact", external_time)
        add_room_message(
            db,
            501 + index * 2,
            f"response_employee_{index}",
            "wang_teacher",
            "employee",
            external_time + timedelta(seconds=seconds),
        )
    db.commit()


def test_analysis_summary_aggregates_metrics(db, client, auth_headers):
    seed_analysis_rows(db)

    response = client.get(
        "/api/analysis/observed-employees/wang_teacher/summary"
        "?start_date=2026-07-23&end_date=2026-07-24&conversation_type=all",
        headers=auth_headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["overview"]["single_message_count"] == 3
    assert body["overview"]["room_message_count"] == 11
    assert body["overview"]["question_count"] == 1
    assert body["hotwords"][0] == {"word": "作业", "count": 7}
    assert body["question_category_stats"] == [{"code": "course", "display_name": "课程", "count": 1}]
    assert body["response_daily_stats"][0]["median_seconds"] == 180


def test_analysis_questions_filter_uncategorized_and_non_questions(db, client, auth_headers):
    seed_analysis_rows(db)

    response = client.get(
        "/api/analysis/observed-employees/wang_teacher/questions?start_date=2026-07-23&end_date=2026-07-23",
        headers=auth_headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["question_category"] == "course"
    assert body["items"][0]["sender_display_name"] == "张同学"


def test_response_groups_compute_exact_quantiles_and_sort(db, client, auth_headers):
    seed_analysis_rows(db)

    response = client.get(
        "/api/analysis/observed-employees/wang_teacher/response-groups"
        "?start_date=2026-07-23&end_date=2026-07-23&sort=median&order=desc",
        headers=auth_headers,
    )

    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["avg_seconds"] == 180
    assert item["median_seconds"] == 180
    assert item["q1_seconds"] == 120
    assert item["q3_seconds"] == 240
    assert item["min_seconds"] == 60
    assert item["max_seconds"] == 300
    assert item["sample_count"] == 5


def test_customer_chats_are_scoped_to_observer(db, client, auth_headers):
    seed_analysis_rows(db)

    visible = client.get("/api/analysis/customer-chats?observer_userid=wang_teacher", headers=auth_headers)
    hidden = client.get(
        "/api/analysis/customer-chats/chat_math/summary"
        "?observer_userid=disabled_teacher&start_date=2026-07-23&end_date=2026-07-23",
        headers=auth_headers,
    )

    assert visible.status_code == 200
    assert visible.json()["items"][0]["roomid"] == "chat_math"
    assert hidden.status_code == 403


def test_question_categories_exclude_uncategorized(client, auth_headers):
    response = client.get("/api/analysis/question-categories", headers=auth_headers)

    assert response.status_code == 200
    codes = [item["code"] for item in response.json()["items"]]
    assert "course" in codes
    assert "uncategorized" not in codes


def test_analysis_rejects_dates_before_lower_bound(client, auth_headers):
    response = client.get(
        "/api/analysis/observed-employees/wang_teacher/summary"
        "?start_date=2026-07-19&end_date=2026-07-23",
        headers=auth_headers,
    )

    assert response.status_code == 422
