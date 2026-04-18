# Stashboard Roadmap

## Phase 1 — Local MVP (Weeks 1–3) ✅

**Goal:** A fully functional Chrome extension that works 100% offline.

- [x] Manifest V3 Chrome extension
- [x] Copy event capture on all pages (with password field guard)
- [x] `chrome.storage.local` persistence (max 500 clips)
- [x] Auto-detection of 9 categories: email, phone, url, address, code, color_hex, json, ip_address, text
- [x] Popup with search, space tabs, category filter
- [x] Full keyboard navigation: ↑↓ navigate, Enter paste, / search, Tab spaces, P pin, D delete, E edit, S move
- [x] Inline clip editing
- [x] Pin/unpin, delete with confirmation for pinned items
- [x] Space management (All, Work, Personal)
- [x] Quick-paste Ctrl+Shift+1–5 shortcuts
- [x] Light/dark mode with system preference detection
- [x] Lazy loading (30 clips at a time via IntersectionObserver)
- [x] Python backend scaffold (models, schemas, routes — not yet running)

---

## Phase 2 — Keyboard UX & Polish (Weeks 4–5)

**Goal:** Make the keyboard experience feel native and delightful.

- [ ] Space creation/deletion from the popup
- [ ] Drag-to-reorder clips (mouse fallback for accessibility)
- [ ] Color swatch preview for `color_hex` category items
- [ ] Syntax highlighting preview for `code` and `json` items (Prism.js)
- [ ] Favicon caching (avoid re-fetching on every popup open)
- [ ] Onboarding tour on first install (highlight keyboard shortcuts)
- [ ] Extension options page (full settings, excluded domains list)
- [ ] Context menu: right-click → "Save to Stashboard" for selected text
- [ ] "Copy count" badge tooltip showing last copied timestamp
- [ ] Performance profiling — ensure popup renders under 80ms

---

## Phase 3 — Python Backend & Sync (Weeks 6–9)

**Goal:** Cross-device sync via a FastAPI + PostgreSQL backend.

- [ ] Deploy FastAPI backend (Docker + Fly.io or Railway)
- [ ] PostgreSQL with pgvector extension
- [ ] Alembic migration system
- [ ] JWT authentication (email/password)
- [ ] Google OAuth login
- [ ] Extension sync: POST /api/sync/batch on a 30-second interval
- [ ] Conflict resolution: server wins on edit conflicts; client wins on new clips
- [ ] Account page in extension popup
- [ ] Data export: JSON download of all clips

---

## Phase 4 — AI Semantic Search (Weeks 10–13)

**Goal:** Find anything, even without exact keywords.

- [ ] Celery worker deployment for async embedding generation
- [ ] sentence-transformers all-MiniLM-L6-v2 (384-dim) embeddings
- [ ] pgvector cosine similarity search
- [ ] Recency-blended ranking (0.7 semantic + 0.3 recency)
- [ ] "Smart search" toggle in popup (keyword vs. semantic)
- [ ] Auto-tag generation (LLM-powered tag suggestion)
- [ ] Duplicate detection across similar (not identical) text
- [ ] "Related clips" panel: show similar clips when a clip is selected

---

## Phase 5 — Full Web App (Weeks 14–18)

**Goal:** A full dashboard at `stashboard.app` for power users.

- [ ] Next.js web app
- [ ] Full-page clipboard history with infinite scroll
- [ ] Advanced filter/sort UI
- [ ] Snippet library (curated, named, shortcut-accessible)
- [ ] Todo list: promote any clip to a task
- [ ] Browser history integration (optional)
- [ ] Bulk operations (delete all in space, export selected, etc.)
- [ ] Keyboard shortcuts reference page in the web app
- [ ] Mobile-responsive layout

---

## Phase 6 — Teams & Monetization (Weeks 19+)

**Goal:** Turn Stashboard into a sustainable SaaS.

- [ ] Team workspaces with shared spaces
- [ ] Role-based access: owner, admin, member
- [ ] Shared snippet library for teams
- [ ] Audit log: who copied/pasted what
- [ ] Stripe billing integration
  - Free tier: local-only, 500 clips
  - Pro tier ($7/mo): sync, AI search, unlimited history
  - Team tier ($12/user/mo): shared spaces, audit log
- [ ] Usage analytics dashboard for admins
- [ ] SOC 2 compliance preparation
- [ ] GDPR: data export, right-to-deletion endpoint
