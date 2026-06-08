import json
from datetime import datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
QUEUE_PATH = ROOT / "content" / "article-queue.json"
KST = timezone(timedelta(hours=9))
FIRST_PUBLISH_AT = "2026-06-08T13:23:00+09:00"


def parse_publish_at(value):
    dt = datetime.fromisoformat(value)
    return dt if dt.tzinfo else dt.replace(tzinfo=KST)


def main():
    if not QUEUE_PATH.exists():
        print(FIRST_PUBLISH_AT)
        return 0

    queue = json.loads(QUEUE_PATH.read_text(encoding="utf-8"))
    articles = queue.get("articles", queue) if isinstance(queue, dict) else queue
    articles = articles if isinstance(articles, list) else []

    published_dates = [
        parse_publish_at(article["publishAt"])
        for article in articles
        if article.get("is_published") is True and article.get("publishAt")
    ]
    if published_dates:
        print(max(published_dates).isoformat())
        return 0

    scheduled_dates = [
        parse_publish_at(article["publishAt"])
        for article in articles
        if article.get("publishAt")
    ]
    print(min(scheduled_dates).isoformat() if scheduled_dates else FIRST_PUBLISH_AT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
