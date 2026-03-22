import asyncio
import json
import os
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from src.main import process_question


HTML_PAGE = """<!DOCTYPE html>
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
        <h1>用对话的方式查询网络协议与 RFC 细节</h1>
        <p class="intro">
          面向当前项目已有能力设计：输入问题，系统自动路由到 RFC 专家或通用助手，并把结果以清晰的对话气泡返回。
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
              <p>你好，我是 Network Expert Agent。你可以问我 RFC、网络协议细节，或者一般性问题。</p>
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
          <h2>和项目能力保持一致</h2>
          <ul class="feature-list">
            <li>自动判断问题更适合 RFC 专家还是通用对话助手。</li>
            <li>需要时会查询本地知识库，并补充下载对应 RFC 文档。</li>
            <li>返回结果只围绕问答本身，不包含当前项目没有实现的扩展操作。</li>
          </ul>
        </section>

        <section class="info-block prompts">
          <p class="section-kicker">Prompt Ideas</p>
          <h2>可以这样开始</h2>
          <div class="prompt-list">
            <button type="button" class="prompt-chip">Explain the TCP three-way handshake.</button>
            <button type="button" class="prompt-chip">RFC 8200 defines which IPv6 header fields?</button>
            <button type="button" class="prompt-chip">IGMPv3 的默认查询间隔是多少？</button>
          </div>
        </section>
      </aside>
    </main>
  </div>

  <script src="/app.js"></script>
</body>
</html>
"""


