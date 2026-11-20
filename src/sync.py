#!/usr/bin/env python3
"""Sync WeRead bookshelf, notes and reading progress into a Notion database."""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

WEREAD_URL = "https://i.weread.qq.com/api/agent/gateway"
NOTION_URL = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"


def request_json(url: str, *, method: str = "GET", headers: dict[str, str] | None = None,
                 payload: dict[str, Any] | None = None) -> Any:
    body = json.dumps(payload, ensure_ascii=False).encode() if payload is not None else None
    req = urllib.request.Request(url, data=body, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=45) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")
        raise RuntimeError(f"HTTP {exc.code} from {url}: {detail[:1000]}") from exc


class WeRead:
    def __init__(self, key: str):
        self.key = key

    def call(self, api_name: str, **params: Any) -> Any:
        # Official WeRead Skills gateway. The gateway owns API version negotiation.
        result = request_json(WEREAD_URL, method="POST", headers={
            "Authorization": f"Bearer {self.key}", "Content-Type": "application/json",
        }, payload={"api_name": api_name, "skill_version": "1.0.6", **params})
        if isinstance(result, dict) and result.get("errcode", 0) not in (0, None):
            raise RuntimeError(f"WeRead {api_name}: {result.get('errmsg') or result.get('message') or result['errcode']}")
        return result

    def shelf(self) -> list[dict[str, Any]]:
        data = self.call("/shelf/sync")
        if isinstance(data, list): return data
        for key in ("books", "bookList", "items", "data"):
            if isinstance(data, dict) and isinstance(data.get(key), list): return data[key]
        raise RuntimeError("WeRead shelf response did not contain a book list; see action logs.")

    def notes(self, book_id: str) -> dict[str, Any]:
        # Highlights and personal thoughts use separate WeRead endpoints.
        highlights = self.call("/book/bookmarklist", bookId=book_id)
        reviews: list[dict[str, Any]] = []
        synckey = 0
        for _ in range(100):
            page = self.call("/review/list/mine", bookid=book_id, synckey=synckey, count=100)
            reviews.extend(page.get("reviews", []))
            if not page.get("hasMore"):
                break
            next_key = page.get("synckey")
            if next_key is None or next_key == synckey:
                break
            synckey = next_key
        return {"highlights": highlights, "reviews": reviews}

    def progress(self, book_id: str) -> Any:
        return self.call("/book/getprogress", bookId=book_id)


def notion_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "Notion-Version": NOTION_VERSION,
            "Content-Type": "application/json"}


def rich(text: str) -> list[dict[str, Any]]:
    return [{"type": "text", "text": {"content": text[:2000]}}] if text else []


def block(typ: str, content: str) -> dict[str, Any]:
    return {"object": "block", "type": typ, typ: {"rich_text": rich(content)}}


def find_page(database_id: str, token: str, book_id: str) -> dict[str, Any] | None:
    url = f"{NOTION_URL}/databases/{database_id}/query"
    body = {"filter": {"property": "WeRead ID", "rich_text": {"equals": book_id}}, "page_size": 1}
    result = request_json(url, method="POST", headers=notion_headers(token), payload=body)
    return result["results"][0] if result.get("results") else None


def write_children(page_id: str, token: str, children: list[dict[str, Any]], *, replace: bool) -> None:
    headers = notion_headers(token)
    if replace:
        url = f"{NOTION_URL}/blocks/{page_id}/children?page_size=100"
        while url:
            result = request_json(url, headers=headers)
            for child in result.get("results", []):
                request_json(f"{NOTION_URL}/blocks/{child['id']}", method="DELETE", headers=headers)
                time.sleep(0.12)
            cursor = result.get("next_cursor")
            url = f"{NOTION_URL}/blocks/{page_id}/children?page_size=100&start_cursor={urllib.parse.quote(cursor)}" if result.get("has_more") and cursor else ""
    for offset in range(0, len(children), 100):
        request_json(f"{NOTION_URL}/blocks/{page_id}/children", method="PATCH", headers=headers,
                     payload={"children": children[offset:offset + 100]})


def getv(obj: Any, *keys: str, default: str = "") -> str:
    if not isinstance(obj, dict): return default
    for key in keys:
        value = obj.get(key)
        if value is not None and not isinstance(value, (dict, list)): return str(value)
    return default


def as_iso_time(value: Any) -> str | None:
    try:
        return datetime.fromtimestamp(int(value), timezone.utc).isoformat(timespec="seconds")
    except (TypeError, ValueError, OSError, OverflowError):
        return None


def existing_date(page: dict[str, Any] | None, prop: str) -> str | None:
    if not page:
        return None
    value = page.get("properties", {}).get(prop, {}).get("date") or {}
    return value.get("start")


