/**
 * @fileoverview Stashboard popup script.
 *
 * Responsibilities:
 *  - Load clips from background, render paginated list
 *  - Full keyboard navigation (Arrow keys, Enter, /, Tab, P, D, E, S, Escape)
 *  - Debounced search across text, title, and source URL
 *  - Space switching and category filtering
 *  - Inline clip editing, pin/unpin, delete, space move
 *  - Lazy loading via IntersectionObserver
 *  - Settings panel read/write
 *  - Light/dark theme application
 */

'use strict';

// ── Constants ─────────────────────────────────────────────────────────────────

const PAGE_SIZE = 30;

/** @type {Array<{id: string, label: string}>} */
const CATEGORIES = [
  { id: 'email',      label: 'Email'   },
  { id: 'phone',      label: 'Phone'   },
  { id: 'url',        label: 'URL'     },
  { id: 'code',       label: 'Code'    },
  { id: 'json',       label: 'JSON'    },
  { id: 'color_hex',  label: 'Color'   },
  { id: 'address',    label: 'Address' },
  { id: 'ip_address', label: 'IP'      },
  { id: 'text',       label: 'Text'    },
];

// ── Application state ─────────────────────────────────────────────────────────

const state = {
  /** @type {Array<Object>} Currently displayed clips */
  clips:          [],
  /** @type {Array<Object>} All spaces */
  spaces:         [],
  /** @type {string} Active space ID */
  activeSpace:    'all',
  /** @type {string|null} Active category filter */
  activeCategory: null,
  /** @type {number} Keyboard-selected list index */
  selectedIndex:  0,
  /** @type {string} Current search query */
  searchQuery:    '',
  /** @type {number} Total matching clips (for pagination) */
  total:          0,
  /** @type {number} Offset for next page load */
  offset:         0,
  /** @type {boolean} True while fetching */
  loading:        false,
  /** @type {Object} User settings */
  settings:       {},
  /** @type {string|null} ID of clip currently being edited */
  editingId:      null,
};

// ── DOM references ─────────────────────────────────────────────────────────────

const el = (id) => document.getElementById(id);

const searchInput    = el('search');
const spaceTabsEl    = el('space-tabs');
const categoryFilter = el('category-filter');
const clipsList      = el('clips-list');
const statusCount    = el('status-count');
const statusCapture  = el('status-capture');
const settingsBtn    = el('settings-btn');
const settingsPanel  = el('settings-panel');
const settingsClose  = el('settings-close');
const settingsSave   = el('settings-save');
const settingCapture = el('setting-capture');
const settingTheme   = el('setting-theme');
const settingExcluded= el('setting-excluded');
const loadMoreSentinel = el('load-more-sentinel');

// ── Messaging ─────────────────────────────────────────────────────────────────

/**
 * Sends a message to the background service worker and resolves with the response.
 * @param {Object} msg
 * @returns {Promise<any>}
 */
function sendMessage(msg) {
  return new Promise((resolve, reject) => {
    chrome.runtime.sendMessage(msg, (response) => {
      if (chrome.runtime.lastError) {
        reject(new Error(chrome.runtime.lastError.message));
      } else {
        resolve(response);
      }
    });
  });
}

// ── Utilities ─────────────────────────────────────────────────────────────────

/**
 * Formats a Unix timestamp (ms) as a human-readable relative string.
 * @param {number} ts
 * @returns {string}
 */
function relativeTime(ts) {
  const diff = Date.now() - ts;
  const s = Math.floor(diff / 1000);
  if (s < 15)   return 'just now';
  if (s < 60)   return `${s}s ago`;
  const m = Math.floor(s / 60);
  if (m < 60)   return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24)   return `${h}h ago`;
  const d = Math.floor(h / 24);
  if (d === 1)  return 'yesterday';
  if (d < 7)    return `${d}d ago`;
  return new Date(ts).toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}

/**
 * Extracts the bare hostname from a URL (strips www.).
 * @param {string} url
 * @returns {string}
 */
function getDomain(url) {
  try { return new URL(url).hostname.replace(/^www\./, ''); }
  catch { return ''; }
}

