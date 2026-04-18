# Stashboard

**Your second brain for everything you copy.**

A keyboard-first Chrome extension that turns your clipboard into a searchable, organized, AI-ready memory layer. Never lose a copied snippet again.

---

## Features

- **Automatic capture** — Every copy is saved with timestamp, source URL, page title, and auto-detected category
- **9 smart categories** — Email, phone, URL, code, JSON, color hex, address, IP address, and generic text — detected instantly with zero configuration
- **Keyboard-first UX** — Every action is reachable without a mouse. Open popup → navigate → paste in under a second
- **Fast popup** — Renders in under 100ms with lazy loading (30 clips at a time)
- **Quick-paste shortcuts** — `Ctrl+Shift+1–5` paste your top 5 clips directly into any input without opening the popup
- **Spaces** — Organize clips into compartments: Work, Personal, or any custom space
- **Pin, edit, delete** — Full clip management from the keyboard
- **Light/dark mode** — Follows your system preference, with manual override
- **Privacy-first** — Password fields are never captured. Excluded domains are respected. All data stays local in Phase 1.

---

## Quick Start — Load in Chrome

1. Clone or download this repository
2. Open Chrome → `chrome://extensions`
3. Enable **Developer mode** (toggle in the top right)
4. Click **Load unpacked**
5. Select the `stashboard/extension/` folder
6. The Stashboard icon appears in your toolbar

**Open the popup:** Click the icon or press `Ctrl+Shift+V` (`⌘+Shift+V` on Mac)

---

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+Shift+V` | Open popup |
| `Ctrl+Shift+1–5` | Quick paste item 1–5 (no popup needed) |
| `↑` / `↓` | Navigate clips |
| `Enter` | Paste selected clip |
| `Ctrl+Enter` | Copy to clipboard (no paste) |
| `/` | Focus search |
| `Tab` / `Shift+Tab` | Cycle through spaces |
| `P` | Pin / unpin |
| `D` / `Delete` | Delete clip |
| `E` | Inline edit |
| `S` | Move to space |
| `Esc` | Close popup |

See [docs/KEYBOARD_SHORTCUTS.md](docs/KEYBOARD_SHORTCUTS.md) for the full reference.

---

## Tech Stack

### Extension (Phase 1 — active now)
- Manifest V3 Chrome Extension
- Vanilla JavaScript (no build step)
- `chrome.storage.local` for persistence
- `chrome.scripting` for paste injection
- `navigator.clipboard` API for clipboard reads

### Backend (Phase 3+)
- **Python 3.12** + **FastAPI** for the API layer
- **PostgreSQL** with **pgvector** for semantic search
- **SQLAlchemy 2.0** (async) for ORM
- **Alembic** for database migrations
- **Celery + Redis** for async embedding generation
- **sentence-transformers** (all-MiniLM-L6-v2) for 384-dim embeddings
- **Pydantic v2** for validation

---

## Project Structure

```
stashboard/
├── extension/          # Chrome Extension (Manifest V3) — works today
│   ├── manifest.json
│   ├── background.js   # Service worker: storage, paste, commands
│   ├── content.js      # Captures copy events on all pages
│   └── popup/          # Popup UI: search, keyboard nav, settings
├── backend/            # Python backend — activates in Phase 3
│   └── app/            # FastAPI app, models, services, AI
├── docs/               # Architecture, shortcuts, roadmap
└── .github/workflows/  # CI: Python ruff + JS eslint
```

---

## Architecture

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for a full system diagram and data flow documentation.

## Roadmap

See [docs/ROADMAP.md](docs/ROADMAP.md) for the full 6-phase plan from local MVP to teams and AI.

---

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feat/your-feature`
3. Make your changes
4. Commit: `git commit -m "feat: describe your change"`
5. Push and open a Pull Request

Please ensure your JS passes `eslint` and Python passes `ruff` before opening a PR.

---

## License

MIT — see [LICENSE](LICENSE).