CSS_STYLES = """:root {
  --bg: #f6f1e8;
  --bg-soft: #fbf8f2;
  --panel: rgba(255, 252, 247, 0.88);
  --panel-strong: rgba(255, 250, 243, 0.96);
  --line: rgba(132, 104, 66, 0.16);
  --text: #2f2419;
  --muted: #7d6a56;
  --accent: #739b78;
  --accent-strong: #587d5f;
  --assistant: #fff9f0;
  --user: #dfeee0;
  --shadow: 0 18px 48px rgba(98, 74, 39, 0.08);
}

* {
  box-sizing: border-box;
}

html, body {
  margin: 0;
  min-height: 100%;
}

body {
  font-family: "Avenir Next", "PingFang SC", "Hiragino Sans GB", "Segoe UI", sans-serif;
  color: var(--text);
  background:
    radial-gradient(circle at top left, rgba(243, 216, 170, 0.35), transparent 28%),
    radial-gradient(circle at top right, rgba(181, 210, 184, 0.45), transparent 25%),
    linear-gradient(180deg, #f8f4ec 0%, var(--bg) 44%, #f3ede3 100%);
}

body::before {
  content: "";
  position: fixed;
  inset: 0;
  background:
    linear-gradient(120deg, rgba(255, 255, 255, 0.32), transparent 30%),
    repeating-linear-gradient(
      90deg,
      rgba(121, 153, 110, 0.04) 0,
      rgba(121, 153, 110, 0.04) 1px,
      transparent 1px,
      transparent 72px
    );
  pointer-events: none;
}

.page-shell {
  position: relative;
  padding: 32px;
}

.topbar,
.workspace {
  width: min(1180px, 100%);
  margin: 0 auto;
}

.topbar {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 24px;
  padding: 10px 0 30px;
  animation: lift-in 700ms ease both;
}

.brand-block {
  max-width: 720px;
}

.eyebrow,
.section-kicker,
.bubble-role {
  margin: 0 0 10px;
  font-size: 0.78rem;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--muted);
}

.topbar h1,
.support-region h2,
.chat-header h2 {
  margin: 0;
  font-family: "Iowan Old Style", "Georgia", serif;
  font-weight: 600;
  letter-spacing: -0.03em;
}

.topbar h1 {
  max-width: 12ch;
  font-size: clamp(2.4rem, 4vw, 4.8rem);
  line-height: 0.94;
}

.intro,
.section-note,
.feature-list,
.composer-hint {
  color: var(--muted);
}

.intro {
  max-width: 58ch;
  margin: 16px 0 0;
  font-size: 1.05rem;
  line-height: 1.7;
}

.status-pill {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  padding: 12px 16px;
  border: 1px solid var(--line);
  border-radius: 999px;
  background: rgba(255, 251, 245, 0.82);
  box-shadow: var(--shadow);
  color: var(--muted);
  backdrop-filter: blur(12px);
}

.status-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: var(--accent);
  box-shadow: 0 0 0 6px rgba(115, 155, 120, 0.12);
}

.workspace {
  display: grid;
  grid-template-columns: minmax(0, 1.6fr) minmax(280px, 0.9fr);
  gap: 28px;
  align-items: start;
}

.chat-region,
.support-region {
  min-height: 68svh;
}

.chat-region {
  display: flex;
  flex-direction: column;
  border: 1px solid var(--line);
  background: var(--panel);
  box-shadow: var(--shadow);
  backdrop-filter: blur(18px);
}

.chat-header,
.composer,
.info-block {
  padding: 24px 26px;
}

.chat-header {
  display: flex;
  justify-content: space-between;
  align-items: end;
  gap: 18px;
  border-bottom: 1px solid var(--line);
}

.chat-header h2,
.support-region h2 {
  font-size: 1.65rem;
}

.section-note {
  max-width: 28ch;
  margin: 0;
  line-height: 1.6;
  text-align: right;
}

.chat-log {
  flex: 1;
  min-height: 420px;
  max-height: 68svh;
  overflow-y: auto;
  padding: 24px 26px 10px;
  scroll-behavior: smooth;
}

.message {
  display: flex;
  margin-bottom: 18px;
  opacity: 0;
  transform: translateY(12px);
  animation: bubble-in 360ms ease forwards;
}

.message.user {
  justify-content: flex-end;
}

.message.assistant {
  justify-content: flex-start;
}

.bubble {
  max-width: min(78%, 700px);
  padding: 16px 18px;
  border-radius: 24px;
  border: 1px solid rgba(121, 91, 58, 0.08);
  line-height: 1.7;
  box-shadow: 0 12px 24px rgba(77, 55, 27, 0.05);
}

.assistant .bubble {
  background: var(--assistant);
  border-bottom-left-radius: 8px;
}

.user .bubble {
  background: var(--user);
  border-bottom-right-radius: 8px;
}

.bubble p {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
}

.welcome .bubble {
  background: linear-gradient(180deg, #fff9f0 0%, #fffcf7 100%);
}

.composer {
  border-top: 1px solid var(--line);
  background: var(--panel-strong);
}

.composer-label {
  display: block;
  margin-bottom: 12px;
  font-size: 0.94rem;
}

.composer-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 12px;
  align-items: end;
}

textarea {
  width: 100%;
  min-height: 58px;
  max-height: 180px;
  resize: vertical;
  border: 1px solid rgba(125, 106, 86, 0.22);
  border-radius: 20px;
  padding: 16px 18px;
  font: inherit;
  color: var(--text);
  background: rgba(255, 255, 255, 0.78);
  transition: border-color 180ms ease, box-shadow 180ms ease, transform 180ms ease;
}

textarea:focus {
  outline: none;
  border-color: rgba(115, 155, 120, 0.72);
  box-shadow: 0 0 0 4px rgba(115, 155, 120, 0.14);
}

button {
  font: inherit;
  cursor: pointer;
}

#sendButton,
.prompt-chip {
  border: none;
  transition: transform 180ms ease, background-color 180ms ease, color 180ms ease, opacity 180ms ease;
}

#sendButton {
  min-width: 108px;
  padding: 16px 20px;
  border-radius: 999px;
  background: var(--accent);
  color: #f9fbf7;
}

#sendButton:hover,
#sendButton:focus-visible {
  background: var(--accent-strong);
  transform: translateY(-1px);
}

#sendButton:disabled {
  opacity: 0.6;
  cursor: wait;
}

.composer-hint {
  margin: 10px 0 0;
  font-size: 0.88rem;
}

.support-region {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.info-block {
  border: 1px solid var(--line);
  background: rgba(255, 251, 246, 0.72);
  box-shadow: var(--shadow);
  backdrop-filter: blur(14px);
  animation: lift-in 850ms ease both;
}

.feature-list {
  margin: 18px 0 0;
  padding-left: 18px;
  line-height: 1.85;
}

.prompts {
  position: sticky;
  top: 20px;
}

.prompt-list {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 18px;
}

.prompt-chip {
  padding: 13px 16px;
  border-radius: 999px;
  background: rgba(115, 155, 120, 0.1);
  color: var(--text);
}

.prompt-chip:hover,
.prompt-chip:focus-visible {
  background: rgba(115, 155, 120, 0.2);
  transform: translateY(-1px);
}

.typing .bubble {
  position: relative;
  min-width: 92px;
}

.typing .bubble::after {
  content: "思考中...";
  color: var(--muted);
}

@keyframes lift-in {
  from {
    opacity: 0;
    transform: translateY(18px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes bubble-in {
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@media (max-width: 980px) {
  .page-shell {
    padding: 20px;
  }

  .workspace {
    grid-template-columns: 1fr;
  }

  .chat-region,
  .support-region {
    min-height: auto;
  }

  .chat-log {
    max-height: none;
    min-height: 360px;
  }

  .prompts {
    position: static;
  }

  .chat-header {
    flex-direction: column;
    align-items: flex-start;
  }

  .section-note {
    text-align: left;
  }
}

@media (max-width: 640px) {
  .topbar {
    flex-direction: column;
  }

  .topbar h1 {
    max-width: 100%;
  }

  .chat-header,
  .composer,
  .info-block {
    padding: 20px;
  }

  .chat-log {
    padding: 20px 20px 10px;
  }

  .bubble {
    max-width: 88%;
  }

  .composer-row {
    grid-template-columns: 1fr;
  }

  #sendButton {
    width: 100%;
  }
}
"""


