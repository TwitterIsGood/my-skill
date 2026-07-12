#!/usr/bin/env python3
"""Fast linux.do topic fetcher using Edge cookies + Discourse JSON."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import shutil
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
from html.parser import HTMLParser
from pathlib import Path
from typing import Any


EDGE_COOKIE_DB = (
    Path.home()
    / "Library/Application Support/Microsoft Edge/Default/Cookies"
)
CHROME_COOKIE_DB = (
    Path.home()
    / "Library/Application Support/Google/Chrome/Default/Cookies"
)
UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 "
    "Safari/537.36 Edg/137.0.0.0"
)

CookieRows = list[tuple[str, bool, str, bool, bool, int, str, str]]


class SimpleHTMLText(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.href_stack: list[str | None] = []
        self.skip = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_d = dict(attrs)
        if tag in {"script", "style", "svg"}:
            self.skip += 1
            return
        if tag in {"p", "div", "li", "h1", "h2", "h3", "h4", "blockquote", "pre", "br", "hr"}:
            self.parts.append("\n")
        if tag == "a":
            self.href_stack.append(attrs_d.get("href"))
        if tag == "img":
            src = attrs_d.get("src")
            alt = attrs_d.get("alt") or "image"
            if src:
                self.parts.append(f"\n[{alt}: {src}]\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "svg"} and self.skip:
            self.skip -= 1
            return
        if tag == "a" and self.href_stack:
            href = self.href_stack.pop()
            if href:
                self.parts.append(f" ({href})")
        if tag in {"p", "div", "li", "h1", "h2", "h3", "h4", "blockquote", "pre", "hr"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self.skip:
            self.parts.append(data)

    def text(self) -> str:
        raw = html.unescape("".join(self.parts))
        lines = [re.sub(r"[ \t]+", " ", x).strip() for x in raw.splitlines()]
        out: list[str] = []
        for line in lines:
            if line or (out and out[-1]):
                out.append(line)
        return "\n".join(out).strip()


def html_to_text(cooked: str) -> str:
    try:
        from bs4 import BeautifulSoup  # type: ignore

        soup = BeautifulSoup(cooked, "html.parser")
        for tag in soup(["script", "style", "svg"]):
            tag.decompose()
        for img in soup.find_all("img"):
            src = img.get("src")
            alt = img.get("alt") or "image"
            img.replace_with(f"\n[{alt}: {src}]\n" if src else "")
        text = soup.get_text("\n", strip=True)
        return re.sub(r"\n{3,}", "\n\n", text)
    except Exception:
        parser = SimpleHTMLText()
        parser.feed(cooked)
        return parser.text()


def topic_and_post(url: str) -> tuple[str, int | None]:
    m = re.search(r"/t/(?:[^/?#]+/)?(\d+)(?:/(\d+))?", url)
    if not m:
        raise SystemExit(f"Cannot find topic id in URL: {url}")
    topic_id = m.group(1)
    post_no = int(m.group(2)) if m.group(2) else None
    return topic_id, post_no


def proxy_url(mode: str) -> str | None:
    if mode == "none":
        return None
    if mode != "auto":
        return mode
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.25)
        try:
            s.connect(("127.0.0.1", 7890))
            return "http://127.0.0.1:7890"
        except OSError:
            return None


def keychain_password(browser: str) -> bytes:
    service = "Microsoft Edge Safe Storage" if browser == "edge" else "Chrome Safe Storage"
    try:
        return subprocess.check_output(
            ["security", "find-generic-password", "-w", "-s", service],
            stderr=subprocess.DEVNULL,
        ).strip()
    except subprocess.CalledProcessError as exc:
        raise SystemExit(f"Cannot read macOS Keychain item: {service}") from exc


def decrypt_chromium_cookie(host: str, encrypted: bytes, browser: str) -> str:
    if not encrypted:
        return ""
    if not encrypted.startswith(b"v10"):
        return encrypted.decode("utf-8", "replace")
    try:
        from cryptography.hazmat.backends import default_backend
        from cryptography.hazmat.primitives import hashes, padding
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    except Exception as exc:
        raise SystemExit("Missing Python package: cryptography") from exc

    password = keychain_password(browser)
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA1(),
        length=16,
        salt=b"saltysalt",
        iterations=1003,
        backend=default_backend(),
    )
    key = kdf.derive(password)
    cipher = Cipher(algorithms.AES(key), modes.CBC(b" " * 16), backend=default_backend())
    decryptor = cipher.decryptor()
    padded = decryptor.update(encrypted[3:]) + decryptor.finalize()
    unpadder = padding.PKCS7(128).unpadder()
    plain = unpadder.update(padded) + unpadder.finalize()
    host_hash = hashlib.sha256(host.encode()).digest()
    if plain.startswith(host_hash):
        plain = plain[32:]
    return plain.decode("utf-8", "replace")


def chrome_expiry_to_unix(expires_utc: int) -> int:
    if not expires_utc:
        return 0
    return int(expires_utc / 1_000_000 - 11644473600)


def load_linuxdo_cookies(cookie_db: Path, browser: str) -> CookieRows:
    if not cookie_db.exists():
        raise SystemExit(f"Cookie DB not found: {cookie_db}")
    tmp_dir = Path(tempfile.mkdtemp(prefix="linuxdo-cookies-"))
    tmp_db = tmp_dir / "Cookies.sqlite"
    try:
        shutil.copy2(cookie_db, tmp_db)
        con = sqlite3.connect(tmp_db)
        rows = con.execute(
            """
            select host_key, name, value, encrypted_value, expires_utc, path, is_secure, is_httponly
            from cookies
            where host_key like '%linux.do%'
            order by host_key, name
            """
        ).fetchall()
        now = int(time.time())
        out: CookieRows = []
        for host, name, value, encrypted, expires_utc, path, is_secure, is_httponly in rows:
            exp = chrome_expiry_to_unix(int(expires_utc or 0))
            if exp and exp < now:
                continue
            val = value or decrypt_chromium_cookie(host, encrypted, browser)
            if val and val != "deleted":
                include_subdomains = host.startswith(".")
                out.append((
                    host,
                    include_subdomains,
                    path or "/",
                    bool(is_secure),
                    bool(is_httponly),
                    exp,
                    name,
                    val,
                ))
        if not out:
            raise SystemExit("No usable linux.do cookies found in browser profile")
        return out
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def write_cookiejar(cookies: CookieRows, path: Path) -> None:
    lines = ["# Netscape HTTP Cookie File"]
    for host, include_subdomains, cookie_path, secure, httponly, exp, name, value in cookies:
        jar_host = f"#HttpOnly_{host}" if httponly else host
        lines.append(
            "\t".join(
                [
                    jar_host,
                    "TRUE" if include_subdomains else "FALSE",
                    cookie_path,
                    "TRUE" if secure else "FALSE",
                    str(exp),
                    name,
                    value,
                ]
            )
        )
    path.write_text("\n".join(lines) + "\n")
    path.chmod(0o600)


def fetch_json(url: str, cookies: CookieRows, proxy: str | None, timeout: float) -> dict[str, Any]:
    tmp_dir = Path(tempfile.mkdtemp(prefix="linuxdo-fetch-"))
    jar = tmp_dir / "cookies.txt"
    try:
        write_cookiejar(cookies, jar)
        cmd = [
            "curl",
            "-L",
            "--compressed",
            "--max-time",
            str(timeout),
            "-sS",
            "-w",
            "\n__HTTP_CODE__:%{http_code}\n__CONTENT_TYPE__:%{content_type}\n",
            "-b",
            str(jar),
            "-A",
            UA,
            "-H",
            "Accept: application/json, text/javascript, */*; q=0.01",
            "-H",
            "X-Requested-With: XMLHttpRequest",
        ]
        if proxy:
            cmd.extend(["-x", proxy])
        cmd.append(url)
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=False)
        stdout = proc.stdout.decode("utf-8", "replace")
        stderr = proc.stderr.decode("utf-8", "replace")
        m_code = re.search(r"\n__HTTP_CODE__:(\d+)\n", stdout)
        m_type = re.search(r"\n__CONTENT_TYPE__:(.*?)\n", stdout)
        code = int(m_code.group(1)) if m_code else 0
        ctype = m_type.group(1).strip() if m_type else ""
        body = re.sub(r"\n__HTTP_CODE__:\d+\n__CONTENT_TYPE__:.*?\n$", "", stdout, flags=re.S)
        if proc.returncode != 0:
            raise SystemExit(f"curl failed ({proc.returncode}) for {url}: {stderr[:240]}")
        if code != 200:
            raise SystemExit(f"HTTP {code} from {url}: {body[:240]}")
        if "json" not in ctype.lower():
            raise SystemExit(f"Expected JSON, got {ctype} from {url}: {body[:240]}")
        return json.loads(body)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def post_page(post_no: int) -> int:
    return max(1, ((post_no - 1) // 20) + 1)


def render_topic(data: dict[str, Any], selected_post: int | None) -> str:
    posts = data.get("post_stream", {}).get("posts", [])
    if not posts:
        raise SystemExit("Topic JSON contained no posts")
    post = None
    if selected_post is not None:
        for item in posts:
            if item.get("post_number") == selected_post:
                post = item
                break
        if post is None:
            loaded = [str(p.get("post_number")) for p in posts[:3]]
            raise SystemExit(f"Post #{selected_post} not loaded; loaded starts with: {', '.join(loaded)}")
    else:
        post = posts[0]

    text = html_to_text(post.get("cooked") or "")
    lines = [
        f"TITLE: {data.get('title', '')}",
        f"TOPIC_ID: {data.get('id', '')}",
        f"POSTS_COUNT: {data.get('posts_count', '')}",
        f"POST: #{post.get('post_number')} by {post.get('username')} at {post.get('created_at')}",
        "",
        text,
    ]
    return "\n".join(lines).strip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch linux.do Discourse topics quickly.")
    parser.add_argument("url", help="linux.do topic URL")
    parser.add_argument("--post", type=int, help="specific post_number to extract")
    parser.add_argument("--page", type=int, help="Discourse page to fetch")
    parser.add_argument("--json", action="store_true", help="print raw JSON")
    parser.add_argument("--proxy", default="auto", help="'auto', 'none', or proxy URL")
    parser.add_argument("--browser", choices=["edge", "chrome"], default="edge")
    parser.add_argument("--cookie-db", type=Path, help="override browser Cookies sqlite path")
    parser.add_argument("--timeout", type=float, default=8.0)
    args = parser.parse_args()

    topic_id, url_post = topic_and_post(args.url)
    selected_post = args.post or url_post
    page = args.page or (post_page(selected_post) if selected_post else None)
    endpoint = f"https://linux.do/t/topic/{topic_id}.json"
    if page:
        endpoint += f"?page={page}"

    cookie_db = args.cookie_db or (EDGE_COOKIE_DB if args.browser == "edge" else CHROME_COOKIE_DB)
    cookies = load_linuxdo_cookies(cookie_db, args.browser)
    proxy = proxy_url(args.proxy)
    data = fetch_json(endpoint, cookies, proxy, args.timeout)
    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        print(render_topic(data, selected_post))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