/**
 * Returns a favicon URL for a given page URL.
 * @param {string} url
 * @returns {string}
 */
function faviconUrl(url) {
  try { return `${new URL(url).origin}/favicon.ico`; }
  catch { return ''; }
}

/**
 * Escapes HTML entities to prevent XSS in innerHTML assignments.
 * @param {string} str
 * @returns {string}
 */
function esc(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

/**
 * Highlights all occurrences of a query string within text using <mark>.
 * @param {string} text
 * @param {string} query
 * @returns {string} HTML string with matches wrapped in <mark>.
 */
function highlightMatches(text, query) {
  if (!query) return esc(text);
  const escaped = esc(text);
  const escapedQuery = query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  return escaped.replace(
    new RegExp(escapedQuery, 'gi'),
    (match) => `<mark>${match}</mark>`,
  );
}

// ── Theme ─────────────────────────────────────────────────────────────────────

/**
 * Applies the theme preference to the document root element.
 * @param {'light'|'dark'|'system'} theme
 */
function applyTheme(theme) {
  if (theme === 'dark')  document.documentElement.setAttribute('data-theme', 'dark');
  else if (theme === 'light') document.documentElement.setAttribute('data-theme', 'light');
  else document.documentElement.removeAttribute('data-theme');
}

// ── Rendering ─────────────────────────────────────────────────────────────────

/**
 * Renders the space tab navigation.
 */
function renderSpaces() {
  spaceTabsEl.innerHTML = '';
  state.spaces.forEach((space) => {
    const btn = document.createElement('button');
    btn.className = `space-tab${state.activeSpace === space.id ? ' active' : ''}`;
    btn.setAttribute('role', 'tab');
    btn.setAttribute('aria-selected', String(state.activeSpace === space.id));
    btn.dataset.spaceId = space.id;
    btn.innerHTML = `<span class="space-icon">${space.icon}</span>${esc(space.name)}`;
    btn.addEventListener('click', () => switchSpace(space.id));
    spaceTabsEl.appendChild(btn);
  });
}

/**
 * Renders the category filter pills.
 */
function renderCategoryFilter() {
  categoryFilter.innerHTML = '';
  CATEGORIES.forEach(({ id, label }) => {
    const btn = document.createElement('button');
    btn.className = `cat-btn cat-${id}${state.activeCategory === id ? ' active' : ''}`;
    btn.textContent = label;
    btn.dataset.category = id;
    btn.title = `Filter: ${label}`;
    btn.addEventListener('click', () => toggleCategory(id));
    categoryFilter.appendChild(btn);
  });
}

/**
 * Constructs and returns a single clip list-item element.
 * @param {Object} clip
 * @param {number} index - Position in the visible list.
 * @returns {HTMLElement}
 */
function buildClipElement(clip, index) {
  const wrap = document.createElement('div');
  wrap.className =
    `clip-item` +
    (clip.pinned ? ' pinned' : '') +
    (index === state.selectedIndex ? ' selected' : '');
  wrap.dataset.id       = clip.id;
  wrap.dataset.index    = String(index);
  wrap.dataset.category = clip.category || 'text';
  wrap.setAttribute('role', 'listitem');
  wrap.setAttribute('tabindex', '-1');

  const category  = clip.category || 'text';
  const time      = relativeTime(clip.timestamp);
  const domain    = clip.source ? getDomain(clip.source) : '';
  const favicon   = clip.source ? faviconUrl(clip.source) : '';
  const textHtml  = highlightMatches(clip.text, state.searchQuery);

  wrap.innerHTML = `
    <div class="clip-top">
      <span class="clip-category-badge cat-${esc(category)}">${esc(category.replace(/_/g, ' '))}</span>
      <div class="clip-meta">
        ${clip.copyCount > 1 ? `<span class="clip-count" title="Copied ${clip.copyCount} times">×${clip.copyCount}</span>` : ''}
        <span class="clip-time">${time}</span>
        ${clip.pinned ? '<span class="clip-pin-icon" title="Pinned">📌</span>' : ''}
      </div>
    </div>
    <div class="clip-text">${textHtml}</div>
    ${domain ? `
    <div class="clip-source">
      ${favicon ? `<img class="clip-source-favicon" src="${esc(favicon)}" alt="" loading="lazy" onerror="this.style.display='none'" />` : ''}
      <span class="clip-source-domain" title="${esc(clip.source || '')}">${esc(domain)}</span>
    </div>` : ''}
  `;

  // Click to paste
  wrap.addEventListener('click', (e) => {
    if (e.target.closest('.clip-edit-textarea, .clip-edit-actions, .space-picker')) return;
    state.selectedIndex = index;
    updateSelection();
    pasteSelected();
  });

  // Hover changes keyboard cursor without stealing focus
  wrap.addEventListener('mouseenter', () => {
    if (state.editingId) return;
    state.selectedIndex = index;
    updateSelection();
  });

  return wrap;
}

/**
 * Replaces the clips list with the current state.clips array.
 */
function renderClips() {
  clipsList.innerHTML = '';

  if (state.clips.length === 0) {
    clipsList.innerHTML = state.searchQuery
      ? `<div class="empty-state">
           <div class="empty-state-emoji">🔍</div>
           <div class="empty-state-title">No results for "${esc(state.searchQuery)}"</div>
           <div class="empty-state-subtitle">Try a different search term</div>
         </div>`
      : `<div class="empty-state">
           <div class="empty-state-emoji">📋</div>
           <div class="empty-state-title">No clips yet</div>
           <div class="empty-state-subtitle">Copy something to get started!</div>
         </div>`;
    updateStatus();
    return;
  }

  const frag = document.createDocumentFragment();
  state.clips.forEach((clip, i) => frag.appendChild(buildClipElement(clip, i)));
  clipsList.appendChild(frag);
  updateStatus();
}

/**
 * Appends a new page of clips to the existing list (lazy loading).
 * @param {Array<Object>} newClips
 */
function appendClips(newClips) {
  const startIndex = state.clips.length - newClips.length;
  const frag = document.createDocumentFragment();
  newClips.forEach((clip, i) => frag.appendChild(buildClipElement(clip, startIndex + i)));
  clipsList.appendChild(frag);
}

/**
 * Syncs the .selected class on list items to match state.selectedIndex.
 * Scrolls the selected item into view smoothly.
 */
function updateSelection() {
  const items = clipsList.querySelectorAll('.clip-item');
  items.forEach((item, i) => item.classList.toggle('selected', i === state.selectedIndex));
  const selected = clipsList.querySelector('.clip-item.selected');
  selected?.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
}

/**
 * Refreshes the status bar counters and capture indicator.
 */
function updateStatus() {
  statusCount.textContent = `${state.total} clip${state.total !== 1 ? 's' : ''}`;
  const capturing = state.settings.captureEnabled !== false;
  statusCapture.textContent = capturing ? '● Capturing' : '● Paused';
  statusCapture.className = `status-capture ${capturing ? 'capture-on' : 'capture-off'}`;
}

// ── Data fetching ─────────────────────────────────────────────────────────────

/**
 * Fetches the first page of clips matching current filters and re-renders the list.
 * @returns {Promise<void>}
 */
async function loadClips() {
  if (state.loading) return;
  state.loading = true;
  state.offset  = 0;
  state.clips   = [];

  try {
    const resp = await sendMessage({
      type:    'GET_CLIPS',
      options: {
        spaceId:  state.activeSpace,
        category: state.activeCategory,
        query:    state.searchQuery,
        offset:   0,
        limit:    PAGE_SIZE,
      },
    });

    if (resp) {
      state.clips  = resp.clips  ?? [];
      state.total  = resp.total  ?? 0;
      state.offset = state.clips.length;
      state.selectedIndex = 0;
    }
  } finally {
    state.loading = false;
  }

  renderClips();
}

/**
 * Loads the next page of clips and appends them to the list.
 * @returns {Promise<void>}
 */
async function loadMore() {
  if (state.loading || state.clips.length >= state.total) return;
  state.loading = true;

  try {
    const resp = await sendMessage({
      type:    'GET_CLIPS',
      options: {
        spaceId:  state.activeSpace,
        category: state.activeCategory,
        query:    state.searchQuery,
        offset:   state.offset,
        limit:    PAGE_SIZE,
      },
    });

    if (resp?.clips?.length) {
      state.clips.push(...resp.clips);
      state.offset = state.clips.length;
      appendClips(resp.clips);
    }
  } finally {
    state.loading = false;
  }
}

// ── Clip actions ──────────────────────────────────────────────────────────────

/**
 * Sends the selected clip to the active tab's focused element and closes the popup.
 * @returns {Promise<void>}
 */
async function pasteSelected() {
  const clip = state.clips[state.selectedIndex];
  if (!clip) return;
  try {
    await sendMessage({ type: 'PASTE_TEXT', text: clip.text });
  } catch (err) {
    console.error('[Stashboard] Paste error:', err);
  }
  window.close();
}

/**
 * Copies the selected clip to the system clipboard and closes the popup.
 * @returns {Promise<void>}
 */
async function copySelected() {
  const clip = state.clips[state.selectedIndex];
  if (!clip) return;
  try {
    await navigator.clipboard.writeText(clip.text);
  } catch (err) {
    console.error('[Stashboard] Clipboard write error:', err);
  }
  window.close();
}

/**
 * Removes the selected clip, with confirmation for pinned items.
 * @returns {Promise<void>}
 */
async function deleteSelected() {
  const clip = state.clips[state.selectedIndex];
  if (!clip) return;

  if (clip.pinned && !confirm('Delete this pinned clip?')) return;

  // Animate removal
  const items = clipsList.querySelectorAll('.clip-item');
  const itemEl = items[state.selectedIndex];
  if (itemEl) {
    itemEl.classList.add('removing');
    await new Promise((r) => setTimeout(r, 150));
  }

  await sendMessage({ type: 'DELETE_CLIP', id: clip.id });
  state.clips.splice(state.selectedIndex, 1);
  state.total = Math.max(0, state.total - 1);

  if (state.selectedIndex >= state.clips.length) {
    state.selectedIndex = Math.max(0, state.clips.length - 1);
  }

  renderClips();
}

/**
 * Toggles the pin state of the selected clip and re-renders.
 * @returns {Promise<void>}
 */
async function pinSelected() {
  const clip = state.clips[state.selectedIndex];
  if (!clip) return;

  const resp = await sendMessage({ type: 'PIN_CLIP', id: clip.id });
  if (resp?.pinned !== undefined) {
    clip.pinned = resp.pinned;

    // Re-sort: pinned items belong at the top
    state.clips.sort((a, b) => {
      if (a.pinned && !b.pinned) return -1;
      if (!a.pinned && b.pinned) return 1;
      return b.timestamp - a.timestamp;
    });
    state.selectedIndex = state.clips.findIndex((c) => c.id === clip.id);
    renderClips();
  }
}

/**
 * Enters inline edit mode for the selected clip item.
 */
function editSelected() {
  const clip = state.clips[state.selectedIndex];
  if (!clip || state.editingId) return;

  state.editingId = clip.id;
  const items  = clipsList.querySelectorAll('.clip-item');
  const itemEl = items[state.selectedIndex];
  if (!itemEl) return;

  const textEl = itemEl.querySelector('.clip-text');
  if (!textEl) return;

  const textarea = document.createElement('textarea');
  textarea.className = 'clip-edit-textarea';
  textarea.value     = clip.text;
  textEl.replaceWith(textarea);

  const actions = document.createElement('div');
  actions.className = 'clip-edit-actions';
  actions.innerHTML =
    '<button class="btn-sm primary" data-action="save">Save</button>' +
    '<button class="btn-sm" data-action="cancel">Cancel</button>';
  itemEl.appendChild(actions);

  textarea.focus();
  textarea.setSelectionRange(textarea.value.length, textarea.value.length);

  const save = async () => {
    const newText = textarea.value.trim();
    if (newText && newText !== clip.text) {
      await sendMessage({ type: 'EDIT_CLIP', id: clip.id, text: newText });
      clip.text = newText;
    }
    state.editingId = null;
    renderClips();
  };

  const cancel = () => {
    state.editingId = null;
    renderClips();
  };

  actions.addEventListener('click', (e) => {
    const action = e.target.closest('[data-action]')?.dataset.action;
    if (action === 'save')   save();
    if (action === 'cancel') cancel();
  });

  textarea.addEventListener('keydown', (e) => {
    e.stopPropagation(); // Don't propagate to global handler
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); save(); }
    if (e.key === 'Escape') cancel();
  });
}