JS_APP = """const chatLog = document.getElementById('chatLog');
const chatForm = document.getElementById('chatForm');
const messageInput = document.getElementById('messageInput');
const sendButton = document.getElementById('sendButton');
const serviceStatus = document.getElementById('serviceStatus');
const promptChips = document.querySelectorAll('.prompt-chip');

function autoResize() {
  messageInput.style.height = 'auto';
  messageInput.style.height = Math.min(messageInput.scrollHeight, 180) + 'px';
}

function scrollToBottom() {
  chatLog.scrollTop = chatLog.scrollHeight;
}

function createMessage(role, content, extraClass = '') {
  const article = document.createElement('article');
  article.className = `message ${role} ${extraClass}`.trim();

  const bubble = document.createElement('div');
  bubble.className = 'bubble';

  if (!extraClass.includes('typing')) {
    const roleTag = document.createElement('p');
    roleTag.className = 'bubble-role';
    roleTag.textContent = role === 'user' ? 'You' : 'Assistant';

    const text = document.createElement('p');
    text.textContent = content;

    bubble.appendChild(roleTag);
    bubble.appendChild(text);
  }

  article.appendChild(bubble);
  chatLog.appendChild(article);
  scrollToBottom();
  return article;
}

async function sendMessage(message) {
  createMessage('user', message);
  const typingNode = createMessage('assistant', '', 'typing');

  sendButton.disabled = true;
  sendButton.textContent = '发送中';
  serviceStatus.lastElementChild.textContent = '正在处理';

  try {
    const response = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message }),
    });

    const data = await response.json();
    typingNode.remove();

    if (!response.ok) {
      throw new Error(data.error || '请求失败');
    }

    createMessage('assistant', data.answer || '未返回内容。');
    serviceStatus.lastElementChild.textContent = '服务已就绪';
  } catch (error) {
    typingNode.remove();
    createMessage('assistant', `请求失败：${error.message}`);
    serviceStatus.lastElementChild.textContent = '服务异常';
  } finally {
    sendButton.disabled = false;
    sendButton.textContent = '发送';
    messageInput.focus();
    scrollToBottom();
  }
}

chatForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  const message = messageInput.value.trim();

  if (!message) {
    return;
  }

  messageInput.value = '';
  autoResize();
  await sendMessage(message);
});

messageInput.addEventListener('input', autoResize);
messageInput.addEventListener('keydown', (event) => {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault();
    chatForm.requestSubmit();
  }
});

promptChips.forEach((chip) => {
  chip.addEventListener('click', () => {
    messageInput.value = chip.textContent;
    autoResize();
    messageInput.focus();
  });
});

window.addEventListener('load', async () => {
  autoResize();
  scrollToBottom();

  try {
    const response = await fetch('/health');
    if (!response.ok) {
      throw new Error('health check failed');
    }
  } catch (error) {
    serviceStatus.lastElementChild.textContent = '服务未连接';
  }
});
"""


def _json_response(handler: BaseHTTPRequestHandler, status: int, payload: dict) -> None:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _text_response(
    handler: BaseHTTPRequestHandler,
    status: int,
    content: str,
    content_type: str,
) -> None:
    body = content.encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", content_type)
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


class NetworkExpertHandler(BaseHTTPRequestHandler):
    server_version = "NetworkExpertHTTP/0.1"

    def do_GET(self) -> None:
        if self.path == "/":
            _text_response(self, HTTPStatus.OK, HTML_PAGE, "text/html; charset=utf-8")
            return

        if self.path == "/app.css":
            _text_response(self, HTTPStatus.OK, CSS_STYLES, "text/css; charset=utf-8")
            return

        if self.path == "/app.js":
            _text_response(
                self,
                HTTPStatus.OK,
                JS_APP,
                "application/javascript; charset=utf-8",
            )
            return

        if self.path == "/health":
            _json_response(self, HTTPStatus.OK, {"status": "ok"})
            return

        _json_response(self, HTTPStatus.NOT_FOUND, {"error": "Not found"})

    def do_POST(self) -> None:
        if self.path != "/api/chat":
            _json_response(self, HTTPStatus.NOT_FOUND, {"error": "Not found"})
            return

        try:
            content_length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            _json_response(
                self,
                HTTPStatus.BAD_REQUEST,
                {"error": "Invalid Content-Length header"},
            )
            return

        raw_body = self.rfile.read(content_length)

        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except json.JSONDecodeError:
            _json_response(self, HTTPStatus.BAD_REQUEST, {"error": "Invalid JSON body"})
            return

        message = str(payload.get("message", "")).strip()
        if not message:
            _json_response(self, HTTPStatus.BAD_REQUEST, {"error": "Message is required"})
            return

        try:
            answer = asyncio.run(process_question(message))
        except Exception as exc:
            _json_response(
                self,
                HTTPStatus.INTERNAL_SERVER_ERROR,
                {"error": f"Failed to process request: {exc}"},
            )
            return

        _json_response(self, HTTPStatus.OK, {"answer": answer})

    def log_message(self, format: str, *args) -> None:
        return


def main() -> None:
    host = os.getenv("NETWORK_EXPERT_WEB_HOST", "127.0.0.1")
    port = int(os.getenv("NETWORK_EXPERT_WEB_PORT", "8000"))

    server = ThreadingHTTPServer((host, port), NetworkExpertHandler)
    print(f"Network Expert Web UI available at http://{host}:{port}")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\\nShutting down web server...")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
