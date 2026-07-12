#!/usr/bin/env python3
"""Fetch and extract text from a public WeChat Official Account article."""
from __future__ import annotations

import argparse
import html as html_lib
import json
import mimetypes
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

DEFAULT_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Safari/537.36 Edg/126.0.0.0"
)

BLOCK_TAGS = {
    "address", "article", "aside", "blockquote", "br", "div", "dl", "fieldset",
    "figcaption", "figure", "footer", "form", "h1", "h2", "h3", "h4", "h5", "h6",
    "header", "hr", "li", "main", "nav", "ol", "p", "pre", "section", "table", "tbody",
    "td", "tfoot", "th", "thead", "tr", "ul",
}
DROP_TAGS = {"script", "style", "svg", "canvas", "noscript", "iframe", "mp-common-profile", "mp-common-miniprogram"}
IMAGE_ATTRS = ("data-src", "data-original", "data-backsrc", "src")


def eprint(*args: object) -> None:
    print(*args, file=sys.stderr)


def looks_like_wechat_url(url: str) -> bool:
    try:
        parsed = urllib.parse.urlparse(url)
    except Exception:
        return False
    host = parsed.netloc.lower()
    return host.endswith("mp.weixin.qq.com") and (parsed.path.startswith("/s/") or parsed.path == "/s")


def decode_bytes(data: bytes, headers: Any, html_hint: bytes) -> str:
    charset = None
    try:
        charset = headers.get_content_charset()
    except Exception:
        charset = None
    if not charset:
        m = re.search(br'<meta[^>]+charset=["\']?([a-zA-Z0-9_\-]+)', html_hint[:4096], re.I)
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


def fetch(url: str, timeout: int = 25) -> tuple[str, str]:
    headers = {
        "User-Agent": DEFAULT_UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Accept-Encoding": "identity",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "Referer": "https://mp.weixin.qq.com/",
    }
    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = resp.read()
            final_url = resp.geturl()
            text = decode_bytes(data, resp.headers, data)
            return final_url, text
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")[:800]
        raise RuntimeError(f"HTTP {exc.code} fetching {url}: {body}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Network error fetching {url}: {exc}") from exc


def decode_wechat_escapes(text: str) -> str:
    """Decode common WeChat/JS-style escapes that appear inside HTML attributes."""
    text = text or ""

    def repl_x(match: re.Match[str]) -> str:
        try:
            return chr(int(match.group(1), 16))
        except Exception:
            return match.group(0)

    text = re.sub(r"\\x([0-9a-fA-F]{2})", repl_x, text)
    text = re.sub(r"\\u([0-9a-fA-F]{4})", repl_x, text)
    return html_lib.unescape(text)


def clean_inline(text: str) -> str:
    text = decode_wechat_escapes(text or "")
    text = text.replace("\u200b", "").replace("\ufeff", "")
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    return text.strip()


def clean_lines(text: str) -> str:
    lines: list[str] = []
    previous = None
    for raw in re.split(r"\n+", text or ""):
        line = clean_inline(raw)
        if not line:
            continue
        # Drop repeated adjacent UI/card artifacts while preserving repeated article quotes elsewhere.
        if line == previous and len(line) <= 40:
            continue
        lines.append(line)
        previous = line
    return "\n".join(lines).strip()


def strip_tags(fragment: str) -> str:
    class _Stripper(HTMLParser):
        def __init__(self) -> None:
            super().__init__(convert_charrefs=True)
            self.parts: list[str] = []
            self.drop_depth = 0

        def handle_starttag(self, tag: str, attrs: list[tuple[str, Optional[str]]]) -> None:
            tag = tag.lower()
            if tag in DROP_TAGS:
                self.drop_depth += 1
                return
            if self.drop_depth:
                return
            if tag in BLOCK_TAGS:
                self.parts.append("\n")

        def handle_endtag(self, tag: str) -> None:
            tag = tag.lower()
            if self.drop_depth:
                if tag in DROP_TAGS:
                    self.drop_depth -= 1
                return
            if tag in BLOCK_TAGS:
                self.parts.append("\n")

        def handle_data(self, data: str) -> None:
            if not self.drop_depth:
                self.parts.append(data)

    parser = _Stripper()
    parser.feed(fragment or "")
    return clean_lines("".join(parser.parts))


