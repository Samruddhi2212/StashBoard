# Keyboard Shortcuts Reference

Stashboard is designed to be 100% keyboard-driven. The mouse is never required.

---

## Global (Browser-wide)

These shortcuts work from any webpage, regardless of whether the popup is open.

| Shortcut | Mac | Action |
|----------|-----|--------|
| `Ctrl+Shift+V` | `⌘+Shift+V` | Open Stashboard popup |
| `Ctrl+Shift+1` | `⌘+Shift+1` | Quick paste item #1 (most recent) |
| `Ctrl+Shift+2` | `⌘+Shift+2` | Quick paste item #2 |
| `Ctrl+Shift+3` | `⌘+Shift+3` | Quick paste item #3 |
| `Ctrl+Shift+4` | `⌘+Shift+4` | Quick paste item #4 |
| `Ctrl+Shift+5` | `⌘+Shift+5` | Quick paste item #5 |

> **Note:** Quick-paste shortcuts paste the Nth most recent clip directly into
> the focused field — no popup required. Pinned items appear first so they
> can be reliably targeted by position.

---

## Popup Navigation

These shortcuts are active while the Stashboard popup is open and focused.

### List Navigation

| Key | Action |
|-----|--------|
| `↓` Arrow Down | Move selection down one clip |
| `↑` Arrow Up | Move selection up one clip |
| `Enter` | **Paste** selected clip into active tab, close popup |
| `Ctrl+Enter` / `⌘+Enter` | **Copy** selected clip to clipboard (no paste), close popup |
| `Escape` | Close popup (or clear search if query is active) |

### Search

| Key | Action |
|-----|--------|
| `/` | Jump focus to search input |
| Type anything | Filter clips in real-time (150ms debounce) |
| `Escape` (in search) | Clear query and show all clips |

### Space Switching

| Key | Action |
|-----|--------|
| `Tab` | Cycle forward to next space tab |
| `Shift+Tab` | Cycle backward to previous space tab |

### Clip Actions (when a clip is selected, search not focused)

| Key | Action |
|-----|--------|
| `P` | Pin / Unpin selected clip |
| `D` or `Delete` | Delete selected clip (confirms if pinned) |
| `E` | Edit selected clip (inline edit mode) |
| `S` | Show space picker to move clip |

### Inline Edit Mode

When `E` is pressed, the clip text becomes an editable textarea.

| Key | Action |
|-----|--------|
| `Enter` | Save changes |
| `Shift+Enter` | Insert newline (don't save) |
| `Escape` | Cancel edit, discard changes |

### Space Picker (after pressing `S`)

| Key | Action |
|-----|--------|
| Click | Move clip to clicked space |
| `Escape` / click outside | Dismiss picker without moving |

---

## Category Filter

Click any category pill (Email, URL, Code, etc.) at the top of the popup
to filter by that category. Click the same pill again to clear the filter.

---

## Tips

- **Muscle memory**: After a few uses, `Ctrl+Shift+V`, one or two arrows,
  `Enter` becomes a single fluid gesture to paste any recent item.

- **Quick-paste workflow**: Pin your most-reused snippets (email signature,
  phone number, address) so they always appear at positions 1–5,
  accessible without opening the popup.

- **Search workflow**: `Ctrl+Shift+V` → `/` → type a few chars → `↓` → `Enter`
  lets you search and paste without touching the mouse.
