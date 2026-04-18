/**
 * @fileoverview Stashboard content script — captures copy events on all pages.
 * Injected at document_end on all URLs via manifest.json content_scripts.
 * SECURITY: Never captures password fields or excluded domains.
 */

'use strict';

/** Category detection regex patterns. Order matters — more specific patterns first. */
const CATEGORY_PATTERNS = {
  email:      /^[\w.+-]+@[\w-]+(?:\.[\w-]+)+$/,
  color_hex:  /^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$/,
  ip_address: /^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$/,
  url:        /^https?:\/\//,
  address:    /^\d+\s+[\w\s]+(st(?:reet)?|nd|rd|th|ave(?:nue)?|blvd|dr(?:ive)?|ln|ct|way|pl(?:ace)?|rd|road)\b/i,
  phone:      /^\+?[-\d\s()+]{7,20}$/,
};

/**
 * Detects the semantic category of copied text.
 * @param {string} text - The copied text.
 * @returns {string} One of: email, phone, url, address, code, color_hex, json, ip_address, text.
 */
function detectCategory(text) {
  const trimmed = text.trim();

  if (CATEGORY_PATTERNS.email.test(trimmed))      return 'email';
  if (CATEGORY_PATTERNS.color_hex.test(trimmed))  return 'color_hex';
  if (CATEGORY_PATTERNS.ip_address.test(trimmed)) return 'ip_address';
  if (CATEGORY_PATTERNS.url.test(trimmed))        return 'url';
  if (CATEGORY_PATTERNS.address.test(trimmed))    return 'address';
  if (CATEGORY_PATTERNS.phone.test(trimmed))      return 'phone';

  // JSON: starts with { or [ and parses successfully
  if (/^\s*[{[]/.test(trimmed)) {
    try {
      JSON.parse(trimmed);
      return 'json';
    } catch (_) {
      // Not valid JSON — fall through
    }
  }

  // Code: has common programming characters AND more than 2 newlines
  const hasCodeChars = /[{};()=<>]/.test(trimmed);
  const newlineCount = (trimmed.match(/\n/g) || []).length;
  if (hasCodeChars && newlineCount > 2) return 'code';

  return 'text';
}

/**
 * Checks whether the given element is a password input field.
 * Includes aria-label checks as a secondary signal.
 * @param {Element|null} el - The element to check.
 * @returns {boolean}
 */
function isPasswordField(el) {
  if (!el) return false;
  if (el instanceof HTMLInputElement && el.type === 'password') return true;
  // Also guard on aria-labels that hint at password
  const ariaLabel = (el.getAttribute('aria-label') || '').toLowerCase();
  const placeholder = (el.getAttribute('placeholder') || '').toLowerCase();
  if (ariaLabel.includes('password') || placeholder.includes('password')) return true;
  return false;
}

/**
 * Resolves the list of excluded domains from extension storage.
 * @returns {Promise<string[]>}
 */
async function getExcludedDomains() {
  return new Promise((resolve) => {
    chrome.storage.local.get(['settings'], (result) => {
      resolve(result.settings?.excludedDomains ?? []);
    });
  });
}

/**
 * Checks whether clipboard capturing is currently enabled.
 * @returns {Promise<boolean>}
 */
async function isCaptureEnabled() {
  return new Promise((resolve) => {
    chrome.storage.local.get(['settings'], (result) => {
      resolve(result.settings?.captureEnabled !== false);
    });
  });
}

/**
 * Handles the document 'copy' event.
 * Reads the clipboard after the event settles, builds a clip object,
 * and dispatches it to the background service worker.
 */
async function handleCopy() {
  // Guard: never capture from password fields
  const active = document.activeElement;
  if (isPasswordField(active)) return;

  // Guard: capturing must be enabled
  if (!(await isCaptureEnabled())) return;

  // Guard: excluded domains
  const excludedDomains = await getExcludedDomains();
  const host = window.location.hostname;
  if (excludedDomains.some((d) => host === d || host.endsWith(`.${d}`))) return;

  // Wait for clipboard to settle after the copy event fires
  await new Promise((resolve) => setTimeout(resolve, 100));

  let text;
  try {
    text = await navigator.clipboard.readText();
  } catch (_err) {
    // Clipboard read may fail if the page lost focus; silently skip
    return;
  }

  if (!text || !text.trim()) return;

  /** @type {StashClip} */
  const clip = {
    id:          crypto.randomUUID(),
    text:        text,
    timestamp:   Date.now(),
    source:      window.location.href,
    sourceTitle: document.title || '',
    category:    detectCategory(text),
  };

  chrome.runtime.sendMessage({ type: 'NEW_CLIP', clip }, () => {
    // Ignore chrome.runtime.lastError — background may restart between copies
    void chrome.runtime.lastError;
  });
}

document.addEventListener('copy', handleCopy);
