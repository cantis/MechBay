---
description: "Second review — top 5 improvements for MechBay (April 2026)"
mode: "ask"
---

# MechBay Code Review #2 — Top 5 Improvements

Second review conducted April 15, 2026 on `feature/code-improvement` after implementing all items from the first review (security fixes, structlog, error handlers, input validation, test expansion, UI bug fixes).

**Overall assessment:** The app is in solid shape — CSRF everywhere, structured logging, custom error pages, 161 passing tests, validated inputs. The remaining items are about performance, robustness, and polish rather than critical gaps.

---

## 1. Fix N+1 Query and Missing Expunge in Miniature Service

**Priority:** High | **Effort:** Small

### Problem
Three related issues in `miniature_service.py` and `miniatures.py`:

### a) N+1 query in edit route
[app/blueprints/miniatures.py](../../app/blueprints/miniatures.py) line ~320 fetches **all** miniatures into Python memory to find one by ID:
```python
mini = next((m for m in get_all_miniatures() if m.id == id), None)
```
With 500+ miniatures this is a significant performance penalty on every edit page load.

**Fix:** Add a `get_miniature_by_id(id)` function to `miniature_service.py` that does `session.get(Miniature, id)` with proper expunge. Use it in the edit route.

### b) Missing session.expunge() in add_miniature()
[app/services/miniature_service.py](../../app/services/miniature_service.py) — `add_miniature()` returns the Miniature object without calling `session.expunge()`. The object is still attached to the now-closed session, risking DetachedInstanceError if any attribute is accessed after return.

### c) Missing session.expunge() in update_miniature()
Same issue — `update_miniature()` returns the object without expunging.

**Fix for b & c:** Add `session.expunge(mini)` before returning in both functions, matching the pattern used in `get_force_by_id()`.

---

## 2. Replace deprecated datetime.utcnow() with datetime.now(UTC)

**Priority:** High | **Effort:** Small

### Problem
Python 3.12+ deprecates `datetime.utcnow()` — it returns a naive datetime that can cause subtle timezone bugs. This generates ~1375 warnings during the test suite. Found in 5+ locations:

- [app/models/force.py](../../app/models/force.py) — `default=datetime.utcnow` and `onupdate=datetime.utcnow` on `created_at` / `updated_at`
- [app/services/force_service.py](../../app/services/force_service.py) — `datetime.utcnow()` in export functions
- [app/services/lance_template_service.py](../../app/services/lance_template_service.py) — same in export functions

### Fix
```python
from datetime import UTC, datetime

# In models — use a lambda to generate timezone-aware datetimes
created_at = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

# In service code
datetime.now(UTC)  # instead of datetime.utcnow()
```

---

## 3. Add .catch() Error Handling to All fetch() Calls

**Priority:** High | **Effort:** Small

### Problem
Every `fetch()` call in the JavaScript files (except one in `forces/list.html`) is missing a `.catch()` handler. If the network fails, the server is down, or the response isn't valid JSON, the user sees **no feedback** — the UI just silently does nothing.

Affected locations:
- [app/static/js/forces.js](../../app/static/js/forces.js) — move miniature, apply template, remove miniature, rename lance (4 calls)
- [app/static/js/miniatures.js](../../app/static/js/miniatures.js) — bulk action (1 call)

### Fix
Add `.catch(() => { alert('Request failed. Please try again.'); })` to every fetch chain. For the move-miniature handler, also add `location.reload()` in the catch to resync the UI.

---

## 4. Extract Filter Parameter Preservation Helper

**Priority:** Medium | **Effort:** Small

### Problem
The pattern of preserving series/faction/q/sort/direction filter state across redirects is copy-pasted 10+ times across `miniatures.py`:
```python
return_params = {}
if form.get("return_series"):
    return_params["series"] = form.get("return_series")
if form.get("return_faction"):
    return_params["faction"] = form.get("return_faction")
if form.get("return_q"):
    return_params["q"] = form.get("return_q")
if form.get("return_sort"):
    return_params["sort"] = form.get("return_sort")
if form.get("return_direction"):
    return_params["direction"] = form.get("return_direction")
```

This is error-prone (easy to forget a field) and adds visual noise to every route handler.

### Fix
Extract a helper function at the top of the blueprint:
```python
def _preserve_filters(source) -> dict:
    """Extract filter params from form/args for redirect preservation."""
    params = {}
    for key in ("series", "faction", "q", "sort", "direction"):
        val = source.get(f"return_{key}") or source.get(key)
        if val:
            params[key] = val
    return params
```
Then replace all 10+ occurrences with `return_params = _preserve_filters(request.form)`.

---

## 5. Improve Accessibility on Core Interactive Elements

**Priority:** Medium | **Effort:** Medium

### Problem
Several interactive elements lack proper accessibility attributes, making the app difficult to use with screen readers or keyboard-only navigation:

### a) Select-all checkbox has no label
[app/templates/miniatures/list.html](../../app/templates/miniatures/list.html) — the "select all" checkbox uses `title` but no `aria-label`:
```html
<input type="checkbox" id="selectAll" class="form-check-input" title="Select all on this page">
```

### b) Row checkboxes have no labels
Individual row checkboxes (`class="row-check"`) have no label or aria-label — screen readers announce them as unlabelled checkboxes.

### c) Sortable table headers lack sort state
Column headers are clickable links but don't communicate current sort state to assistive technology. Missing `aria-sort` attribute on `<th>` elements.

### d) Modal dialogs missing aria attributes
Modals in `forces/detail.html` lack `aria-labelledby` pointing to the modal title, and `aria-modal="true"`.

### Fix
- Add `aria-label="Select all miniatures on this page"` to the select-all checkbox
- Add `aria-label="Select {{ m.prefix }} {{ m.chassis }}"` to each row checkbox
- Add `aria-sort="ascending|descending|none"` to `<th>` elements based on current sort state
- Add `aria-labelledby` and `aria-modal="true"` to all modal `<div>` elements

---

## Summary

| # | Improvement | Priority | Effort | Category |
|---|------------|----------|--------|----------|
| 1 | Fix N+1 query + missing expunge in miniature service | High | Small | Performance / Safety |
| 2 | Replace datetime.utcnow() with datetime.now(UTC) | High | Small | Deprecation |
| 3 | Add .catch() to all fetch() calls | High | Small | Robustness |
| 4 | Extract filter parameter preservation helper | Medium | Small | Code Quality |
| 5 | Improve accessibility on interactive elements | Medium | Medium | Accessibility |