class IdTextExtractor(HTMLParser):
    def __init__(self, target_id: str) -> None:
        super().__init__(convert_charrefs=True)
        self.target_id = target_id
        self.capturing = False
        self.depth = 0
        self.drop_depth = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, Optional[str]]]) -> None:
        tag = tag.lower()
        attrs_dict = {k.lower(): v for k, v in attrs if k}
        if not self.capturing and attrs_dict.get("id") == self.target_id:
            self.capturing = True
            self.depth = 1
            if tag in BLOCK_TAGS:
                self.parts.append("\n")
            return
        if not self.capturing:
            return
        if tag in DROP_TAGS:
            self.drop_depth += 1
        if self.drop_depth:
            return
        self.depth += 1
        if tag in BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if not self.capturing:
            return
        if self.drop_depth:
            if tag in DROP_TAGS:
                self.drop_depth -= 1
            return
        if tag in BLOCK_TAGS:
            self.parts.append("\n")
        self.depth -= 1
        if self.depth <= 0:
            self.capturing = False

    def handle_data(self, data: str) -> None:
        if self.capturing and not self.drop_depth:
            self.parts.append(data)

    def text(self) -> str:
        return clean_lines("".join(self.parts))


def extract_id_text_fallback(html_text: str, target_id: str) -> str:
    parser = IdTextExtractor(target_id)
    parser.feed(html_text)
    return parser.text()


def meta_content_regex(html_text: str, key: str, attr: str = "name") -> str:
    patterns = [
        rf'<meta\b(?=[^>]*\b{attr}=["\']{re.escape(key)}["\'])(?=[^>]*\bcontent=["\']([^"\']*)["\'])[^>]*>',
        rf'<meta\b(?=[^>]*\bcontent=["\']([^"\']*)["\'])(?=[^>]*\b{attr}=["\']{re.escape(key)}["\'])[^>]*>',
    ]
    for pattern in patterns:
        m = re.search(pattern, html_text, re.I | re.S)
        if m:
            return clean_inline(m.group(1))
    return ""


def regex_first(html_text: str, patterns: Iterable[str]) -> str:
    for pattern in patterns:
        m = re.search(pattern, html_text, re.I | re.S)
        if m:
            return clean_inline(m.group(1))
    return ""


def absolutize_url(url: str, base_url: str) -> str:
    url = clean_inline(url)
    if not url:
        return ""
    if url.startswith("//"):
        return "https:" + url
    return urllib.parse.urljoin(base_url, url)


def choose_image_url(attrs: Dict[str, Any], base_url: str) -> str:
    for key in IMAGE_ATTRS:
        value = attrs.get(key)
        if value:
            return absolutize_url(str(value), base_url)
    return ""


def parse_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    m = re.search(r"\d+", str(value))
    return int(m.group(0)) if m else None


def media_item_from_attrs(attrs: Dict[str, Any], base_url: str, index: int, source: str = "img") -> Optional[Dict[str, Any]]:
    url = choose_image_url(attrs, base_url)
    if not url:
        return None
    item: Dict[str, Any] = {
        "index": index,
        "source": source,
        "url": url,
    }
    for key in ("alt", "title", "data-type", "data-ratio", "data-w", "width", "height"):
        if attrs.get(key):
            item[key.replace("-", "_")] = clean_inline(str(attrs[key]))
    width = parse_int(attrs.get("data-w") or attrs.get("width"))
    height = parse_int(attrs.get("height"))
    if width:
        item["width_px"] = width
    if height:
        item["height_px"] = height
    return item


