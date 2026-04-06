import asyncio
import json
from dataclasses import dataclass
from html import escape
from http import HTTPStatus
from pathlib import Path
from urllib.parse import urlparse

from src.core.rfc_catalog import get_supported_protocol_tags


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PUBLIC_DIR = PROJECT_ROOT / "public"
_process_question = None

PROMPT_IDEAS = (
    "IGMPv3 的默认 Query Interval 是多少？",
    "MLDv2 是由哪个 RFC 定义的？",
    "PIM-SM 是由哪个 RFC 定义的？",
    "IGMPv2 支持吗？",
)

CAPABILITIES = (
    "自动判断问题更适合 RFC 专家还是通用对话助手。",
    "基于已预热的 RFC 知识库回答当前支持协议相关问题。",
    "未预热的协议会直接提示暂未入库，避免长时间等待。",
)

INDEX_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Network Expert Agent</title>
  <link rel="stylesheet" href="/app.css">
</head>
<body>
  <div class="page-shell">
    <header class="topbar">
      <div class="brand-block">
        <p class="eyebrow">Network Expert Agent</p>
        <h1>🐳</h1>
        <p class="intro">
          你好呀👋我是你的网络问答专家。
        </p>
      </div>
      <div class="status-pill" id="serviceStatus">
        <span class="status-dot"></span>
        <span>服务已就绪</span>
      </div>
    </header>

    <main class="workspace">
      <section class="chat-region" aria-label="对话区">
        <div class="chat-header">
          <div>
            <p class="section-kicker">Conversation</p>
            <h2>当前会话</h2>
          </div>
          <p class="section-note">建议直接提问协议字段、RFC 编号、报文格式或配置机制。</p>
        </div>

        <div class="chat-log" id="chatLog" aria-live="polite">
          <article class="message assistant welcome">
            <div class="bubble">
              <p class="bubble-role">Assistant</p>
              <p>你好，我是 Network Expert Agent。你可以问我网络协议细节，或者一般性问题。</p>
            </div>
          </article>
        </div>

        <form class="composer" id="chatForm">
          <label class="composer-label" for="messageInput">输入你的问题</label>
          <div class="composer-row">
            <textarea
              id="messageInput"
              name="message"
              rows="1"
              maxlength="4000"
              placeholder="例如：What is the default query interval in IGMPv3?"
              required
            ></textarea>
            <button type="submit" id="sendButton">发送</button>
          </div>
          <p class="composer-hint">按 Enter 发送，Shift + Enter 换行。</p>
        </form>
      </section>

      <aside class="support-region" aria-label="能力说明">
        <section class="info-block">
          <p class="section-kicker">Capabilities</p>
          <h2>可以做什么</h2>
          <ul class="feature-list">
            {capabilities_html}
          </ul>
          <p class="protocol-caption">当前支持协议</p>
          <div class="protocol-tags" aria-label="当前支持协议">
            {protocol_tags_html}
          </div>
          <p class="support-note">当前回答基于已预热的 {supported_protocols_text} 最新版协议，旧版本或其他协议会直接提示未入库。</p>
        </section>

        <section class="info-block prompts">
          <p class="section-kicker">Prompt Ideas</p>
          <h2>可以这样开始</h2>
          <div class="prompt-list">
            {prompt_chips_html}
          </div>
        </section>
      </aside>
    </main>
  </div>

  <script src="/app.js"></script>
