/**
 * @fileoverview Stashboard service worker — manages clip storage, spaces, and paste injection.
 * Runs as a Manifest V3 background service worker (no DOM access).
 */

'use strict';

const MAX_LOCAL_ITEMS = 500;

/** Built-in default spaces installed on first run. */
const DEFAULT_SPACES = [
  { id: 'all',      name: 'All',      builtin: true,  icon: '📋' },
  { id: 'work',     name: 'Work',     builtin: false, icon: '💼' },
  { id: 'personal', name: 'Personal', builtin: false, icon: '🏠' },
];

/** Default user settings. */
const DEFAULT_SETTINGS = {
  excludedDomains: [],
  maxItems:        MAX_LOCAL_ITEMS,
  captureEnabled:  true,
  theme:           'system',
};

// ── Storage helpers ───────────────────────────────────────────────────────────

/**
 * Reads the full storage state.
 * @returns {Promise<{clips: Array, spaces: Array, activeSpace: string, settings: Object}>}
 */
async function loadStorage() {
  return new Promise((resolve) => {
    chrome.storage.local.get(['clips', 'spaces', 'activeSpace', 'settings'], (result) => {
      resolve({
        clips:       result.clips       ?? [],
        spaces:      result.spaces      ?? DEFAULT_SPACES,
        activeSpace: result.activeSpace ?? 'all',
        settings:    { ...DEFAULT_SETTINGS, ...(result.settings ?? {}) },
      });
    });
  });
}

/**
 * Persists a partial update to chrome.storage.local.
 * @param {Object} data - Key/value pairs to save.
 * @returns {Promise<void>}
 */
async function saveStorage(data) {
  return new Promise((resolve) => chrome.storage.local.set(data, resolve));
}

// ── Clip management ───────────────────────────────────────────────────────────

/**
 * Saves a new clip to storage.
 * - Deduplicates: if the same text already exists, increments copyCount and moves it to the front.
 * - Respects the maxItems cap while always preserving pinned items.
 * - Auto-assigns the clip to the currently active space (unless active space is 'all').
 *
 * @param {Object} clip - The clip object from the content script.
 * @returns {Promise<void>}
 */
async function saveClip(clip) {
  const { clips, activeSpace, settings } = await loadStorage();
  const maxItems = settings.maxItems ?? MAX_LOCAL_ITEMS;

  // Deduplication check
  const existingIndex = clips.findIndex((c) => c.text === clip.text);
  if (existingIndex !== -1) {
    const existing = clips.splice(existingIndex, 1)[0];
    existing.copyCount   = (existing.copyCount ?? 1) + 1;
    existing.timestamp   = clip.timestamp;
    existing.source      = clip.source;
    existing.sourceTitle = clip.sourceTitle;
    clips.unshift(existing);
    await saveStorage({ clips });
    return;
  }

  // Assign space and defaults
  clip.spaceId   = activeSpace !== 'all' ? activeSpace : null;
  clip.pinned    = false;
  clip.copyCount = 1;
  clips.unshift(clip);

  // Enforce cap — never evict pinned items
  if (clips.length > maxItems) {
    const excess = clips.length - maxItems;
    let removed = 0;
    for (let i = clips.length - 1; i >= 0 && removed < excess; i--) {
      if (!clips[i].pinned) {
        clips.splice(i, 1);
        removed++;
      }
    }
  }

  await saveStorage({ clips });
  resetCursor(); // New copy → reset navigation back to index 0
}

/**
 * Returns a paginated, filtered, and sorted slice of clips.
 * Pinned items are always sorted to the front within results.
 *
 * @param {Object}  opts
 * @param {string}  [opts.spaceId]  - Filter by space ('all' = no filter).
 * @param {string}  [opts.category] - Filter by category.
 * @param {string}  [opts.query]    - Full-text search query.
 * @param {number}  [opts.offset]   - Pagination offset.
 * @param {number}  [opts.limit]    - Max results to return.
 * @returns {Promise<{clips: Array, total: number}>}
 */
async function getClips({ spaceId, category, query, offset = 0, limit = 30 } = {}) {
  const { clips } = await loadStorage();
  let filtered = clips;

  if (spaceId && spaceId !== 'all') {
    filtered = filtered.filter((c) => c.spaceId === spaceId);
  }

  if (category) {
    filtered = filtered.filter((c) => c.category === category);
  }

  if (query && query.trim()) {
    const q = query.trim().toLowerCase();
    filtered = filtered.filter(
      (c) =>
        c.text.toLowerCase().includes(q) ||
        (c.sourceTitle ?? '').toLowerCase().includes(q) ||
        (c.source ?? '').toLowerCase().includes(q),
    );
  }

  // Pinned first, then newest
  filtered.sort((a, b) => {
    if (a.pinned && !b.pinned) return -1;
    if (!a.pinned && b.pinned) return 1;
    return b.timestamp - a.timestamp;
  });

  return {
    clips: filtered.slice(offset, offset + limit),
    total: filtered.length,
  };
}