class IdMediaExtractor(HTMLParser):
    def __init__(self, target_id: str, base_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.target_id = target_id
        self.base_url = base_url
        self.capturing = False
        self.depth = 0
        self.images: list[Dict[str, Any]] = []
        self.card_images: list[Dict[str, Any]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, Optional[str]]]) -> None:
        tag = tag.lower()
        attrs_dict = {k.lower(): v for k, v in attrs if k}
        if not self.capturing and attrs_dict.get("id") == self.target_id:
            self.capturing = True
            self.depth = 1
            return
        if not self.capturing:
            return
        self.depth += 1
        if tag == "img":
            item = media_item_from_attrs(attrs_dict, self.base_url, len(self.images) + 1, "img")
            if item:
                self.images.append(item)
        elif tag == "mp-common-miniprogram":
            url = absolutize_url(str(attrs_dict.get("data-miniprogram-imageurl") or ""), self.base_url)
            if url:
                self.card_images.append({
                    "index": len(self.card_images) + 1,
                    "source": "mp-common-miniprogram",
                    "url": url,
                    "title": clean_inline(str(attrs_dict.get("data-miniprogram-title") or "")),
                    "nickname": clean_inline(str(attrs_dict.get("data-miniprogram-nickname") or "")),
                })

    def handle_endtag(self, tag: str) -> None:
        if not self.capturing:
            return
        self.depth -= 1
        if self.depth <= 0:
            self.capturing = False


def extract_id_media_fallback(html_text: str, target_id: str, base_url: str) -> tuple[list[Dict[str, Any]], list[Dict[str, Any]]]:
    parser = IdMediaExtractor(target_id, base_url)
    parser.feed(html_text)
    return parser.images, parser.card_images


def extract_with_bs4(html_text: str, final_url: str) -> Optional[Dict[str, Any]]:
    try:
        from bs4 import BeautifulSoup  # type: ignore
    except Exception:
        return None

    soup = BeautifulSoup(html_text, "html.parser")

    def by_id(node_id: str, sep: str = " ") -> str:
        node = soup.find(id=node_id)
        return clean_inline(node.get_text(sep, strip=True)) if node else ""

    def meta(name: str, attr: str = "name") -> str:
        node = soup.find("meta", attrs={attr: name})
        return clean_inline(node.get("content", "")) if node else ""

    content_node = soup.find(id="js_content")
    content = ""
    images: list[Dict[str, Any]] = []
    card_images: list[Dict[str, Any]] = []
    if content_node:
        for img in content_node.find_all("img"):
            item = media_item_from_attrs(dict(img.attrs), final_url, len(images) + 1, "img")
            if item:
                images.append(item)
        for card in content_node.find_all("mp-common-miniprogram"):
            url = absolutize_url(str(card.get("data-miniprogram-imageurl") or ""), final_url)
            if url:
                card_images.append({
                    "index": len(card_images) + 1,
                    "source": "mp-common-miniprogram",
                    "url": url,
                    "title": clean_inline(str(card.get("data-miniprogram-title") or "")),
                    "nickname": clean_inline(str(card.get("data-miniprogram-nickname") or "")),
                })
        for selector in [
            "script", "style", "svg", "canvas", "noscript", "iframe",
            "mp-common-profile", "mp-common-miniprogram", ".mp_profile_iframe_wrp",
        ]:
            for node in content_node.select(selector):
                node.decompose()
        for node in content_node.find_all(style=re.compile(r"display\s*:\s*none", re.I)):
            node.decompose()
        for br in content_node.find_all("br"):
            br.replace_with("\n")
        content = clean_lines(content_node.get_text("\n", strip=True))

    return {
        "title": by_id("activity-name"),
        "account": by_id("js_name"),
        "author": meta("author"),
        "description": meta("description") or meta("og:description", "property"),
        "cover": meta("og:image", "property") or meta("twitter:image", "property"),
        "content": content,
        "images": images,
        "card_images": card_images,
    }


