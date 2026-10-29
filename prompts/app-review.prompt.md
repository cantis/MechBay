---
description: "Top 5 improvements for MechBay — April 2026 code review"
mode: "ask"
---

# MechBay Code Review — Top 5 Improvements

Comprehensive review of the MechBay Flask application conducted April 14, 2026 on the `feature/code-improvement` branch.

**Overall assessment:** Well-structured Flask app with clean separation of concerns (models → services → blueprints), good test coverage, and thoughtful UX patterns. The five items below are the highest-impact improvements ranked by risk and value.

---

## 1. Fix Security Defaults Before Any Public Deployment

**Priority:** Critical | **Effort:** Small

Three issues that must be resolved before the app is exposed to any network:

### a) Hardcoded secret key fallback
[app/config.py](../../app/config.py) falls back to "dev-secret" when the `SECRET_KEY` env var is unset. This makes CSRF tokens and session cookies predictable.

**Fix:** Fail fast in non-testing environments if `SECRET_KEY` is not set, or generate a random key at startup with a logged warning.

### b) Debug mode in server.py
[server.py](../../server.py) runs with `debug=True` unconditionally. This exposes the Werkzeug interactive debugger, which allows arbitrary code execution from the browser.

**Fix:** Read `DEBUG` from an environment variable and default to `False`.

### c) XSS via innerHTML in forces.js
[app/static/js/forces.js](../../app/static/js/forces.js) (around line 53) renders `data.template_name` and `data.missing` array items using `innerHTML` without sanitization. If a template name contains `<script>` tags (e.g., via imported JSON), it will execute in the browser.

**Fix:** Use `textContent` for plain text values, or build DOM nodes programmatically instead of string interpolation into `innerHTML`.

---

## 2. Add Custom Error Handlers and Structured Logging

**Priority:** High | **Effort:** Medium

### Problem
- No custom error pages — 404 and 500 return raw Flask/Werkzeug defaults that leak implementation details.
- Zero `logging` usage anywhere in the codebase — errors in service functions are silently swallowed or re-raised with no record.
- No audit trail for data mutations (imports, deletes, bulk updates).

### Recommendation
1. Register `@app.errorhandler` handlers for 400, 404, and 500 in `app/__init__.py`. Create simple branded error templates.
2. Add Python `logging` with a named logger per module. Log at `WARNING`+ in services (failed validations, constraint violations) and `ERROR` in exception handlers.
3. For production readiness, integrate a structured logging library (e.g., `structlog`) so logs can be parsed by monitoring tools.

---

## 3. Harden Input Validation at Route Boundaries

**Priority:** High | **Effort:** Small–Medium

### Problem
Multiple routes perform bare `int()` conversions on user-supplied values without try/except, causing unhandled 500 errors:

- `forces.py` — `int(miniature_id)`, `int(target_lance_id)`, `int(position)` in the move-miniature endpoint
- `forces.py` — `int(template_id)` in lance-from-template
- `miniatures.py` — `int(request.args.get("page"))` in pagination

Additionally, `miniature_service.update_miniature()` uses `setattr()` with only a `hasattr()` guard, which could allow setting protected fields like `id` or timestamps.

### Recommendation
1. Wrap all `int()` conversions at route level in try/except, returning 400 with a clear error message.
2. Add a field whitelist (`ALLOWED_UPDATE_FIELDS`) in `update_miniature()` instead of relying on `hasattr()`.
3. Add `MAX_CONTENT_LENGTH` to Flask config to prevent oversized file uploads on import routes.

---

## 4. Expand Test Coverage to Routes and Edge Cases

**Priority:** High | **Effort:** Medium

### Current State
- ~200+ tests covering service-layer CRUD, file documents, search/sort/filter, and Jeff export.
- Route-level tests exist for miniatures but are minimal for forces and lance templates.
- No tests for error paths (invalid input, missing records, malformed JSON imports).
- No tests for the dual-mode (JSON vs form) response pattern used in forces routes.

### Recommendation
1. Add route-level tests for forces blueprint — especially `add_miniature`, `remove_miniature`, `move_miniature`, and `lances/from-template` covering both JSON and form submission modes.
2. Add route-level tests for the files blueprint (inventory/force save, open, upload fallbacks).
3. Add negative tests: invalid IDs, missing required fields, duplicate entries, corrupt import files.
4. Add a test that verifies the active force partial unique index actually prevents two active forces.

---

## 5. Standardize Error Response Format and Dual-Mode Pattern

**Priority:** Medium | **Effort:** Medium

### Problem
Routes use an inconsistent mix of response styles:
- Some return `jsonify({"success": True})` / `jsonify({"success": False, "error": "..."})`
- Some return `jsonify({"error": "..."})` without a `success` field
- Flash message placement relative to the `is_json` check is inconsistent — some set flash before, some after, some not at all
- No standard HTTP status codes — some errors return 200, others 400 or 500

### Recommendation
1. Define a standard JSON error envelope: `{"success": bool, "error": str | null, "data": dict | null}`
2. Create a small helper function for dual-mode responses that handles the JSON vs redirect logic in one place.
3. Ensure all error responses use appropriate HTTP status codes (400 for bad input, 404 for missing resources, 409 for conflicts).
4. Document the dual-mode pattern in copilot-instructions.md with before/after examples.

---

## Summary

| # | Improvement | Priority | Effort | Category |
|---|------------|----------|--------|----------|
| 1 | Fix security defaults (secret key, debug, XSS) | Critical | Small | Security |
| 2 | Add error handlers and logging | High | Medium | Reliability |
| 3 | Harden input validation at route boundaries | High | Small–Med | Security |
| 4 | Expand test coverage to routes and edge cases | High | Medium | Quality |
| 5 | Standardize error responses and dual-mode pattern | Medium | Medium | Consistency |