/**
 * Deletes a clip by ID.
 * @param {string} id
 * @returns {Promise<boolean>} True if the clip was found and removed.
 */
async function deleteClip(id) {
  const { clips } = await loadStorage();
  const idx = clips.findIndex((c) => c.id === id);
  if (idx === -1) return false;
  clips.splice(idx, 1);
  await saveStorage({ clips });
  return true;
}

/**
 * Toggles the pinned state of a clip.
 * @param {string} id
 * @returns {Promise<boolean|null>} New pinned value, or null if not found.
 */
async function togglePin(id) {
  const { clips } = await loadStorage();
  const clip = clips.find((c) => c.id === id);
  if (!clip) return null;
  clip.pinned = !clip.pinned;
  await saveStorage({ clips });
  return clip.pinned;
}

/**
 * Updates the text content of a clip.
 * @param {string} id
 * @param {string} newText
 * @returns {Promise<boolean>}
 */
async function editClip(id, newText) {
  const { clips } = await loadStorage();
  const clip = clips.find((c) => c.id === id);
  if (!clip) return false;
  clip.text     = newText;
  clip.editedAt = Date.now();
  await saveStorage({ clips });
  return true;
}

/**
 * Moves a clip to a different space.
 * @param {string} clipId
 * @param {string} spaceId - Pass 'all' to remove the clip from any specific space.
 * @returns {Promise<boolean>}
 */
async function moveToSpace(clipId, spaceId) {
  const { clips, spaces } = await loadStorage();
  const clip = clips.find((c) => c.id === clipId);
  if (!clip) return false;
  if (spaceId !== 'all' && !spaces.find((s) => s.id === spaceId)) return false;
  clip.spaceId = spaceId !== 'all' ? spaceId : null;
  await saveStorage({ clips });
  return true;
}

// ── Space management ──────────────────────────────────────────────────────────

/**
 * Returns all spaces.
 * @returns {Promise<Array>}
 */
async function getSpaces() {
  const { spaces } = await loadStorage();
  return spaces;
}

/**
 * Creates a new custom space.
 * @param {{name: string, icon?: string}} opts
 * @returns {Promise<Object>} The newly created space object.
 */
async function createSpace({ name, icon = '📁' }) {
  const { spaces } = await loadStorage();
  const newSpace = {
    id:        crypto.randomUUID(),
    name,
    icon,
    builtin:   false,
    createdAt: Date.now(),
  };
  spaces.push(newSpace);
  await saveStorage({ spaces });
  return newSpace;
}

/**
 * Deletes a non-builtin space and unassigns its clips.
 * @param {string} spaceId
 * @returns {Promise<boolean>}
 */
async function deleteSpace(spaceId) {
  const { spaces, clips } = await loadStorage();
  const idx = spaces.findIndex((s) => s.id === spaceId);
  if (idx === -1) return false;
  if (spaces[idx].builtin) return false;
  spaces.splice(idx, 1);
  clips.forEach((c) => { if (c.spaceId === spaceId) c.spaceId = null; });
  await saveStorage({ spaces, clips });
  return true;
}

// ── Paste injection ───────────────────────────────────────────────────────────

/**
 * Injects the given text into the currently focused element of the active tab.
 * Handles both contentEditable elements and standard input/textarea controls.
 * Dispatches 'input' and 'change' events so frameworks (React, Vue, etc.) pick up the change.
 *
 * @param {string} text - The text to inject.
 * @returns {Promise<{success: boolean, error?: string}>}
 */