def extract(html_text: str, final_url: str) -> Dict[str, Any]:
    parsed = extract_with_bs4(html_text, final_url) or {}

    title = parsed.get("title") or extract_id_text_fallback(html_text, "activity-name")
    account = parsed.get("account") or extract_id_text_fallback(html_text, "js_name")
    content = parsed.get("content") or extract_id_text_fallback(html_text, "js_content")
    author = parsed.get("author") or meta_content_regex(html_text, "author")
    description = parsed.get("description") or meta_content_regex(html_text, "description") or meta_content_regex(html_text, "og:description", "property")
    cover = parsed.get("cover") or meta_content_regex(html_text, "og:image", "property") or meta_content_regex(html_text, "twitter:image", "property")
    images = parsed.get("images")
    card_images = parsed.get("card_images")
    if images is None or card_images is None:
        images, card_images = extract_id_media_fallback(html_text, "js_content", final_url)

    publish_time = regex_first(
        html_text,
        [
            r"var\s+createTime\s*=\s*['\"]([^'\"]+)['\"]",
            r"create_time\s*:\s*['\"]([^'\"]+)['\"]",
            r"publish_time\s*['\"]?\s*[:=]\s*['\"]([^'\"]+)['\"]",
        ],
    )
    create_timestamp = regex_first(
        html_text,
        [
            r"var\s+createTimestamp\s*=\s*['\"]([^'\"]+)['\"]",
            r"var\s+oriCreateTime\s*=\s*['\"]([^'\"]+)['\"]",
            r"ori_create_time\s*:\s*['\"]([^'\"]+)['\"]",
            r"var\s+ct\s*=\s*['\"]([^'\"]+)['\"]",
        ],
    )

    error_hint = ""
    if not content:
        for hint in ["环境异常", "访问频繁", "页面不存在", "该内容已被发布者删除", "请在微信客户端打开链接"]:
            if hint in html_text:
                error_hint = hint
                break

    return {
        "url": final_url,
        "title": title,
        "account": account,
        "author": author,
        "publish_time": publish_time,
        "create_timestamp": create_timestamp,
        "description": description,
        "cover": cover,
        "images": images or [],
        "image_count": len(images or []),
        "card_images": card_images or [],
        "card_image_count": len(card_images or []),
        "content": content,
        "char_count": len(content),
        "line_count": len(content.splitlines()) if content else 0,
        "error_hint": error_hint,
    }


def truncate_content(result: Dict[str, Any], max_chars: int) -> Dict[str, Any]:
    if max_chars and result.get("content") and len(result["content"]) > max_chars:
        cloned = dict(result)
        original_len = len(cloned["content"])
        cloned["content"] = cloned["content"][:max_chars].rstrip() + f"\n\n[已截断：原文 {original_len} 字符，仅输出前 {max_chars} 字符]"
        cloned["truncated"] = True
        return cloned
    result["truncated"] = False
    return result


def extension_from_url(url: str, content_type: str = "") -> str:
    query = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
    wx_fmt = (query.get("wx_fmt") or [""])[0].lower()
    if wx_fmt:
        if wx_fmt == "jpeg":
            return ".jpg"
        return "." + re.sub(r"[^a-z0-9]", "", wx_fmt)
    ext = Path(urllib.parse.urlparse(url).path).suffix.lower()
    if ext and len(ext) <= 6:
        return ext
    guessed = mimetypes.guess_extension(content_type.split(";")[0].strip()) if content_type else None
    if guessed == ".jpe":
        return ".jpg"
    return guessed or ".jpg"


