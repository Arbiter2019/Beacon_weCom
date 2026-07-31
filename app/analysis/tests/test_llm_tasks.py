from datetime import date

from analysis_app.services.question_classification import run_question_classification
from analysis_app.services.sentiment import run_sentiment_analysis


class FakeLLMClient:
    def __init__(self, sentiment_items=None, question_items=None):
        self.sentiment_items = sentiment_items or []
        self.question_items = question_items or []

    def analyze_sentiment(self, prompt, messages):
        return {"items": self.sentiment_items}

    def analyze_questions(self, prompt, messages):
        return {"items": self.question_items}


def test_run_sentiment_analysis_persists_detail_and_daily_stats(db):
    client = FakeLLMClient(
        sentiment_items=[
            {"msgid": "msg_group_ext_1", "sentiment": "negative", "confidence": 0.95, "reason": "问难题"},
            {"msgid": "msg_group_ext_2", "sentiment": "positive", "confidence": 0.88, "reason": "积极"},
        ]
    )

    result = run_sentiment_analysis(db, db, date(2026, 7, 21), client, observer_userid="wang_teacher")

    assert result["detail_rows_written"] == 2
    assert result["daily_rows_written"] == 1
    daily = result["daily_rows"][0]
    assert daily.negative_count == 1
    assert daily.positive_count == 1
    assert daily.total_count == 2


def test_run_question_classification_uses_dynamic_categories(db):
    client = FakeLLMClient(
        question_items=[
            {
                "msgid": "msg_group_ext_1",
                "is_question": True,
                "category": "course",
                "confidence": 0.91,
                "reason": "问课程",
            },
            {
                "msgid": "msg_group_ext_2",
                "is_question": False,
                "category": "uncategorized",
                "confidence": 0.76,
                "reason": "陈述",
            },
        ]
    )

    result = run_question_classification(db, db, date(2026, 7, 21), client, observer_userid="wang_teacher")

    assert result["rows_written"] == 2
    assert result["rows"][0].question_category == "course"
    assert result["rows"][0].is_question is True
    assert result["rows"][1].question_category == "uncategorized"