/**
 * Shows a space-picker dropdown anchored to the selected clip item.
 */
function showSpacePicker() {
  const clip   = state.clips[state.selectedIndex];
  if (!clip) return;

  // Remove any existing picker
  document.querySelector('.space-picker')?.remove();

  const items  = clipsList.querySelectorAll('.clip-item');
  const itemEl = items[state.selectedIndex];
  if (!itemEl) return;

  const picker = document.createElement('div');
  picker.className = 'space-picker';
  picker.setAttribute('role', 'listbox');
  picker.setAttribute('aria-label', 'Move to space');

  state.spaces.forEach((space) => {
    const opt = document.createElement('div');
    opt.className = `space-picker-item${clip.spaceId === space.id ? ' active' : ''}`;
    opt.setAttribute('role', 'option');
    opt.innerHTML = `<span>${space.icon}</span>${esc(space.name)}`;
    opt.addEventListener('click', async (e) => {
      e.stopPropagation();
      await sendMessage({ type: 'MOVE_TO_SPACE', clipId: clip.id, spaceId: space.id });
      clip.spaceId = space.id !== 'all' ? space.id : null;
      picker.remove();
    });
    picker.appendChild(opt);
  });

  itemEl.style.position = 'relative';
  itemEl.appendChild(picker);

  const closeOutside = (e) => {
    if (!picker.contains(e.target)) {
      picker.remove();
      document.removeEventListener('click', closeOutside);
    }
  };
  setTimeout(() => document.addEventListener('click', closeOutside), 0);
}