def content_blocks(book: dict[str, Any], notes: Any) -> list[dict[str, Any]]:
    # Reading progress is stored in the database property, not repeated in page body.
    blocks = [block("heading_2", "划线")]
    highlights = notes.get("highlights", {}).get("updated", []) if isinstance(notes, dict) else []
    chapters = notes.get("highlights", {}).get("chapters", []) if isinstance(notes, dict) else []
    chapter_names = {str(c.get("chapterUid")): c.get("title", "") for c in chapters if isinstance(c, dict)}
    for item in highlights:
        if not isinstance(item, dict):
            continue
        chapter = chapter_names.get(str(item.get("chapterUid", "")), "")
        quote = getv(item, "markText")
        line = (f"【{chapter}】\n" if chapter else "") + (f"> {quote}" if quote else "")
        if line.strip():
            blocks.append(block("quote", line[:1900]))
    reviews = notes.get("reviews", []) if isinstance(notes, dict) else []
    if reviews:
        blocks.append(block("heading_2", "想法与点评"))
    for item in reviews:
        review = item.get("review", {}) if isinstance(item, dict) else {}
        if not isinstance(review, dict):
            continue
        chapter = getv(review, "chapterName")
        quote = getv(review, "abstract")
        thought = getv(review, "content")
        parts = []
        if chapter: parts.append(f"【{chapter}】")
        if quote: parts.append(f"> {quote}")
        if thought: parts.append(thought)
        if parts:
            blocks.append(block("quote", "\n".join(parts)[:1900]))
    if not highlights and not reviews:
        blocks.append(block("paragraph", "暂无笔记与想法"))
    return blocks


def sync_book(book: dict[str, Any], database_id: str, token: str, wr: WeRead) -> None:
    book_id = getv(book, "bookId", "book_id", "id")
    title = getv(book, "title", "bookName", default=f"微信读书 {book_id}")
    if not book_id: raise RuntimeError(f"Book has no stable ID: {book}")
    notes, progress = wr.notes(book_id), wr.progress(book_id)
    existing = find_page(database_id, token, book_id)
    progress_book = progress.get("book", {}) if isinstance(progress, dict) else {}
    progress_value = progress_book.get("progress")
    cover_url = getv(book, "cover")
    properties: dict[str, Any] = {
        "title": {"title": rich(title)},
        "WeRead ID": {"rich_text": rich(book_id)},
        "作者": {"rich_text": rich(getv(book, "author"))},
        "阅读进度": {"number": (float(progress_value) / 100) if progress_value is not None else None},
        "总共阅读时长": {"number": progress_book.get("recordReadingTime", progress_book.get("readingTime"))},
        "最后阅读时间": {"date": {"start": as_iso_time(progress_book.get("updateTime"))} if as_iso_time(progress_book.get("updateTime")) else None},
        "最后同步时间": {"date": {"start": datetime.now(timezone.utc).isoformat(timespec="seconds")}},
        "封面": {"files": ([{"name": title, "type": "external", "external": {"url": cover_url}}]
                          if cover_url.startswith(("http://", "https://")) else [])},
    }
    # WeRead exposes only a boolean for whether reading has started, not the
    # historical start date. Set it once to first observed sync time; preserve thereafter.
    started = existing_date(existing, "开始阅读时间")
    if not started and progress_book.get("isStartReading"):
        started = datetime.now(timezone.utc).isoformat(timespec="seconds")
    properties["开始阅读时间"] = {"date": {"start": started} if started else None}
    props = properties
    children = content_blocks(book, notes)
    if existing:
        page_id = existing["id"]
        write_children(page_id, token, children, replace=True)
        request_json(f"{NOTION_URL}/pages/{page_id}", method="PATCH", headers=notion_headers(token),
                     payload={"properties": props})
    else:
        created = request_json(f"{NOTION_URL}/pages", method="POST", headers=notion_headers(token), payload={
            "parent": {"database_id": database_id}, "properties": props,
            "children": children[:100],
        })
        if len(children) > 100: write_children(created["id"], token, children[100:], replace=False)


def main() -> None:
    weread_key = os.environ["WEREAD_API_KEY"]
    notion_token = os.environ["NOTION_TOKEN"]
    database_id = os.environ["NOTION_DATABASE_ID"]
    wr = WeRead(weread_key)
    books = wr.shelf()
    print(f"Found {len(books)} WeRead books")
    failed = 0
    for book in books:
        try:
            sync_book(book, database_id, notion_token, wr)
            print(f"Synced {getv(book, 'title', 'bookName', 'bookId')}")
        except Exception as exc:
            failed += 1
            print(f"Failed to sync {getv(book, 'title', 'bookName', 'bookId')}: {exc}", file=sys.stderr)
        time.sleep(0.4)
    if failed: raise SystemExit(f"{failed} book(s) failed")


if __name__ == "__main__": main()
