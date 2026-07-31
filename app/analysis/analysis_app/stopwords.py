from __future__ import annotations

from pathlib import Path

DEFAULT_STOPWORDS: frozenset[str] = frozenset(
    {
        "我们",
        "你们",
        "他们",
        "好的",
        "好",
        "嗯",
        "嗯嗯",
        "收到",
        "了解",
        "老师",
        "同学",
        "请问",
        "麻烦",
        "谢谢",
        "辛苦",
        "一下",
        "这个",
        "那个",
        "怎么",
        "什么",
        "可以",
        "是不是",
        "就是",
        "还有",
        "然后",
        "但是",
        "因为",
        "所以",
    }
)


def load_stopwords(extra_path: str | Path | None = None) -> list[str]:
    stopwords = set(DEFAULT_STOPWORDS)
    if extra_path:
        path = Path(extra_path)
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                word = line.strip()
                if word:
                    stopwords.add(word)
    return sorted(stopwords)