</body>
</html>
"""


@dataclass(frozen=True)
class RouteResponse:
    status: int
    content_type: str
    body: bytes
    headers: tuple[tuple[str, str], ...] = ()


def _text_response(
    status: int,
    content: str,
    content_type: str,
    headers: tuple[tuple[str, str], ...] = (),
) -> RouteResponse:
    return RouteResponse(
        status=status,
        content_type=content_type,
        body=content.encode("utf-8"),
        headers=headers,
    )


def _json_response(
    status: int,
    payload: dict[str, object],
    headers: tuple[tuple[str, str], ...] = (),
) -> RouteResponse:
    return RouteResponse(
        status=status,
        content_type="application/json; charset=utf-8",
        body=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers=headers,
    )


def _read_public_asset(filename: str, content_type: str) -> RouteResponse:
    asset_path = PUBLIC_DIR / filename
    content = asset_path.read_text(encoding="utf-8")
    return _text_response(HTTPStatus.OK, content, content_type)


def _get_process_question():
    global _process_question

    if _process_question is None:
        from src.main import process_question as process_question_handler

        _process_question = process_question_handler

    return _process_question


def _build_protocol_tags_html() -> str:
    return "\n            ".join(
        f'<span class="protocol-tag">{escape(protocol)}</span>'
        for protocol in get_supported_protocol_tags()
    )


def _build_capabilities_html() -> str:
    return "\n            ".join(
        f"<li>{escape(item)}</li>"
        for item in CAPABILITIES
    )


def _build_prompt_chips_html() -> str:
    return "\n            ".join(
        f'<button type="button" class="prompt-chip">{escape(prompt)}</button>'
        for prompt in PROMPT_IDEAS
    )


def render_index_html() -> str:
    supported_protocols = get_supported_protocol_tags()
    supported_protocols_text = "、".join(supported_protocols)
    return INDEX_HTML_TEMPLATE.format(
        capabilities_html=_build_capabilities_html(),
        protocol_tags_html=_build_protocol_tags_html(),
        prompt_chips_html=_build_prompt_chips_html(),
        supported_protocols_text=escape(supported_protocols_text),
    )


def build_index_response() -> RouteResponse:
    return _text_response(HTTPStatus.OK, render_index_html(), "text/html; charset=utf-8")


def build_health_response() -> RouteResponse:
    return _json_response(HTTPStatus.OK, {"status": "ok"})


def build_not_found_response() -> RouteResponse:
    return _json_response(HTTPStatus.NOT_FOUND, {"error": "Not found"})


def build_method_not_allowed_response(allowed_methods: str) -> RouteResponse:
    return _json_response(
        HTTPStatus.METHOD_NOT_ALLOWED,
        {"error": "Method not allowed"},
        headers=(("Allow", allowed_methods),),
    )


def build_invalid_content_length_response() -> RouteResponse:
    return _json_response(
        HTTPStatus.BAD_REQUEST,
        {"error": "Invalid Content-Length header"},
    )


def build_chat_response(raw_body: bytes) -> RouteResponse:
    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except json.JSONDecodeError:
        return _json_response(HTTPStatus.BAD_REQUEST, {"error": "Invalid JSON body"})

    message = str(payload.get("message", "")).strip()
    if not message:
        return _json_response(HTTPStatus.BAD_REQUEST, {"error": "Message is required"})

    try:
        answer = asyncio.run(_get_process_question()(message))
    except Exception as exc:
        return _json_response(
            HTTPStatus.INTERNAL_SERVER_ERROR,
            {"error": f"Failed to process request: {exc}"},
        )

    return _json_response(HTTPStatus.OK, {"answer": answer})


def dispatch_local_request(method: str, raw_path: str, body: bytes = b"") -> RouteResponse:
    path = urlparse(raw_path).path
    index_paths = {"/", "/api/index"}
    health_paths = {"/health", "/api/health"}
    chat_paths = {"/api/chat"}

    if method == "GET":
        if path in index_paths:
            return build_index_response()
        if path == "/app.css":
            return _read_public_asset("app.css", "text/css; charset=utf-8")
        if path == "/app.js":
            return _read_public_asset("app.js", "application/javascript; charset=utf-8")
        if path in health_paths:
            return build_health_response()
        if path in chat_paths:
            return build_method_not_allowed_response("POST")
        return build_not_found_response()

    if method == "POST":
        # Vercel may route POST requests to the same Python entrypoint that serves "/".
        # Treat root/index POSTs as chat requests so the deployment keeps working.
        if path in chat_paths or path in index_paths:
            return build_chat_response(body)
        if path in {"/app.css", "/app.js"} | health_paths:
            return build_method_not_allowed_response("GET")
        return build_not_found_response()

    return build_method_not_allowed_response("GET, POST")
