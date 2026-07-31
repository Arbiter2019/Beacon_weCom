from datetime import date

import jieba

from analysis_app.services.hotwords import run_hotwords


def test_hotwords_filters_stopwords_and_uses_top_words(db, monkeypatch):
    monkeypatch.setattr(jieba, "lcut", lambda text: ["老师", "作业", "作业", "今天", "今天", "今天", "我们"])

    result = run_hotwords(db, db, date(2026, 7, 21), observer_userid="wang_teacher")

    assert result["rows_written"] == 1
    hotwords = result["rows"][0].hotwords
    assert hotwords[0]["word"] == "今天"
    assert hotwords[0]["count"] == 6
    assert all(item["word"] != "老师" for item in hotwords)
