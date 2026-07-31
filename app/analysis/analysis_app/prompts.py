from __future__ import annotations

import json

from analysis_app.question_categories import load_question_categories


def _json_schema_enum(values: list[str]) -> str:
    return json.dumps(values, ensure_ascii=False)


def build_sentiment_prompt() -> str:
    schema = {
        "type": "object",
        "additionalProperties": False,
        "required": ["items"],
        "properties": {
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["msgid", "sentiment", "confidence", "reason"],
                    "properties": {
                        "msgid": {"type": "string"},
                        "sentiment": {"type": "string", "enum": ["positive", "neutral", "negative"]},
                        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                        "reason": {"type": "string"},
                    },
                },
            }
        },
    }
    return "\n".join(
        [
            "你是企业微信教育服务群舆情分析助手。",
            "只允许输出合法 JSON，不允许 Markdown、解释文本、前后缀、代码块。",
            "严格按下列 JSON Schema 输出：",
            json.dumps(schema, ensure_ascii=False, indent=2),
        ]
    )


def build_question_prompt() -> str:
    categories = load_question_categories()
    schema = {
        "type": "object",
        "additionalProperties": False,
        "required": ["items"],
        "properties": {
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["msgid", "is_question", "category", "confidence", "reason"],
                    "properties": {
                        "msgid": {"type": "string"},
                        "is_question": {"type": "boolean"},
                        "category": {"type": "string", "enum": [item.key for item in categories]},
                        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                        "reason": {"type": "string"},
                    },
                },
            }
        },
    }
    return "\n".join(
        [
            "你是教育服务群问题分类助手。",
            "分类枚举由 question_categories.py 维护。",
            "只允许输出合法 JSON，不允许 Markdown、解释文本、前后缀、代码块。",
            "严格按下列 JSON Schema 输出：",
            json.dumps(schema, ensure_ascii=False, indent=2),
        ]
    )

