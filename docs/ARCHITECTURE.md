# Stashboard Architecture

## Overview

Stashboard is split into two layers:

- **Chrome Extension (JavaScript)** — thin client, runs entirely in the browser
- **Python Backend (FastAPI)** — activated in Phase 3 for sync, AI, and teams

This split is intentional. The extension must work **completely offline** with
no round-trip latency. The backend provides persistence beyond a single browser,
semantic search, and team sharing.

---

## System Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                     Chrome Extension                         │
│                                                             │
│  ┌──────────────┐  copy event  ┌──────────────────────┐    │
│  │  content.js  │ ────────────▶│   background.js      │    │
│  │ (all pages)  │              │   (service worker)   │    │
│  └──────────────┘              │                      │    │
│                                │  chrome.storage.local│    │
│  ┌──────────────┐  messages   │  (up to 500 clips)   │    │
│  │   popup.js   │◀───────────▶│                      │    │
│  │  (popup UI)  │              │  Paste injection via │    │
│  └──────────────┘              │  chrome.scripting    │    │
│                                └──────────┬───────────┘    │
└───────────────────────────────────────────│─────────────────┘
                                            │ HTTP (Phase 3+)
                                            ▼
┌─────────────────────────────────────────────────────────────┐
│                     Python Backend                           │
│                                                             │
│  ┌──────────────┐     ┌──────────────┐   ┌──────────────┐  │
│  │   FastAPI    │────▶│  SQLAlchemy  │──▶│  PostgreSQL  │  │
│  │   Routes     │     │  (async)     │   │  + pgvector  │  │
│  └──────┬───────┘     └──────────────┘   └──────────────┘  │
│         │                                                    │
│         │ enqueue                         ┌──────────────┐  │
│         ▼                                 │    Redis     │  │
│  ┌──────────────┐                         └──────┬───────┘  │
│  │    Celery    │◀────────────────────────────────┘          │
│  │   Workers    │                                            │
│  │              │  sentence-transformers                     │
│  │  generate_   │  all-MiniLM-L6-v2 (384 dim)               │
│  │  embedding() │                                            │
│  └──────────────┘                                            │
└─────────────────────────────────────────────────────────────┘
```

---

## Why Two Languages?

| Concern | JavaScript (Extension) | Python (Backend) |
|---|---|---|
| Clipboard capture | Native (copy event API) | N/A |
| Paste injection | Native (chrome.scripting) | N/A |
| Offline-first storage | chrome.storage.local | N/A |
| ML embeddings | Not practical | sentence-transformers |
| Vector search | N/A | pgvector |
| Auth / billing | N/A | jose, passlib, Stripe |
| Multi-device sync | N/A | PostgreSQL |

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Liveness check |
| POST | `/api/auth/register` | Email/password registration |
| POST | `/api/auth/login` | Login, returns JWT |
| GET | `/api/clips/` | List clips (paginated, filterable) |
| POST | `/api/clips/` | Create clip |
| GET | `/api/clips/{id}` | Get single clip |
| PATCH | `/api/clips/{id}` | Update clip |
| DELETE | `/api/clips/{id}` | Delete clip |
| POST | `/api/clips/{id}/pin` | Toggle pin |
| POST | `/api/clips/search` | Full-text or semantic search |
| GET | `/api/spaces/` | List spaces |
| POST | `/api/spaces/` | Create space |
| PATCH | `/api/spaces/{id}` | Update space |
| DELETE | `/api/spaces/{id}` | Delete space |
| POST | `/api/sync/batch` | Bulk sync from extension |

---

## Data Flow: Clipboard Capture

1. User presses Ctrl+C on any webpage
2. `content.js` receives the `copy` DOM event
3. Waits 100ms for the clipboard to settle
4. Reads clipboard text via `navigator.clipboard.readText()`
5. Guards: password fields, excluded domains, capture disabled
6. Detects category via regex
7. Sends `NEW_CLIP` message to `background.js`
8. Background deduplicates, stores in `chrome.storage.local`

## Data Flow: Paste

1. User opens popup (Ctrl+Shift+V) or presses quick-paste shortcut
2. Selects item with arrow keys, presses Enter
3. Popup sends `PASTE_TEXT` to background
4. Background calls `chrome.scripting.executeScript` on active tab
5. Injected function finds `document.activeElement`
6. Injects text into `input`/`textarea` (via `.value` splice) or
   `contentEditable` (via `execCommand('insertText')`)
7. Fires `input` + `change` events so frameworks (React, Vue) see the change
8. Popup calls `window.close()`

---

## Storage Schema (chrome.storage.local)

```json
{
  "clips": [
    {
      "id": "uuid",
      "text": "copied text",
      "timestamp": 1700000000000,
      "source": "https://example.com/page",
      "sourceTitle": "Page Title",
      "category": "email",
      "spaceId": "work",
      "pinned": false,
      "copyCount": 1,
      "editedAt": null
    }
  ],
  "spaces": [
    { "id": "all",  "name": "All",      "builtin": true,  "icon": "📋" },
    { "id": "work", "name": "Work",     "builtin": false, "icon": "💼" },
    { "id": "personal", "name": "Personal", "builtin": false, "icon": "🏠" }
  ],
  "activeSpace": "all",
  "settings": {
    "excludedDomains": [],
    "maxItems": 500,
    "captureEnabled": true,
    "theme": "system"
  }
}
```
