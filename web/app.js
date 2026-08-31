document.addEventListener('DOMContentLoaded', () => {
  const chatMessages = document.getElementById('chat-messages');
  const chatInput = document.getElementById('chat-input');
  const sendBtn = document.getElementById('send-btn');
  const syncStatus = document.getElementById('sync-status');
  const factsList = document.getElementById('facts-list');
  const activeFactsCount = document.getElementById('active-facts-count');
  const entitiesCount = document.getElementById('entities-count');
  const memorySearch = document.getElementById('memory-search');
  const refreshFactsBtn = document.getElementById('refresh-facts-btn');
  const toggleMemoryBtn = document.getElementById('toggle-memory-btn');
  const memorySidebar = document.getElementById('memory-sidebar');
  const historyModal = document.getElementById('history-modal');
  const modalTitle = document.getElementById('modal-title');
  const modalBody = document.getElementById('modal-body');
  const modalCloseBtn = document.getElementById('modal-close-btn');

  let allActiveFacts = [];
  let isSending = false;

  // Toggle Memory Sidebar
  toggleMemoryBtn.addEventListener('click', () => {
    memorySidebar.classList.toggle('closed');
  });

  // Modal Close
  modalCloseBtn.addEventListener('click', () => {
    historyModal.classList.remove('open');
  });
  historyModal.addEventListener('click', (e) => {
    if (e.target === historyModal) historyModal.classList.remove('open');
  });

  // Auto-resize chat textarea
  chatInput.addEventListener('input', () => {
    chatInput.style.height = 'auto';
    chatInput.style.height = Math.min(chatInput.scrollHeight, 140) + 'px';
  });

  // Enter to send
  chatInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  });

  sendBtn.addEventListener('click', handleSend);

  // Quick Chips
  document.querySelectorAll('.quick-chip').forEach(chip => {
    chip.addEventListener('click', () => {
      chatInput.value = chip.dataset.prompt;
      chatInput.focus();
      handleSend();
    });
  });

  // Refresh Facts
  refreshFactsBtn.addEventListener('click', fetchFacts);

  // Search Facts
  memorySearch.addEventListener('input', (e) => {
    const q = e.target.value.toLowerCase();
    renderFacts(allActiveFacts.filter(f => 
      f.entity.toLowerCase().includes(q) ||
      f.attribute.toLowerCase().includes(q) ||
      f.value.toLowerCase().includes(q)
    ));
  });

  // Fetch facts on page load
  fetchFacts();

  async function fetchFacts() {
    try {
      refreshFactsBtn.classList.add('spinning');
      const res = await fetch('/facts');
      if (!res.ok) throw new Error('Failed to fetch facts');
      allActiveFacts = await res.json();
      renderFacts(allActiveFacts);
    } catch (err) {
      console.error('Error loading facts:', err);
    } finally {
      refreshFactsBtn.classList.remove('spinning');
    }
  }

  function renderFacts(facts) {
    activeFactsCount.textContent = facts.length;
    const uniqueEntities = new Set(facts.map(f => f.entity));
    entitiesCount.textContent = uniqueEntities.size;

    if (facts.length === 0) {
      factsList.innerHTML = '<div class="empty-facts">No facts stored yet. Start conversing with ECHO to build your memory!</div>';
      return;
    }

    factsList.innerHTML = facts.map(f => `
      <div class="fact-card" data-id="${f.id}">
        <div class="fact-entity">${escapeHtml(f.entity)}</div>
        <div class="fact-attribute">${escapeHtml(f.attribute.replace(/_/g, ' '))}</div>
        <div class="fact-value">${escapeHtml(f.value)}</div>
        <div class="fact-footer">
          <button class="fact-history-link" onclick="window.viewFactHistory('${escapeHtml(f.entity)}', '${escapeHtml(f.attribute)}')">
            View History
          </button>
          <span style="font-size:0.7rem; color:var(--text-muted);">
            ${f.created_at ? new Date(f.created_at).toLocaleDateString() : ''}
          </span>
        </div>
      </div>
    `).join('');
  }

  window.viewFactHistory = async function(entity, attribute) {
    try {
      modalTitle.textContent = `Memory History: ${entity}.${attribute}`;
      modalBody.innerHTML = '<div style="text-align:center; padding:20px; color:var(--text-muted);">Loading audit timeline...</div>';
      historyModal.classList.add('open');

      const res = await fetch(`/facts/history/${encodeURIComponent(entity)}/${encodeURIComponent(attribute)}`);
      if (!res.ok) throw new Error('History not found');
      const history = await res.json();

      modalBody.innerHTML = `
        <div class="timeline">
          ${history.map((item, idx) => {
            const isActive = !item.superseded_by;
            return `
              <div class="timeline-item ${isActive ? 'active' : 'superseded'}">
                <div class="timeline-dot"></div>
                <div class="timeline-tag">${isActive ? '● CURRENT ACTIVE' : '○ SUPERSEDED'}</div>
                <div class="timeline-value">${escapeHtml(item.value)}</div>
                <div class="timeline-time">${item.created_at ? new Date(item.created_at).toLocaleString() : ''}</div>
              </div>
            `;
          }).join('')}
        </div>
      `;
    } catch (err) {
      modalBody.innerHTML = `<div style="color:var(--accent-rose); padding:20px;">Could not load history: ${escapeHtml(err.message)}</div>`;
    }
  };

  async function handleSend() {
    const text = chatInput.value.trim();
    if (!text || isSending) return;

    isSending = true;
    chatInput.value = '';
    chatInput.style.height = 'auto';

    // Remove welcome card if present
    const welcomeCard = document.querySelector('.welcome-card');
    if (welcomeCard) welcomeCard.remove();

    // Append user message
    appendMessage('user', text);
    syncStatus.textContent = '⚡ ECHO is thinking & recalling memory...';

    // Append assistant typing indicator
    const typingId = appendTypingIndicator();

    try {
      const res = await fetch('/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ platform: 'web', message: text })
      });

      if (!res.ok) {
        throw new Error(`Server returned ${res.status}`);
      }

      const data = await res.json();
      removeTypingIndicator(typingId);

      // Append assistant reply with memory tags
      appendMessage('assistant', data.reply, data.extracted_facts);

      // Refresh memory sidebar facts
      if (data.extracted_facts && data.extracted_facts.length > 0) {
        fetchFacts();
      }

      syncStatus.textContent = '⚡ Memory synchronized';
    } catch (err) {
      removeTypingIndicator(typingId);
      appendMessage('assistant', `⚠️ Sorry, an error occurred while processing: ${err.message}`);
      syncStatus.textContent = '⚠️ Connection error';
    } finally {
      isSending = false;
      chatInput.focus();
    }
  }

  function appendMessage(role, content, extractedFacts = []) {
    const row = document.createElement('div');
    row.className = `message-row ${role}`;

    const avatar = document.createElement('div');
    avatar.className = 'avatar';
    avatar.textContent = role === 'user' ? '👤' : '🧠';

    const bubbleWrapper = document.createElement('div');
    bubbleWrapper.style.display = 'flex';
    bubbleWrapper.style.flexDirection = 'column';
    bubbleWrapper.style.maxWidth = '100%';

    const bubble = document.createElement('div');
    bubble.className = 'message-bubble';
    bubble.innerHTML = formatMessageText(content);
    bubbleWrapper.appendChild(bubble);

    // If facts extracted, render badges
    if (extractedFacts && extractedFacts.length > 0) {
      const tagsContainer = document.createElement('div');
      tagsContainer.className = 'memory-tags';
      extractedFacts.forEach(fact => {
        const tag = document.createElement('span');
        tag.className = `memory-tag ${fact.contradicts_existing ? 'superseded' : 'new'}`;
        const icon = fact.contradicts_existing ? '🔄 Updated' : '✨ Learned';
        tag.innerHTML = `${icon}: <strong>${escapeHtml(fact.entity)}.${escapeHtml(fact.attribute)}</strong> = "${escapeHtml(fact.value)}"`;
        tagsContainer.appendChild(tag);
      });
      bubbleWrapper.appendChild(tagsContainer);
    }

    row.appendChild(avatar);
    row.appendChild(bubbleWrapper);
    chatMessages.appendChild(row);
    chatMessages.scrollTop = chatMessages.scrollHeight;
  }

  function appendTypingIndicator() {
    const id = 'typing-' + Date.now();
    const row = document.createElement('div');
    row.className = 'message-row assistant';
    row.id = id;

    const avatar = document.createElement('div');
    avatar.className = 'avatar';
    avatar.textContent = '🧠';

    const bubble = document.createElement('div');
    bubble.className = 'message-bubble';
    bubble.innerHTML = '<span style="color:var(--text-muted); font-style:italic;">ECHO is recalling memory and writing...</span>';

    row.appendChild(avatar);
    row.appendChild(bubble);
    chatMessages.appendChild(row);
    chatMessages.scrollTop = chatMessages.scrollHeight;
    return id;
  }

  function removeTypingIndicator(id) {
    const el = document.getElementById(id);
    if (el) el.remove();
  }

  function formatMessageText(text) {
    return escapeHtml(text).replace(/\n/g, '<br/>');
  }

  function escapeHtml(str) {
    if (!str) return '';
    return str
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }
});