// ── Space & category navigation ───────────────────────────────────────────────

/**
 * Switches to the specified space and reloads clips.
 * @param {string} spaceId
 * @returns {Promise<void>}
 */
async function switchSpace(spaceId) {
  state.activeSpace = spaceId;
  await sendMessage({ type: 'SET_ACTIVE_SPACE', spaceId });
  renderSpaces();
  await loadClips();
}

/**
 * Cycles through the spaces tab list.
 * @param {number} direction - +1 forward, -1 backward.
 */
async function cycleSpace(direction) {
  const idx  = state.spaces.findIndex((s) => s.id === state.activeSpace);
  const next = (idx + direction + state.spaces.length) % state.spaces.length;
  await switchSpace(state.spaces[next].id);
}

/**
 * Activates or deactivates a category filter.
 * @param {string} category
 */
async function toggleCategory(category) {
  state.activeCategory = state.activeCategory === category ? null : category;
  renderCategoryFilter();
  await loadClips();
}

// ── Settings ──────────────────────────────────────────────────────────────────

/** Opens the settings panel and populates current values. */
function openSettings() {
  settingCapture.checked  = state.settings.captureEnabled !== false;
  settingTheme.value      = state.settings.theme ?? 'system';
  settingExcluded.value   = (state.settings.excludedDomains ?? []).join('\n');
  settingsPanel.classList.remove('hidden');
}

