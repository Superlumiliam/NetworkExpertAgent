const chatLog = document.getElementById('chatLog');
const chatForm = document.getElementById('chatForm');
const messageInput = document.getElementById('messageInput');
const sendButton = document.getElementById('sendButton');
const serviceStatus = document.getElementById('serviceStatus');
const promptChips = document.querySelectorAll('.prompt-chip');

function autoResize() {
  messageInput.style.height = 'auto';
  messageInput.style.height = `${Math.min(messageInput.scrollHeight, 180)}px`;
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
