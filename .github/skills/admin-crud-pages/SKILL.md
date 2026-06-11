---
name: admin-crud-pages
description: Use this skill when building or refining admin CRUD pages for Flask or FastAPI applications using Bootstrap 5 and server-rendered templates. Covers list, detail, create, edit, archive/delete, filtering, pagination, and clean business-style admin UX.
---

# Admin CRUD Pages Skill

This skill is for building internal or line-of-business CRUD interfaces in Python web applications.

Target stack:
- Flask or FastAPI
- Jinja or similar server-rendered templates
- Bootstrap 5
- Clean, simple, business-oriented UI

Use this skill when the task involves:
- index/list pages
- detail/view pages
- create/edit forms
- delete or archive flows
- filters and search bars
- pagination
- action menus
- row-level operations
- admin dashboards that primarily manage records

## Core assumptions

- Prioritize clarity over visual flair.
- The page exists to help a person manage records quickly and correctly.
- Server-rendered patterns are preferred unless the codebase clearly uses richer client-side interactions.
- CRUD pages should be predictable and consistent across entities.

## Design principles

- Make the primary action obvious.
- Keep repetitive screens structurally consistent.
- Minimize clicks for common admin tasks.
- Make risky actions harder to trigger accidentally.
- Keep search, filters, and row actions easy to scan.
- Do not overload a single page with every possible operation.

## Standard CRUD page set

For a typical entity, aim for these screens:

1. List page
   - page title
   - primary action button
   - optional search/filter bar
   - table or card list
   - row actions
   - pagination
   - empty state

2. Detail page
   - title and key metadata
   - primary actions near top
   - core fields grouped clearly
   - related items or history in secondary sections

3. Create page
   - concise form
   - save and cancel actions
   - help text only where needed

4. Edit page
   - same structure as create
   - stable field order
   - save, cancel, and separate destructive actions if needed

5. Delete/archive confirmation
   - explicit confirmation step for destructive actions
   - plain explanation of impact
   - separate safe and destructive choices visually

## List page rules

A list page should usually include:
- entity title
- count if useful
- `New` button
- search box if the dataset is large enough
- filters only for meaningful distinctions
- readable table with restrained metadata
- row actions placed consistently
- pagination when needed

Prefer columns that support action:
- name/title
- status
- owner/category if relevant
- updated date
- actions

Do not include every field in the list view.

## Detail page rules

A detail page should:
- identify the record clearly
- show important metadata near the top
- provide top-level actions such as Edit or Back to list
- organize content into sections or cards
- avoid looking like a raw database dump

## Create/Edit form rules

Forms should:
- preserve backend field names and expected payloads
- follow a stable field order
- group related inputs together
- use sensible widths
- keep labels explicit
- show errors clearly
- keep submit controls in a consistent place

For long forms:
- split into sections
- consider cards or fieldsets
- do not create multi-step flows unless complexity justifies it

## Delete/archive rules

Prefer archive/deactivate over permanent delete where the business flow supports it.

For destructive flows:
- require explicit confirmation
- explain what happens next
- avoid making the destructive button the primary visual action
- separate delete/archive from save actions on edit screens

## Search/filter rules

Use search and filters only when they reduce effort.

Good filters:
- status
- category
- owner
- date range

Bad filters:
- rarely used, low-value toggles
- too many controls that create noise

Search/filter bars should:
- sit above the list
- be visually grouped
- allow reset/clear
- preserve current filter values on reload

## Status display

Use badges or muted labels for status:
- active
- inactive
- archived
- draft
- pending
- complete

Keep color meaning consistent across entities.

## Pagination rules

Show pagination when the record volume justifies it.
Also show:
- total count if available
- current slice summary if useful, such as items 21-40

Do not paginate tiny datasets.

## Action rules

Prefer these action tiers:

Primary page actions:
- New
- Save
- Edit

Secondary actions:
- Cancel
- Back
- Export

Destructive actions:
- Archive
- Delete
- Deactivate

Row actions should be limited. Usually:
- View
- Edit
- Archive/Delete

Do not create button clutter.

## Bootstrap 5 guidance

Prefer:
- `container` or `container-fluid`
- `card`
- `table table-striped table-hover align-middle`
- `btn btn-primary`
- `btn btn-outline-secondary`
- `btn btn-outline-danger`
- `badge`
- `form-control`, `form-select`
- spacing utilities

Use custom CSS sparingly.

## Flask/FastAPI expectations

For Flask:
- respect Blueprint structure
- follow existing route names and template layout
- integrate flash messages cleanly

For FastAPI:
- preserve Jinja template usage and route/template conventions
- keep template logic thin

## Output expectations

When applying this skill:
1. identify the CRUD screen type
2. inspect existing templates and routes
3. reuse patterns already present
4. make the page consistent with the admin set
5. keep changes minimal and maintainable
6. provide quick verification steps

See also:
- `crud-patterns.md`
- `crud-checklist.md`