/** Closes the settings panel. */
function closeSettings() {
  settingsPanel.classList.add('hidden');
}

/** Reads the form, persists settings, and closes the panel. */
async function saveSettings() {
  const excludedDomains = settingExcluded.value
    .split(/[\n,]+/)
    .map((s) => s.trim())
    .filter(Boolean);

  const updated = {
    captureEnabled: settingCapture.checked,
    theme:          settingTheme.value,
    excludedDomains,
  };

  await sendMessage({ type: 'UPDATE_SETTINGS', settings: updated });
  state.settings = { ...state.settings, ...updated };

  applyTheme(updated.theme);
  updateStatus();
  closeSettings();
}

// ── Search ────────────────────────────────────────────────────────────────────

let searchTimer = null;

/** Handles search input with 150ms debounce. */
function handleSearchInput() {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(async () => {
    state.searchQuery   = searchInput.value;
    state.selectedIndex = 0;
    await loadClips();
  }, 150);
}

// ── Keyboard navigation ───────────────────────────────────────────────────────

/**
 * Moves the selected index by `direction` and wraps around.
 * Triggers lazy loading when the end is reached.
 * @param {number} direction
 */
function moveSelection(direction) {
  const len = state.clips.length;
  if (len === 0) return;
  state.selectedIndex = (state.selectedIndex + direction + len) % len;
  updateSelection();
  // Trigger load-more when near the bottom
  if (direction > 0 && state.selectedIndex >= len - 3 && len < state.total) {
    loadMore();
  }
}