async function pasteText(text) {
  const [tab] = await chrome.tabs.query({ active: true, lastFocusedWindow: true });
  if (!tab?.id) return { success: false, error: 'No active tab found' };

  try {
    const results = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: (textToInsert) => {
        const el = document.activeElement;
        if (!el) return { ok: false, reason: 'no active element' };

        if (el.isContentEditable) {
          document.execCommand('insertText', false, textToInsert);
          el.dispatchEvent(new Event('input', { bubbles: true }));
          return { ok: true };
        }

        if (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA') {
          const start = el.selectionStart ?? el.value.length;
          const end   = el.selectionEnd   ?? el.value.length;
          el.value = el.value.slice(0, start) + textToInsert + el.value.slice(end);
          el.selectionStart = el.selectionEnd = start + textToInsert.length;
          el.dispatchEvent(new Event('input',  { bubbles: true }));
          el.dispatchEvent(new Event('change', { bubbles: true }));
          return { ok: true };
        }

        return { ok: false, reason: 'unsupported element type: ' + el.tagName };
      },
      args: [text],
    });

    const result = results?.[0]?.result;
    if (result?.ok) return { success: true };
    return { success: false, error: result?.reason ?? 'unknown' };
  } catch (err) {
    return { success: false, error: err.message };
  }
}

// ── Message router ────────────────────────────────────────────────────────────

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  const dispatch = async () => {
    switch (message.type) {
      case 'NEW_CLIP':
        await saveClip(message.clip);
        return { success: true };

      case 'GET_CLIPS':
        return getClips(message.options ?? {});

      case 'DELETE_CLIP':
        return { success: await deleteClip(message.id) };

      case 'PIN_CLIP':
        return { pinned: await togglePin(message.id) };

      case 'EDIT_CLIP':
        return { success: await editClip(message.id, message.text) };

      case 'GET_SPACES':
        return { spaces: await getSpaces() };

      case 'CREATE_SPACE':
        return { space: await createSpace(message.space) };

      case 'DELETE_SPACE':
        return { success: await deleteSpace(message.spaceId) };

      case 'MOVE_TO_SPACE':
        return { success: await moveToSpace(message.clipId, message.spaceId) };

      case 'PASTE_TEXT':
        return pasteText(message.text);

      case 'SEARCH_CLIPS':
        return getClips({ query: message.query, offset: message.offset, limit: message.limit });

      case 'GET_ACTIVE_SPACE': {
        const { activeSpace } = await loadStorage();
        return { activeSpace };
      }

      case 'SET_ACTIVE_SPACE':
        await saveStorage({ activeSpace: message.spaceId });
        return { success: true };

      case 'GET_SETTINGS': {
        const { settings } = await loadStorage();
        return { settings };
      }

      case 'UPDATE_SETTINGS': {
        const current = await loadStorage();
        await saveStorage({ settings: { ...current.settings, ...message.settings } });
        return { success: true };
      }

      default:
        return { error: `Unknown message type: ${message.type}` };
    }
  };

  dispatch().then(sendResponse).catch((err) => sendResponse({ error: err.message }));
  return true; // Keep port open for async sendResponse
});

// ── Clipboard cursor (in-memory, resets when service worker restarts) ─────────

/**
 * Tracks the current position in clipboard history for arrow-key navigation.
 * 0 = most recent clip. Increments on paste_prev, decrements on paste_next.
 */
let clipCursor = 0;

/**
 * Resets the clipboard cursor to 0 whenever a new clip is saved.
 * Called from saveClip so navigation always starts from the latest item.
 */
function resetCursor() {
  clipCursor = 0;
}

// ── Quick-paste keyboard commands ─────────────────────────────────────────────

chrome.commands.onCommand.addListener(async (command) => {
  // Cycle backward through history (older items)
  if (command === 'paste_prev') {
    const { clips, total } = await getClips({ offset: 0, limit: 50 });
    if (clips.length === 0) return;
    clipCursor = Math.min(clipCursor + 1, total - 1);
    const clip = clips[Math.min(clipCursor, clips.length - 1)];
    await pasteText(clip.text);
    return;
  }

  // Cycle forward through history (newer items)
  if (command === 'paste_next') {
    const { clips } = await getClips({ offset: 0, limit: 50 });
    if (clips.length === 0) return;
    clipCursor = Math.max(clipCursor - 1, 0);
    const clip = clips[clipCursor];
    await pasteText(clip.text);
    return;
  }

  // Positional quick-paste: quick_paste_1 pastes the most recent clip, etc.
  const match = command.match(/^quick_paste_(\d+)$/);
  if (!match) return;

  const n = parseInt(match[1], 10) - 1; // Convert 1-indexed to 0-indexed
  const { clips } = await getClips({ offset: 0, limit: 5 });
  if (n < clips.length) {
    await pasteText(clips[n].text);
  }
});

// ── First-run initialization ──────────────────────────────────────────────────

chrome.runtime.onInstalled.addListener(async (details) => {
  if (details.reason === 'install') {
    await saveStorage({
      clips:       [],
      spaces:      DEFAULT_SPACES,
      activeSpace: 'all',
      settings:    DEFAULT_SETTINGS,
    });
  }
});
