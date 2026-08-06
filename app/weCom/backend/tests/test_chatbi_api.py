from datetime import date, datetime

from analysis_app.models import (
    HotwordDailyStats,
    MessageDailyStats,
    QuestionDetail,
    ResponseHourlyStats,
    SentimentDailyStats,
    TaskRun,
)
from wecom_app.models import Message, RawMessage


def chatbi_headers() -> dict[str, str]:
    return {"X-ChatBI-Token": "dev-chatbi-token"}


def add_room_message(db, seq: int, msgid: str, content: str, msg_time: datetime) -> None:
    raw = RawMessage(seq=seq, msgid=f"raw_{msgid}", decrypt_payload={"msgtype": "text"})
    db.add(raw)
    db.flush()
    db.add(
        Message(
            raw_message_id=raw.id,
            seq=seq,
            msgid=msgid,
            action="send",
            msg_type="text",
            conversation_type="room",
            roomid="chat_math",
            sender_id="external_math",
            sender_type="external_contact",
            sender_name="数学家长",
            content_text=content,
            msg_time_ms=1784768400000 + seq,
            msg_time=msg_time,
            raw_payload={"roomid": "chat_math", "msgtype": "text"},
        )
    )


def seed_chatbi_rows(db) -> None:
    db.add_all(
        [
            TaskRun(
                run_id="run_latest",
                task_type="all",
                analysis_date=date(2026, 7, 24),
                observer_userid=None,
                status="success",
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
                received_type_counts={"text": 5, "image": 0, "voice": 0, "video": 0, "emotion": 0, "file": 0, "weapp": 0},
                sent_type_counts={"text": 3, "image": 0, "voice": 0, "video": 0, "emotion": 0, "file": 0, "weapp": 0},
            ),
            MessageDailyStats(
                analysis_date=date(2026, 7, 24),
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
            ResponseHourlyStats(
                analysis_date=date(2026, 7, 23),
                observer_userid="wang_teacher",
                conversation_type="room",
                roomid="chat_math",
                display_name="初三数学群",
                member_count=2,
                hour=18,
                response_avg_seconds=120,
                response_count=2,
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
                hotwords=[{"word": "作业", "count": 3}],
            ),
            QuestionDetail(
                analysis_date=date(2026, 7, 23),
                observer_userid="wang_teacher",
                roomid="chat_math",
                room_name="初三数学群",
                member_count=2,
                msgid="question_course",
                content_text="直播课几点开始？",
                sender_external_userid="external_math",
                sender_wechat_name="数学家长",
                sender_group_remark="张同学",
                is_question=True,
                question_category="course",
                llm_output={},
            ),
        ]
    )
    add_room_message(db, 900, "archive_keyword_1", "今晚作业是什么？", datetime(2026, 7, 23, 10, 30))
    db.commit()


def test_chatbi_rejects_invalid_token(client):
    response = client.get("/api/chatbi/freshness", headers={"X-ChatBI-Token": "wrong"})

    assert response.status_code == 401


def test_chatbi_freshness_returns_latest_analysis_date(db, client):
    seed_chatbi_rows(db)

    response = client.get("/api/chatbi/freshness?request_id=req_1", headers=chatbi_headers())

    assert response.status_code == 200
    body = response.json()
    assert body["request_id"] == "req_1"
    assert body["rows"] == [{"latest_analysis_date": "2026-07-24", "data_freshness": "T+1"}]
    assert body["meta"]["datasource"] == "analysis"
    assert body["meta"]["data_freshness"] == "T+1"


def test_chatbi_message_volume_returns_sql_rows_and_meta(db, client):
    seed_chatbi_rows(db)

    response = client.get(
        "/api/chatbi/message-volume?start_date=2026-07-23&end_date=2026-07-24&conversation_type=all",
        headers=chatbi_headers(),
    )

    assert response.status_code == 200
    body = response.json()
    assert "analysis_message_daily_stats" in body["sql"]
    assert body["rows"] == [
        {
            "analysis_date": "2026-07-23",
            "conversation_type": "room",
            "received_count": 5,
            "sent_count": 3,
            "total_count": 8,
        },
        {
            "analysis_date": "2026-07-24",
            "conversation_type": "single",
            "received_count": 2,
            "sent_count": 1,
            "total_count": 3,
        },
    ]
    assert body["meta"]["chart_hint"] == "line"
    assert body["meta"]["row_count"] == 2


def test_chatbi_archive_search_limits_and_converts_beijing_time(db, client):
    seed_chatbi_rows(db)

    response = client.get(
        "/api/chatbi/archive-search?keyword=作业&start_datetime=2026-07-23T18:00:00"
        "&end_datetime=2026-07-23T19:00:00&limit=20000",
        headers=chatbi_headers(),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["meta"]["datasource"] == "archive"
    assert body["meta"]["limit"] == 10000
    assert body["meta"]["time_zone"] == "Asia/Shanghai"
    assert body["rows"][0]["content_text"] == "今晚作业是什么？"
    assert body["rows"][0]["msg_time"] == "2026-07-23T18:30:00+08:00"


def test_chatbi_response_time_returns_hourly_rows(db, client):
    seed_chatbi_rows(db)

    response = client.get(
        "/api/chatbi/response-time?start_date=2026-07-23&end_date=2026-07-23",
        headers=chatbi_headers(),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["rows"] == [
        {
            "analysis_date": "2026-07-23",
            "hour": 18,
            "response_avg_seconds": 120,
            "response_count": 2,
        }
    ]
    assert body["meta"]["chart_hint"] == "line"


def test_chatbi_questions_return_message_time_from_archive(db, client):
    seed_chatbi_rows(db)
    add_room_message(db, 901, "question_course", "直播课几点开始？", datetime(2026, 7, 23, 10, 35))
    db.commit()

    response = client.get(
        "/api/chatbi/questions?start_date=2026-07-23&end_date=2026-07-23",
        headers=chatbi_headers(),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["rows"][0]["msgid"] == "question_course"
    assert body["rows"][0]["msg_time"] == "2026-07-23T18:35:00+08:00"


def test_chatbi_sentiment_and_hotwords_return_chart_hints(db, client):
    seed_chatbi_rows(db)

    sentiment = client.get(
        "/api/chatbi/sentiment?start_date=2026-07-23&end_date=2026-07-23",
        headers=chatbi_headers(),
    )
    hotwords = client.get(
        "/api/chatbi/hotwords?start_date=2026-07-23&end_date=2026-07-23&top_n=1",
        headers=chatbi_headers(),
    )

    assert sentiment.status_code == 200
    assert sentiment.json()["rows"] == [
        {"positive_count": 1, "neutral_count": 2, "negative_count": 1, "total_count": 4}
    ]
    assert sentiment.json()["meta"]["chart_hint"] == "donut"
    assert hotwords.status_code == 200
    assert hotwords.json()["rows"] == [{"word": "作业", "count": 3}]
    assert hotwords.json()["meta"]["chart_hint"] == "bar"