/**
 * Global keydown handler. Drives all keyboard navigation for the popup.
 * @param {KeyboardEvent} e
 */
async function handleKeyDown(e) {
  // When in edit mode, let the textarea's own keydown handler run
  if (state.editingId) return;

  const inSearch = document.activeElement === searchInput;

  switch (e.key) {
    case 'ArrowDown':
      e.preventDefault();
      moveSelection(1);
      break;

    case 'ArrowUp':
      e.preventDefault();
      moveSelection(-1);
      break;

    case 'Enter':
      e.preventDefault();
      if (e.ctrlKey || e.metaKey) {
        await copySelected();
      } else {
        await pasteSelected();
      }
      break;

    case '/':
      if (!inSearch) {
        e.preventDefault();
        searchInput.focus();
        searchInput.select();
      }
      break;

    case 'Tab':
      e.preventDefault();
      await cycleSpace(e.shiftKey ? -1 : 1);
      break;

    case 'p':
    case 'P':
      if (!inSearch) { e.preventDefault(); await pinSelected(); }
      break;

    case 'd':
    case 'D':
    case 'Delete':
      if (!inSearch) { e.preventDefault(); await deleteSelected(); }
      break;

    case 'e':
    case 'E':
      if (!inSearch) { e.preventDefault(); editSelected(); }
      break;

    case 's':
    case 'S':
      if (!inSearch) { e.preventDefault(); showSpacePicker(); }
      break;

    case 'Escape':
      if (document.querySelector('.space-picker')) {
        document.querySelector('.space-picker').remove();
      } else if (!settingsPanel.classList.contains('hidden')) {
        closeSettings();
      } else if (inSearch && searchInput.value) {
        searchInput.value = '';
        state.searchQuery = '';
        await loadClips();
      } else {
        window.close();
      }
      break;
  }
}

// ── Intersection observer for lazy loading ────────────────────────────────────

const lazyObserver = new IntersectionObserver(
  (entries) => { if (entries[0].isIntersecting) loadMore(); },
  { threshold: 0.1 },
);

// ── Bootstrap ─────────────────────────────────────────────────────────────────

/**
 * Initializes the popup.
 * Fetches initial data in parallel, renders UI, wires up event listeners.
 */
async function init() {
  // Parallel fetch of all bootstrap data
  const [settingsResp, spacesResp, activeSpaceResp] = await Promise.all([
    sendMessage({ type: 'GET_SETTINGS'     }),
    sendMessage({ type: 'GET_SPACES'       }),
    sendMessage({ type: 'GET_ACTIVE_SPACE' }),
  ]);

  state.settings    = settingsResp?.settings  ?? {};
  state.spaces      = spacesResp?.spaces      ?? [];
  state.activeSpace = activeSpaceResp?.activeSpace ?? 'all';

  // Apply persisted theme before first render
  applyTheme(state.settings.theme ?? 'system');

  // Render structure
  renderSpaces();
  renderCategoryFilter();

  // Fetch and render first page of clips
  await loadClips();

  // Wire up lazy-load sentinel
  lazyObserver.observe(loadMoreSentinel);

  // Event listeners
  searchInput.addEventListener('input', handleSearchInput);
  document.addEventListener('keydown', handleKeyDown);
  settingsBtn.addEventListener('click', openSettings);
  settingsClose.addEventListener('click', closeSettings);
  settingsSave.addEventListener('click', saveSettings);

  // Auto-focus the search input for immediate keyboard control
  searchInput.focus();
}

init().catch((err) => console.error('[Stashboard] Init error:', err));
