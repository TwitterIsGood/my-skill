---
name: gongzhonghao-cli
description: "Search, read, extract, summarize, and analyze WeChat Official Account public articles from one local CLI. Use for any 公众号/微信公众号/微信文章/mp.weixin.qq.com task: reading a supplied article URL, extracting full text/metadata/images, summarizing观点/方法论/下一步, keyword search via Sogou WeChat Search, parsing a weixin.sogou.com results URL, resolving Sogou redirects, or searching then reading selected results."
---

# 公众号 CLI

## Quick Start

Use the unified CLI first for all 公众号 work:

```bash
python3 <skill-dir>/scripts/gongzhonghao_cli.py search "关键词" -n 10 --format markdown
python3 <skill-dir>/scripts/gongzhonghao_cli.py read "https://mp.weixin.qq.com/s/..." --format markdown
python3 <skill-dir>/scripts/gongzhonghao_cli.py search-read "关键词" -n 5 --read-limit 3 --format markdown
```

`<skill-dir>` is this skill folder. The CLI has no required API key. It uses public Sogou WeChat Search for discovery and `mp.weixin.qq.com` public pages for reading.

## Workflow

1. If the user asks to 搜/找/检索公众号文章, run `search`.
2. If the user gives a `weixin.sogou.com/weixin?...type=2&query=...` page URL, pass it with `search --url '<url>'` to parse the same Sogou result page they opened in Edge/browser.
3. If the user gives an article URL (`mp.weixin.qq.com/s/...`) or a Sogou `/link?...` result URL, run `read`.
4. If the user asks to 搜并总结/读前几篇/整理主题资料, run `search-read` with a small `--read-limit` first, then summarize from extracted article bodies.
5. Base answers on CLI output fields/content, not on snippets alone. For summaries, include source article URLs.
6. If extraction fails, report the exact error and try one narrow fallback: fetch the supplied article URL directly with a browser-like user agent. If `#js_content` remains unavailable, ask for the article text or another accessible link.

## Commands

### Search articles

```bash
python3 <skill-dir>/scripts/gongzhonghao_cli.py search "美团keeta" -n 10 --format markdown
python3 <skill-dir>/scripts/gongzhonghao_cli.py search --url "https://weixin.sogou.com/weixin?...query=..." -n 10 --format json
python3 <skill-dir>/scripts/gongzhonghao_cli.py search "美团keeta" -n 10 --resolve-url --format json
```

Useful flags:

- `-n, --num`: result count, 1-50.
- `-r, --resolve-url`: attempt to resolve Sogou redirect links to `mp.weixin.qq.com` direct article URLs.
- `--sort recent`: sort parsed results by publish time descending. Use for 最近/最新 requests.
- `--news-only`: filter recruiting/internship/job posts when the user asks for 新闻/动态.
- `--html <file>`: parse a saved Sogou search HTML file if live Sogou returns a captcha/anti-bot page.
- `--save-html <file>`: save the fetched search page for debugging.
- `--format markdown|json`, `-o <file>`.

### Read one article

```bash
python3 <skill-dir>/scripts/gongzhonghao_cli.py read "https://mp.weixin.qq.com/s/..." --format markdown
python3 <skill-dir>/scripts/gongzhonghao_cli.py read "https://weixin.sogou.com/link?..." --format json
python3 <skill-dir>/scripts/gongzhonghao_cli.py read "https://mp.weixin.qq.com/s/..." --download-images /tmp/wechat-images --format json
```

`read` accepts direct WeChat article URLs and Sogou result redirect URLs. It returns title, account, author, publish/create time, description, cover, body images, card images, full text, and counts.

### Search then read

```bash
python3 <skill-dir>/scripts/gongzhonghao_cli.py search-read "美团keeta" -n 5 --read-limit 3 --max-chars 6000 --format markdown
```

Use this when the user wants a research brief or asks to summarize search results. Keep `--read-limit` modest because Sogou redirect resolution can be rate-limited.

## Output Guidance

- For summaries, analysis, explanations, comparisons, and recommendations after fetching articles, read and apply `references/talk-normal-output.md` before writing the final answer. This injects talk-normal style into 公众号 article work: direct, natural, no filler, and no canned AI phrasing.
- Preserve source fidelity. When the user asks for raw full text, quotes, titles, metadata, URLs, or extracted fields, do not rewrite those source materials; apply talk-normal only to your surrounding explanation or analysis.
- For search-only tasks, present title, account, time, summary, and URL.
- For read/summarize tasks, use extracted `content` from `read` or `search-read`, not just search summaries.
- Match the response structure to the request. For general article analysis, prefer `核心观点`, `正确做法/方法论`, `下一步行动`, and relevant caveats. Do not force this template onto raw extraction, metadata-only, or narrowly scoped questions.
- Do not paste the full article unless the user explicitly asks for 全文/原文. When full text is requested, preserve the extracted wording rather than rewriting it.
- When the user asks for 正文图片/配图/封面/图片素材, inspect `images`, `card_images`, and `cover`; use `--download-images` only when local files are useful or explicitly requested.
- If Sogou URL resolution fails, keep the Sogou URL and mention `url_resolve_error`; the user can open it in a browser or provide the final `mp.weixin.qq.com` URL.
- If live search is blocked by captcha/anti-bot, do not silently switch to generic web/news search for 公众号-only requests. Ask the user for the current Sogou WeChat search URL or a saved HTML file, then use `search --url` or `search --html`.

## Disk Safety

- Default to stdout. Do not use `-o`, `--save-html`, or `--download-images` unless the user explicitly asks to save/export/debug/download media.
- For routine search/read/summarize tasks, keep results in the response only; avoid creating persistent files in `work/`.
- If files are needed temporarily, put them under the current thread `work/` folder and delete them after use unless the user wants an artifact.
- Never run broad crawling loops. Keep `-n` at the requested count, and keep `--read-limit` small.
- `--download-images` is opt-in and capped by `--max-images` default 30 per article; use `--max-images 0` when no media is needed.

## Legacy extractor

`scripts/fetch_wechat_article.py` is retained for low-level direct extraction. Prefer `scripts/gongzhonghao_cli.py` unless you only need the old direct article fetch behavior.
