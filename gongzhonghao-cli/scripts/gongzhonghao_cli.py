#!/usr/bin/env python3
"""Search and read WeChat Official Account articles from one CLI.

Data sources:
- Search: public Sogou WeChat Search pages at weixin.sogou.com.
- Read: public mp.weixin.qq.com article pages, via the sibling
  fetch_wechat_article.py extractor.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import html as html_lib
import json
import random
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from http.cookiejar import CookieJar
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

SCRIPT_DIR = Path(__file__).resolve().parent
sys.dont_write_bytecode = True
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import fetch_wechat_article as reader  # noqa: E402

SOGOU_BASE = "https://weixin.sogou.com"
SOGOU_SEARCH_PATH = "/weixin"
CHINA_TZ = _dt.timezone(_dt.timedelta(hours=8))

USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36 Edg/126.0.0.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edg/126.0.0.0 Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
]

COOKIE_JAR = CookieJar()
OPENER = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(COOKIE_JAR))


def eprint(*args: object) -> None:
    print(*args, file=sys.stderr)


def now_china() -> _dt.datetime:
    return _dt.datetime.now(CHINA_TZ)


def random_user_agent() -> str:
    return random.choice(USER_AGENTS)


def is_sogou_url(url: str) -> bool:
    try:
        parsed = urllib.parse.urlparse(url)
    except Exception:
        return False
    return parsed.netloc.lower().endswith("weixin.sogou.com")


def is_sogou_search_url(url: str) -> bool:
    try:
        parsed = urllib.parse.urlparse(url)
    except Exception:
        return False
    return parsed.netloc.lower().endswith("weixin.sogou.com") and parsed.path == SOGOU_SEARCH_PATH


def absolute_sogou_url(url: str) -> str:
    return urllib.parse.urljoin(SOGOU_BASE, url)


def decode_bytes(data: bytes, headers: Any) -> str:
    charset = None
    try:
        charset = headers.get_content_charset()
    except Exception:
        charset = None
    if not charset:
        m = re.search(br'<meta[^>]+charset=["\']?([a-zA-Z0-9_\-]+)', data[:4096], re.I)
        if m:
            charset = m.group(1).decode("ascii", "ignore")
    for enc in [charset, "utf-8", "gb18030", "latin-1"]:
        if not enc:
            continue
        try:
            return data.decode(enc)
        except Exception:
            pass
    return data.decode("utf-8", "replace")


def fetch_text(
    url: str,
    *,
    timeout: int = 25,
    referer: str = SOGOU_BASE + "/",
    host: str = "",
    save_html: str = "",
) -> tuple[str, str, Any]:
    headers = {
        "User-Agent": random_user_agent(),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Accept-Encoding": "identity",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "Referer": referer,
    }
    if host:
        headers["Host"] = host
    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with OPENER.open(req, timeout=timeout) as resp:
            data = resp.read()
            text = decode_bytes(data, resp.headers)
            final_url = resp.geturl()
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")[:800]
        raise RuntimeError(f"HTTP {exc.code} fetching {url}: {body}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Network error fetching {url}: {exc}") from exc
    if save_html:
        Path(save_html).write_text(text, encoding="utf-8")
    return final_url, text, resp.headers


def warm_sogou_cookie(timeout: int = 10) -> None:
    """Prime Sogou cookies; failures are non-fatal."""
    urls = [
        "https://weixin.sogou.com/",
        "https://v.sogou.com/v?ie=utf8&query=&p=40030600",
    ]
    for url in urls:
        try:
            fetch_text(url, timeout=timeout, referer="https://www.sogou.com/")
            return
        except Exception:
            continue


def compact_text(text: str) -> str:
    text = html_lib.unescape(text or "")
    text = text.replace("\u200b", "").replace("\ufeff", "")
    text = re.sub(r"<!--red_beg-->|<!--red_end-->", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def strip_html(fragment: str) -> str:
    return compact_text(reader.strip_tags(fragment or ""))


def format_datetime_from_timestamp(timestamp: int) -> tuple[str, str, str]:
    dt = _dt.datetime.fromtimestamp(timestamp, CHINA_TZ)
    datetime_text = dt.strftime("%Y-%m-%d %H:%M:%S")
    date_text = dt.strftime("%Y年%m月%d日")

    diff = now_china() - dt
    seconds = int(diff.total_seconds())
    if seconds < 0:
        relative = date_text
    elif seconds < 60:
        relative = "刚刚"
    elif seconds < 3600:
        relative = f"{seconds // 60}分钟前"
    elif seconds < 86400:
        relative = f"{seconds // 3600}小时前"
    elif seconds < 30 * 86400:
        relative = f"{seconds // 86400}天前"
    else:
        relative = date_text
    return datetime_text, date_text, relative


def extract_timestamp(text: str) -> Optional[int]:
    patterns = [
        r"timeConvert\(['\"]?(\d{10})['\"]?\)",
        r"document\.write\([^)]*?(\d{10})",
        r"(\d{10})",
    ]
    for pattern in patterns:
        m = re.search(pattern, text or "")
        if m:
            try:
                return int(m.group(1))
            except Exception:
                pass
    return None


def parse_articles_with_bs4(html_text: str, max_results: int) -> list[Dict[str, Any]]:
    try:
        from bs4 import BeautifulSoup  # type: ignore
    except Exception:
        return []

    soup = BeautifulSoup(html_text, "html.parser")
    articles: list[Dict[str, Any]] = []
    for li in soup.select("ul.news-list li"):
        if len(articles) >= max_results:
            break
        title_link = li.select_one("h3 a") or li.select_one("a[data-z='art']") or li.find("a")
        if not title_link:
            continue
        title = compact_text(title_link.get_text(" ", strip=True))
        href = (title_link.get("href") or "").strip()
        if not title or not href:
            continue
        sogou_url = absolute_sogou_url(href)

        summary_node = li.select_one("p.txt-info")
        summary = compact_text(summary_node.get_text(" ", strip=True)) if summary_node else ""

        account_node = li.select_one(".s-p .all-time-y2") or li.select_one(".s-p a.account")
        account = compact_text(account_node.get_text(" ", strip=True)) if account_node else ""

        s2 = li.select_one(".s-p .s2")
        s2_text = s2.get_text(" ", strip=True) if s2 else ""
        s2_script = "".join(script.get_text("", strip=False) for script in (s2.find_all("script") if s2 else []))
        timestamp = extract_timestamp(s2_script or str(s2 or "") or s2_text)
        datetime_text = date_text = relative = ""
        if timestamp:
            datetime_text, date_text, relative = format_datetime_from_timestamp(timestamp)
        elif s2_text:
            relative = compact_text(s2_text)

        image_url = ""
        image_link = li.select_one(".img-box img")
        if image_link:
            image_url = image_link.get("src") or image_link.get("data-src") or ""
            image_url = urllib.parse.urljoin(SOGOU_BASE, image_url)

        articles.append(
            {
                "index": len(articles) + 1,
                "title": title,
                "url": sogou_url,
                "sogou_url": sogou_url,
                "url_resolved": False,
                "summary": summary,
                "account": account,
                "publish_timestamp": timestamp,
                "publish_datetime": datetime_text,
                "publish_date": date_text,
                "date_description": relative or date_text,
                "image": image_url,
            }
        )
    return articles


def iter_li_blocks(html_text: str) -> Iterable[str]:
    m = re.search(r"<ul\b[^>]*class=[\"'][^\"']*news-list[^\"']*[\"'][^>]*>(.*?)</ul>", html_text, re.I | re.S)
    if not m:
        return []
    fragment = m.group(1)
    return re.findall(r"<li\b[^>]*>.*?</li>", fragment, re.I | re.S)


def attr_value(fragment: str, attr: str) -> str:
    m = re.search(rf"\b{re.escape(attr)}=[\"']([^\"']+)[\"']", fragment, re.I)
    return html_lib.unescape(m.group(1)) if m else ""


def parse_articles_fallback(html_text: str, max_results: int) -> list[Dict[str, Any]]:
    articles: list[Dict[str, Any]] = []
    for li in iter_li_blocks(html_text):
        if len(articles) >= max_results:
            break
        link_match = re.search(r"<h3[^>]*>\s*(<a\b[^>]*>.*?</a>)\s*</h3>", li, re.I | re.S)
        if not link_match:
            link_match = re.search(r"(<a\b[^>]*data-z=[\"']art[\"'][^>]*>.*?</a>)", li, re.I | re.S)
        if not link_match:
            continue
        link_html = link_match.group(1)
        href = attr_value(link_html, "href")
        title = strip_html(link_html)
        if not href or not title:
            continue
        summary_match = re.search(r"<p\b[^>]*class=[\"'][^\"']*txt-info[^\"']*[\"'][^>]*>(.*?)</p>", li, re.I | re.S)
        summary = strip_html(summary_match.group(1)) if summary_match else ""
        account_match = re.search(r"<span\b[^>]*class=[\"'][^\"']*all-time-y2[^\"']*[\"'][^>]*>(.*?)</span>", li, re.I | re.S)
        account = strip_html(account_match.group(1)) if account_match else ""
        timestamp = extract_timestamp(li)
        datetime_text = date_text = relative = ""
        if timestamp:
            datetime_text, date_text, relative = format_datetime_from_timestamp(timestamp)
        sogou_url = absolute_sogou_url(href)
        articles.append(
            {
                "index": len(articles) + 1,
                "title": title,
                "url": sogou_url,
                "sogou_url": sogou_url,
                "url_resolved": False,
                "summary": summary,
                "account": account,
                "publish_timestamp": timestamp,
                "publish_datetime": datetime_text,
                "publish_date": date_text,
                "date_description": relative or date_text,
                "image": "",
            }
        )
    return articles


def parse_articles_from_search_html(html_text: str, max_results: int) -> list[Dict[str, Any]]:
    articles = parse_articles_with_bs4(html_text, max_results)
    if articles:
        return articles
    return parse_articles_fallback(html_text, max_results)


NON_NEWS_KEYWORDS = (
    "招聘", "实习", "岗位", "校招", "社招", "内推", "简历", "求职", "offer",
    "可远程", "兼职", "全职", "猎头", "JD", "薪资", "投递",
)


def filter_and_sort_articles(
    articles: list[Dict[str, Any]],
    *,
    news_only: bool = False,
    sort: str = "relevance",
) -> list[Dict[str, Any]]:
    result = list(articles)
    if news_only:
        filtered: list[Dict[str, Any]] = []
        for item in result:
            haystack = f"{item.get('title') or ''}\n{item.get('summary') or ''}"
            if any(keyword.lower() in haystack.lower() for keyword in NON_NEWS_KEYWORDS):
                continue
            filtered.append(item)
        result = filtered
    if sort == "recent":
        result.sort(key=lambda x: int(x.get("publish_timestamp") or 0), reverse=True)
    for index, item in enumerate(result, 1):
        item["index"] = index
    return result


def query_from_search_url(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    params = urllib.parse.parse_qs(parsed.query)
    return (params.get("query") or [""])[0]


def query_from_search_html(html_text: str) -> str:
    patterns = [
        r"var\s+oldQuery\s*=\s*['\"]([^'\"]+)['\"]",
        r"var\s+keywords_string\s*=\s*['\"]([^'\"]+)['\"]",
        r"<title>\s*(.*?)的相关微信公众号文章\s*[–-]\s*搜狗微信搜索\s*</title>",
    ]
    for pattern in patterns:
        m = re.search(pattern, html_text or "", re.I | re.S)
        if m:
            return compact_text(m.group(1))
    return ""


def build_search_url(query: str, page: int = 1, base_url: str = "") -> str:
    if base_url:
        parsed = urllib.parse.urlparse(base_url)
        params = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
        replaced: dict[str, str] = {k: v for k, v in params}
        replaced["type"] = "2"
        replaced["ie"] = replaced.get("ie") or "utf8"
        replaced["page"] = str(page)
        new_query = urllib.parse.urlencode(replaced, doseq=False)
        return urllib.parse.urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment))

    params = {
        "ie": "utf8",
        "s_from": "input",
        "_sug_": "n",
        "type": "2",
        "query": query,
        "page": str(page),
    }
    return f"{SOGOU_BASE}{SOGOU_SEARCH_PATH}?" + urllib.parse.urlencode(params)


def looks_like_antispider(html_text: str, final_url: str = "") -> bool:
    haystack = (final_url or "") + "\n" + (html_text or "")[:5000]
    return "antispider" in haystack.lower() or "请输入验证码" in haystack or "访问过于频繁" in haystack


def search_articles(
    query: str = "",
    *,
    search_url: str = "",
    html_file: str = "",
    max_results: int = 10,
    resolve_url: bool = False,
    news_only: bool = False,
    sort: str = "relevance",
    timeout: int = 25,
    save_html: str = "",
) -> Dict[str, Any]:
    max_results = max(1, min(int(max_results or 10), 50))
    source_url = search_url
    if query and is_sogou_search_url(query):
        search_url = query
        source_url = query
        query = query_from_search_url(query)
    if search_url and not query:
        query = query_from_search_url(search_url)
    if not query and not html_file:
        raise ValueError("缺少搜索关键词；传入 query，或使用 --url/--html。")

    warm_sogou_cookie(timeout=min(timeout, 10))

    articles: list[Dict[str, Any]] = []
    fetched_pages: list[str] = []
    html_text = ""
    if html_file:
        html_text = Path(html_file).read_text(encoding="utf-8", errors="replace")
        if not query:
            query = query_from_search_html(html_text)
        fetched_pages.append(f"file://{Path(html_file).resolve()}")
        articles.extend(parse_articles_from_search_html(html_text, max_results))
    else:
        pages_needed = (max_results + 9) // 10
        for page in range(1, pages_needed + 1):
            page_url = build_search_url(query, page=page, base_url=search_url if search_url else "")
            final_url, html_text, _headers = fetch_text(
                page_url,
                timeout=timeout,
                referer=SOGOU_BASE + "/",
                host="weixin.sogou.com",
                save_html=save_html if page == 1 and save_html else "",
            )
            fetched_pages.append(final_url)
            if looks_like_antispider(html_text, final_url):
                raise RuntimeError("搜狗微信返回了验证码/反爬页面；可稍后重试，或用 --html 解析浏览器保存的搜索页。")
            remaining = max_results - len(articles)
            parsed = parse_articles_from_search_html(html_text, remaining)
            if not parsed:
                break
            for item in parsed:
                item["index"] = len(articles) + 1
                articles.append(item)
            if len(articles) >= max_results:
                break
            time.sleep(0.4 + random.random() * 0.5)

    articles = filter_and_sort_articles(articles, news_only=news_only, sort=sort)[:max_results]

    if resolve_url and articles:
        for item in articles:
            resolved, ok, error = resolve_sogou_url(item["sogou_url"], timeout=timeout)
            item["url"] = resolved if ok else item["sogou_url"]
            item["url_resolved"] = ok
            if error:
                item["url_resolve_error"] = error
            time.sleep(0.25 + random.random() * 0.35)

    return {
        "query": query,
        "source": "sogou_weixin",
        "source_url": source_url or (fetched_pages[0] if fetched_pages else ""),
        "fetched_pages": fetched_pages,
        "fetched_at": now_china().strftime("%Y-%m-%d %H:%M:%S %z"),
        "total": len(articles),
        "articles": articles[:max_results],
    }


def extract_redirect_url_from_html(html_text: str) -> str:
    patterns = [
        r'<meta[^>]*http-equiv=["\']refresh["\'][^>]*content=["\']\d+\s*;\s*url=([^"\']+)["\']',
        r'location\.href\s*=\s*["\']([^"\']+)["\']',
        r'window\.location(?:\.href)?\s*=\s*["\']([^"\']+)["\']',
        r'location\.replace\(\s*["\']([^"\']+)["\']\s*\)',
        r'href=["\'](https?://mp\.weixin\.qq\.com/[^"\']+)["\']',
    ]
    for pattern in patterns:
        m = re.search(pattern, html_text or "", re.I | re.S)
        if m:
            return html_lib.unescape(m.group(1))

    parts: list[str] = []
    for m in re.finditer(r"url\s*\+=\s*['\"]([^'\"]*)['\"]", html_text or "", re.I):
        parts.append(m.group(1))
    if parts:
        joined = html_lib.unescape("".join(parts))
        if "mp.weixin.qq.com" in joined:
            return joined
    return ""


def resolve_sogou_url(url: str, *, timeout: int = 20) -> tuple[str, bool, str]:
    if not is_sogou_url(url):
        return url, reader.looks_like_wechat_url(url), ""
    original = absolute_sogou_url(url)
    try:
        final_url, html_text, _headers = fetch_text(
            original,
            timeout=timeout,
            referer=SOGOU_BASE + "/",
            host="weixin.sogou.com",
        )
        if reader.looks_like_wechat_url(final_url):
            return final_url, True, ""
        redirected = extract_redirect_url_from_html(html_text)
        if redirected:
            redirected = urllib.parse.urljoin(original, redirected)
            return redirected, reader.looks_like_wechat_url(redirected), "" if reader.looks_like_wechat_url(redirected) else "resolved URL is not a WeChat article"
        if looks_like_antispider(html_text, final_url):
            return original, False, "Sogou antispider/captcha"
        return original, False, "no mp.weixin.qq.com redirect found"
    except Exception as exc:
        return original, False, str(exc)


def read_article(
    url: str,
    *,
    resolve_sogou: bool = True,
    timeout: int = 25,
    max_chars: int = 0,
    save_html: str = "",
    download_images: str = "",
    max_images: int = 30,
    allow_non_wechat: bool = False,
) -> Dict[str, Any]:
    original_url = url
    resolved = url
    resolved_ok = False
    resolve_error = ""
    if resolve_sogou and is_sogou_url(url):
        resolved, resolved_ok, resolve_error = resolve_sogou_url(url, timeout=timeout)
    else:
        resolved_ok = reader.looks_like_wechat_url(url)

    if not reader.looks_like_wechat_url(resolved) and not allow_non_wechat:
        msg = "URL does not look like a WeChat article after resolution."
        if resolve_error:
            msg += f" resolve_error={resolve_error}"
        raise ValueError(msg)

    final_url, html_text = reader.fetch(resolved, timeout=timeout)
    if save_html:
        Path(save_html).write_text(html_text, encoding="utf-8")
    result = reader.extract(html_text, final_url)
    result["input_url"] = original_url
    result["resolved_url"] = resolved
    result["sogou_url_resolved"] = resolved_ok
    if resolve_error:
        result["url_resolve_error"] = resolve_error
    if download_images:
        max_images = max(0, int(max_images or 0))
        original_image_count = len(result.get("images") or [])
        original_card_image_count = len(result.get("card_images") or [])
        original_has_cover = 1 if result.get("cover") else 0
        remaining = max_images
        if remaining <= 0:
            result["download_skipped"] = "max_images=0"
        else:
            kept_images = (result.get("images") or [])[:remaining]
            remaining -= len(kept_images)
            kept_card_images = (result.get("card_images") or [])[:remaining]
            remaining -= len(kept_card_images)
            if remaining <= 0:
                result["cover_download_skipped"] = bool(result.get("cover"))
                result["cover"] = ""
            result["images"] = kept_images
            result["card_images"] = kept_card_images
            result["image_count"] = len(kept_images)
            result["card_image_count"] = len(kept_card_images)
            result["download_limit"] = max_images
            result["download_candidates_original"] = original_image_count + original_card_image_count + original_has_cover
            result["download_candidates_kept"] = len(kept_images) + len(kept_card_images) + (1 if result.get("cover") else 0)
        reader.download_result_images(result, download_images, timeout)
    result = reader.truncate_content(result, max_chars)
    if not result.get("content"):
        hint = f" Hint: {result['error_hint']}." if result.get("error_hint") else ""
        raise RuntimeError(f"Could not find article body in #js_content.{hint}")
    return result


def search_and_read(
    query: str = "",
    *,
    search_url: str = "",
    html_file: str = "",
    max_results: int = 5,
    read_limit: int = 3,
    news_only: bool = False,
    sort: str = "recent",
    timeout: int = 25,
    max_chars: int = 0,
    download_images: str = "",
    max_images: int = 30,
) -> Dict[str, Any]:
    search = search_articles(
        query,
        search_url=search_url,
        html_file=html_file,
        max_results=max_results,
        resolve_url=True,
        news_only=news_only,
        sort=sort,
        timeout=timeout,
    )
    read_limit = max(1, min(read_limit, len(search["articles"])))
    enriched: list[Dict[str, Any]] = []
    for item in search["articles"][:read_limit]:
        article = dict(item)
        url = item.get("url") or item.get("sogou_url")
        try:
            image_dir = ""
            if download_images:
                image_dir = str(Path(download_images) / f"{item.get('index', len(enriched) + 1):02d}")
            article["article"] = read_article(
                str(url),
                resolve_sogou=True,
                timeout=timeout,
                max_chars=max_chars,
                download_images=image_dir,
                max_images=max_images,
            )
            article["read_ok"] = True
        except Exception as exc:
            article["read_ok"] = False
            article["read_error"] = str(exc)
        enriched.append(article)
        time.sleep(0.4 + random.random() * 0.5)
    search["read_total"] = len(enriched)
    search["read_articles"] = enriched
    return search


def write_output(text: str, out: str = "") -> None:
    if out:
        Path(out).write_text(text, encoding="utf-8")
        eprint(f"已保存: {out}")
    else:
        sys.stdout.write(text)


def search_as_markdown(result: Dict[str, Any]) -> str:
    query = result.get("query") or "公众号文章"
    rows = [f"# 公众号文章搜索：{query}", ""]
    if result.get("source_url"):
        rows.append(f"- 来源: {result['source_url']}")
    rows.append(f"- 抓取时间: {result.get('fetched_at', '')}")
    rows.append(f"- 结果数: {result.get('total', 0)}")
    rows.append("")
    for item in result.get("articles") or []:
        idx = item.get("index")
        title = item.get("title") or "(无标题)"
        account = item.get("account") or "未知公众号"
        date = item.get("publish_datetime") or item.get("date_description") or ""
        rows.append(f"## {idx}. {title}")
        rows.append(f"- 公众号: {account}")
        if date:
            rows.append(f"- 时间: {date}")
        if item.get("summary"):
            rows.append(f"- 摘要: {item['summary']}")
        rows.append(f"- 链接: {item.get('url') or item.get('sogou_url')}")
        if item.get("sogou_url") and item.get("url") != item.get("sogou_url"):
            rows.append(f"- 搜狗链接: {item.get('sogou_url')}")
        if item.get("url_resolve_error"):
            rows.append(f"- 链接解析: {item.get('url_resolve_error')}")
        rows.append("")
    return "\n".join(rows).rstrip() + "\n"


def search_read_as_markdown(result: Dict[str, Any]) -> str:
    rows = [search_as_markdown(result).rstrip(), "", "# 已读取正文", ""]
    for item in result.get("read_articles") or []:
        idx = item.get("index")
        title = item.get("title") or "(无标题)"
        rows.append(f"## {idx}. {title}")
        if not item.get("read_ok"):
            rows.append(f"- 读取失败: {item.get('read_error')}")
            rows.append("")
            continue
        article = item.get("article") or {}
        rows.append(f"- URL: {article.get('url')}")
        rows.append(f"- 公众号: {article.get('account') or item.get('account') or ''}")
        if article.get("publish_time") or article.get("create_timestamp"):
            rows.append(f"- 发布时间: {article.get('publish_time') or article.get('create_timestamp')}")
        rows.append("")
        rows.append(article.get("content") or "")
        rows.append("")
    return "\n".join(rows).rstrip() + "\n"


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    argv = list(sys.argv[1:] if argv is None else argv)
    commands = {"search", "read", "search-read"}
    if argv and argv[0] not in commands and argv[0] not in {"-h", "--help"}:
        first = argv[0]
        if first.startswith("-"):
            argv = ["search"] + argv
        elif reader.looks_like_wechat_url(first) or is_sogou_url(first):
            argv = ["read"] + argv
        else:
            argv = ["search"] + argv

    parser = argparse.ArgumentParser(
        description="公众号 CLI：用搜狗微信搜索公众号文章，并读取 mp.weixin.qq.com 正文。"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_search = sub.add_parser("search", help="按关键词或搜狗搜索页 URL 搜索公众号文章")
    p_search.add_argument("query", nargs="?", help="搜索关键词；也可直接传 weixin.sogou.com/weixin 搜索页 URL")
    p_search.add_argument("--url", help="搜狗微信搜索页 URL（例如 Edge 当前打开的页面）")
    p_search.add_argument("--html", help="已保存的搜狗搜索结果 HTML 文件")
    p_search.add_argument("-n", "--num", type=int, default=10, help="返回数量，1-50，默认 10")
    p_search.add_argument("-r", "--resolve-url", action="store_true", help="尝试解析为 mp.weixin.qq.com 直链")
    p_search.add_argument("--sort", choices=["relevance", "recent"], default="relevance", help="排序方式：相关度或发布时间倒序")
    p_search.add_argument("--news-only", action="store_true", help="过滤招聘/实习/岗位等非新闻型结果")
    p_search.add_argument("--timeout", type=int, default=25)
    p_search.add_argument("--save-html", help="保存第一页搜索 HTML 便于调试")
    p_search.add_argument("--format", choices=["markdown", "json"], default="markdown")
    p_search.add_argument("-o", "--out", help="输出文件")

    p_read = sub.add_parser("read", help="读取微信文章正文，支持 mp.weixin.qq.com 或搜狗跳转链接")
    p_read.add_argument("url", help="文章 URL")
    p_read.add_argument("--no-resolve-sogou", action="store_true", help="不要解析搜狗跳转链接")
    p_read.add_argument("--timeout", type=int, default=25)
    p_read.add_argument("--max-chars", type=int, default=0, help="正文最大字符数；0 表示不截断")
    p_read.add_argument("--save-html", help="保存文章 HTML 便于调试")
    p_read.add_argument("--download-images", help="下载正文图片、卡片图和封面到目录")
    p_read.add_argument("--max-images", type=int, default=30, help="下载图片上限，默认 30；0 表示不下载")
    p_read.add_argument("--allow-non-wechat", action="store_true")
    p_read.add_argument("--format", choices=["markdown", "json", "text"], default="markdown")
    p_read.add_argument("-o", "--out", help="输出文件")

    p_sr = sub.add_parser("search-read", help="先搜索，再读取前 N 篇可解析正文")
    p_sr.add_argument("query", nargs="?", help="搜索关键词；也可直接传 weixin.sogou.com/weixin 搜索页 URL")
    p_sr.add_argument("--url", help="搜狗微信搜索页 URL")
    p_sr.add_argument("--html", help="已保存的搜狗搜索结果 HTML 文件")
    p_sr.add_argument("-n", "--num", type=int, default=5, help="搜索返回数量，默认 5")
    p_sr.add_argument("--read-limit", type=int, default=3, help="读取前几篇正文，默认 3")
    p_sr.add_argument("--sort", choices=["relevance", "recent"], default="recent", help="排序方式：默认按发布时间倒序")
    p_sr.add_argument("--news-only", action="store_true", help="过滤招聘/实习/岗位等非新闻型结果")
    p_sr.add_argument("--timeout", type=int, default=25)
    p_sr.add_argument("--max-chars", type=int, default=6000)
    p_sr.add_argument("--download-images", help="下载图片到目录；每篇文章一个子目录")
    p_sr.add_argument("--max-images", type=int, default=30, help="每篇文章下载图片上限，默认 30；0 表示不下载")
    p_sr.add_argument("--format", choices=["markdown", "json"], default="markdown")
    p_sr.add_argument("-o", "--out", help="输出文件")
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    args = parse_args(argv)
    try:
        if args.command == "search":
            result = search_articles(
                args.query or "",
                search_url=args.url or "",
                html_file=args.html or "",
                max_results=args.num,
                resolve_url=args.resolve_url,
                news_only=args.news_only,
                sort=args.sort,
                timeout=args.timeout,
                save_html=args.save_html or "",
            )
            output = json.dumps(result, ensure_ascii=False, indent=2) + "\n" if args.format == "json" else search_as_markdown(result)
            write_output(output, args.out or "")
            return 0

        if args.command == "read":
            result = read_article(
                args.url,
                resolve_sogou=not args.no_resolve_sogou,
                timeout=args.timeout,
                max_chars=args.max_chars,
                save_html=args.save_html or "",
                download_images=args.download_images or "",
                max_images=args.max_images,
                allow_non_wechat=args.allow_non_wechat,
            )
            if args.format == "json":
                output = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
            elif args.format == "text":
                output = (result.get("content") or "").rstrip() + "\n"
            else:
                output = reader.as_markdown(result)
            write_output(output, args.out or "")
            return 0

        if args.command == "search-read":
            result = search_and_read(
                args.query or "",
                search_url=args.url or "",
                html_file=args.html or "",
                max_results=args.num,
                read_limit=args.read_limit,
                news_only=args.news_only,
                sort=args.sort,
                timeout=args.timeout,
                max_chars=args.max_chars,
                download_images=args.download_images or "",
                max_images=args.max_images,
            )
            output = json.dumps(result, ensure_ascii=False, indent=2) + "\n" if args.format == "json" else search_read_as_markdown(result)
            write_output(output, args.out or "")
            return 0

        raise ValueError(f"Unknown command: {args.command}")
    except Exception as exc:
        eprint(f"ERROR: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
