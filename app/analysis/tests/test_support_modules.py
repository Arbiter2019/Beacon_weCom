from analysis_app.prompts import build_question_prompt, build_sentiment_prompt
from analysis_app.question_categories import DEFAULT_QUESTION_CATEGORIES, load_question_categories
from analysis_app.stopwords import DEFAULT_STOPWORDS, load_stopwords


def test_default_stopwords_include_common_noise_words():
    assert {"我们", "好的", "老师"}.issubset(DEFAULT_STOPWORDS)


def test_load_stopwords_merges_file_and_deduplicates(tmp_path):
    path = tmp_path / "stopwords.txt"
    path.write_text("好的\n新词\n", encoding="utf-8")

    stopwords = load_stopwords(path)

    assert "好的" in stopwords
    assert "新词" in stopwords
    assert len(stopwords) == len(set(stopwords))


def test_question_categories_have_default_entries():
    keys = [item.key for item in DEFAULT_QUESTION_CATEGORIES]
    assert keys == ["course", "content", "refund", "marketing", "service", "uncategorized"]


def test_load_question_categories_returns_copy():
    categories = load_question_categories()

    assert categories is not DEFAULT_QUESTION_CATEGORIES
    assert [item.key for item in categories] == [item.key for item in DEFAULT_QUESTION_CATEGORIES]


def test_sentiment_prompt_contains_hard_json_schema_constraints():
    prompt = build_sentiment_prompt()

    assert '"additionalProperties": false' in prompt
    assert '"sentiment"' in prompt
    assert '"positive"' in prompt


def test_question_prompt_mentions_dynamic_category_enum():
    prompt = build_question_prompt()

    assert "question_categories.py" in prompt
    assert '"category"' in prompt
    assert '"uncategorized"' in prompt