def download_image(url: str, out_dir: Path, index: int, referer: str, timeout: int) -> Dict[str, Any]:
    headers = {
        "User-Agent": DEFAULT_UA,
        "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Referer": referer,
    }
    req = urllib.request.Request(url, headers=headers, method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = resp.read()
        content_type = resp.headers.get("content-type", "")
    ext = extension_from_url(url, content_type)
    path = out_dir / f"{index:03d}{ext}"
    path.write_bytes(data)
    return {
        "local_path": str(path),
        "bytes": len(data),
        "content_type": content_type,
    }


def download_result_images(result: Dict[str, Any], output_dir: str, timeout: int) -> None:
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    downloadable = []
    downloadable.extend(result.get("images") or [])
    downloadable.extend(result.get("card_images") or [])
    if result.get("cover"):
        downloadable.append({"source": "cover", "url": result["cover"]})
    for index, item in enumerate(downloadable, 1):
        url = item.get("url")
        if not url:
            continue
        try:
            item.update(download_image(str(url), out_dir, index, result.get("url") or "", timeout))
        except Exception as exc:
            item["download_error"] = str(exc)
    result["download_dir"] = str(out_dir)
    result["downloaded_image_count"] = sum(1 for item in downloadable if item.get("local_path"))


def as_markdown(result: Dict[str, Any]) -> str:
    title = result.get("title") or "微信公众平台文章"
    rows = [f"# {title}", ""]
    metadata = [
        ("URL", result.get("url")),
        ("公众号", result.get("account")),
        ("作者", result.get("author")),
        ("发布时间", result.get("publish_time")),
        ("创建时间戳", result.get("create_timestamp")),
        ("描述", result.get("description")),
        ("封面", result.get("cover")),
    ]
    for key, value in metadata:
        if value:
            rows.append(f"- {key}: {value}")
    rows.append(f"- 正文图片数: {result.get('image_count', 0)}")
    if result.get("card_image_count"):
        rows.append(f"- 卡片图片数: {result.get('card_image_count', 0)}")
    if result.get("download_dir"):
        rows.append(f"- 图片下载目录: {result.get('download_dir')}")
        rows.append(f"- 已下载图片数: {result.get('downloaded_image_count', 0)}")
    if result.get("images"):
        rows.extend(["", "## 正文图片", ""])
        for item in result["images"]:
            local = f" — {item['local_path']}" if item.get("local_path") else ""
            rows.append(f"{item.get('index')}. {item.get('url')}{local}")
    if result.get("card_images"):
        rows.extend(["", "## 卡片图片", ""])
        for item in result["card_images"]:
            title_part = f" ({item.get('title')})" if item.get("title") else ""
            local = f" — {item['local_path']}" if item.get("local_path") else ""
            rows.append(f"{item.get('index')}. {item.get('url')}{title_part}{local}")
    rows.extend(["", "## 正文", "", result.get("content") or ""])
    return "\n".join(rows).rstrip() + "\n"


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Fetch and extract a public WeChat Official Account article.")
    parser.add_argument("url", help="WeChat article URL, usually https://mp.weixin.qq.com/s/...")
    parser.add_argument("--format", choices=["markdown", "json", "text"], default="markdown")
    parser.add_argument("--max-chars", type=int, default=0, help="Truncate extracted content to this many chars; 0 means no truncation.")
    parser.add_argument("--timeout", type=int, default=25)
    parser.add_argument("--out", help="Optional output file path.")
    parser.add_argument("--save-html", help="Optional path to save fetched raw HTML for debugging.")
    parser.add_argument("--download-images", help="Optional directory for downloading body images, card images, and cover image.")
    parser.add_argument("--allow-non-wechat", action="store_true", help="Try fetching even if the URL is not mp.weixin.qq.com/s.")
    args = parser.parse_args(argv)

    if not looks_like_wechat_url(args.url) and not args.allow_non_wechat:
        eprint("ERROR: URL does not look like a WeChat article. Expected https://mp.weixin.qq.com/s/... .")
        return 2

    try:
        final_url, html_text = fetch(args.url, timeout=args.timeout)
    except Exception as exc:
        eprint(f"ERROR: {exc}")
        return 2

    if args.save_html:
        Path(args.save_html).write_text(html_text, encoding="utf-8")

    result = extract(html_text, final_url)
    if args.download_images:
        download_result_images(result, args.download_images, args.timeout)
    result = truncate_content(result, args.max_chars)

    if not result.get("content"):
        hint = f" Hint: {result['error_hint']}." if result.get("error_hint") else ""
        eprint(f"ERROR: Could not find article body in #js_content.{hint}")
        if args.format == "json":
            print(json.dumps(result, ensure_ascii=False, indent=2))
        return 3

    if args.format == "json":
        output = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    elif args.format == "text":
        output = result["content"].rstrip() + "\n"
    else:
        output = as_markdown(result)

    if args.out:
        Path(args.out).write_text(output, encoding="utf-8")
    else:
        sys.stdout.write(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
