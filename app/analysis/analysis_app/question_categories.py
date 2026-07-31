from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class QuestionCategory:
    key: str
    label: str
    description: str


DEFAULT_QUESTION_CATEGORIES: tuple[QuestionCategory, ...] = (
    QuestionCategory("course", "课程", "课程安排、上课时间、课程报名、课程体系。"),
    QuestionCategory("content", "内容", "学习内容、题目、作业、资料、知识点。"),
    QuestionCategory("refund", "退费", "退款、退费、取消购买。"),
    QuestionCategory("marketing", "营销", "优惠、活动、转介绍、续费、购买咨询。"),
    QuestionCategory("service", "服务", "客服、老师响应、账号、群服务、资料发放。"),
    QuestionCategory("uncategorized", "未分类", "不是问题或无法归入以上分类。"),
)


def load_question_categories() -> list[QuestionCategory]:
    return list(DEFAULT_QUESTION_CATEGORIES)
