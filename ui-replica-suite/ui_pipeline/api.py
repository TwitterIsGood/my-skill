from __future__ import annotations

import base64
import http.client
import json
import mimetypes
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from .config import Settings


class RelayError(RuntimeError):
    pass


def image_data_url(path: str | Path) -> str:
    file_path = Path(path)
    mime = mimetypes.guess_type(file_path.name)[0] or "image/png"
    encoded = base64.b64encode(file_path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def extract_json(text: str) -> Any:
    """Extract a JSON object/array from plain or fenced model output."""
    candidate = text.strip()
    if candidate.startswith("```"):
        lines = candidate.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        candidate = "\n".join(lines).strip()
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        pass
    starts = [(candidate.find("{"), "{"), (candidate.find("["), "[")]
    starts = [(pos, char) for pos, char in starts if pos >= 0]
    for start, opening in sorted(starts):
        closing = "}" if opening == "{" else "]"
        depth = 0
        in_string = False
        escaped = False
        for index in range(start, len(candidate)):
            char = candidate[index]
            if in_string:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    in_string = False
                continue
            if char == '"':
                in_string = True
            elif char == opening:
                depth += 1
            elif char == closing:
                depth -= 1
                if depth == 0:
                    return json.loads(candidate[start : index + 1])
    raise ValueError("model response did not contain valid JSON")


class OpenAICompatibleClient:
    def __init__(self, settings: Settings):
        self.settings = settings
        handlers: list[Any] = []
        if settings.proxy:
            handlers.append(urllib.request.ProxyHandler({"http": settings.proxy, "https": settings.proxy}))
        self.opener = urllib.request.build_opener(*handlers)

    def _request(self, method: str, endpoint: str, payload: dict[str, Any] | None = None) -> Any:
        url = f"{self.settings.base_url}/{endpoint.lstrip('/')}"
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        headers = {"Authorization": f"Bearer {self.settings.api_key}", "Accept": "application/json"}
        if body is not None:
            headers["Content-Type"] = "application/json"
        last_error: Exception | None = None
        for attempt in range(self.settings.max_retries + 1):
            try:
                request = urllib.request.Request(url, data=body, headers=headers, method=method)
                with self.opener.open(request, timeout=self.settings.timeout) as response:
                    raw = response.read()
                return json.loads(raw.decode("utf-8"))
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode("utf-8", errors="replace")
                last_error = RelayError(f"{method} {url} returned HTTP {exc.code}: {detail[:2000]}")
                if exc.code < 500 and exc.code != 429:
                    break
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, http.client.RemoteDisconnected, ConnectionResetError) as exc:
                last_error = exc
            if attempt < self.settings.max_retries:
                time.sleep(min(2**attempt, 4))
        raise RelayError(str(last_error or f"request failed: {url}"))

    def list_models(self) -> Any:
        return self._request("GET", "models")

    def chat(
        self,
        prompt: str,
        *,
        model: str | None = None,
        images: list[str | Path] | None = None,
        temperature: float = 0.1,
        max_tokens: int = 8192,
        reasoning_effort: str | None = None,
    ) -> str:
        content: str | list[dict[str, Any]]
        if images:
            content = [{"type": "text", "text": prompt}]
            for image in images:
                content.append({"type": "image_url", "image_url": {"url": image_data_url(image)}})
        else:
            content = prompt
        payload: dict[str, Any] = {
            "model": model or self.settings.ui_model,
            "messages": [{"role": "user", "content": content}],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        effective_effort = reasoning_effort if reasoning_effort is not None else self.settings.reasoning_effort
        if effective_effort:
            payload["reasoning_effort"] = effective_effort
        response = self._request("POST", "chat/completions", payload)
        try:
            result = response["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise RelayError(f"unexpected chat response: {json.dumps(response)[:2000]}") from exc
        if isinstance(result, list):
            return "\n".join(str(item.get("text", "")) for item in result if isinstance(item, dict))
        return str(result)

    def generate_image(
        self,
        prompt: str,
        output: str | Path,
        *,
        model: str | None = None,
        size: str = "1536x1024",
        background: str | None = None,
    ) -> Path:
        payload: dict[str, Any] = {"model": model or self.settings.image_model, "prompt": prompt, "n": 1, "size": size}
        if background:
            payload["background"] = background
        response = self._request("POST", "images/generations", payload)
        try:
            item = response["data"][0]
        except (KeyError, IndexError, TypeError) as exc:
            raise RelayError(f"unexpected image response: {json.dumps(response)[:2000]}") from exc
        output_path = Path(output).expanduser().resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        encoded = item.get("b64_json") or item.get("b64")
        if encoded:
            output_path.write_bytes(base64.b64decode(encoded))
            return output_path
        url = item.get("url")
        if url:
            with self.opener.open(url, timeout=self.settings.timeout) as result:
                output_path.write_bytes(result.read())
            return output_path
        raise RelayError(f"image response contained neither b64_json nor url: {json.dumps(item)[:1000]}")
