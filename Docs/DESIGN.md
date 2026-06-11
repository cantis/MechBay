---
version: alpha
name: MechBay
description: >
  Visual identity for MechBay — a BattleTech miniature inventory and force
  management tool. Built on Bootstrap 5.3.3 with no custom CSS overrides.
  All token values reflect Bootstrap's default theme.

colors:
  primary: "#0d6efd"
  secondary: "#6c757d"
  success: "#198754"
  danger: "#dc3545"
  warning: "#ffc107"
  neutral: "#f8f9fa"
  surface: "#ffffff"
  on-surface: "#212529"
  on-primary: "#ffffff"
  on-danger: "#ffffff"
  on-success: "#ffffff"

typography:
  headline-lg:
    fontFamily: "system-ui, -apple-system, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif"
    fontSize: 2rem
    fontWeight: 500
    lineHeight: 1.2
  headline-md:
    fontFamily: "system-ui, -apple-system, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif"
    fontSize: 1.25rem
    fontWeight: 500
    lineHeight: 1.2
  body-md:
    fontFamily: "system-ui, -apple-system, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif"
    fontSize: 1rem
    fontWeight: 400
    lineHeight: 1.5
  body-sm:
    fontFamily: "system-ui, -apple-system, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif"
    fontSize: 0.875rem
    fontWeight: 400
    lineHeight: 1.5
  label-md:
    fontFamily: "system-ui, -apple-system, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif"
    fontSize: 0.875rem
    fontWeight: 600
    lineHeight: 1.5

rounded:
  none: 0
  sm: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 1rem
  full: 50rem

spacing:
  xs: 0.25rem
  sm: 0.5rem
  md: 1rem
  lg: 1.5rem
  xl: 3rem

components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.on-primary}"
    rounded: "{rounded.md}"
    padding: "0.375rem 0.75rem"
  button-primary-hover:
    backgroundColor: "#0b5ed7"
    textColor: "{colors.on-primary}"
  button-secondary:
    backgroundColor: "{colors.secondary}"
    textColor: "{colors.on-primary}"
    rounded: "{rounded.md}"
    padding: "0.375rem 0.75rem"
  button-danger:
    backgroundColor: "{colors.danger}"
    textColor: "{colors.on-danger}"
    rounded: "{rounded.md}"
    padding: "0.375rem 0.75rem"
  button-sm:
    padding: "0.25rem 0.5rem"
    typography: "{typography.body-sm}"
  card:
    backgroundColor: "{colors.surface}"
    rounded: "{rounded.md}"
    padding: "{spacing.md}"
  table:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.on-surface}"
  badge-success:
    backgroundColor: "{colors.success}"
    textColor: "{colors.on-success}"
    rounded: "{rounded.full}"
    padding: "0.25rem 0.5rem"
  badge-danger:
    backgroundColor: "{colors.danger}"
    textColor: "{colors.on-danger}"
    rounded: "{rounded.full}"
    padding: "0.25rem 0.5rem"
  alert-success:
    backgroundColor: "#d1e7dd"
    textColor: "#0a3622"
    rounded: "{rounded.md}"
  alert-danger:
    backgroundColor: "#f8d7da"
    textColor: "#58151c"
    rounded: "{rounded.md}"
  alert-warning:
    backgroundColor: "#fff3cd"
    textColor: "#664d03"
    rounded: "{rounded.md}"
  alert-info:
    backgroundColor: "#cff4fc"
    textColor: "#055160"
    rounded: "{rounded.md}"
  navbar:
    backgroundColor: "{colors.neutral}"
    textColor: "{colors.on-surface}"
---

# MechBay Design System

Read this file before changing visual identity, color usage, typography, spacing, or component styling.
See `docs/UI-CONVENTIONS.md` for template structure, JavaScript patterns, and Jinja conventions.

## Overview

MechBay is a functional, data-focused tool for BattleTech enthusiasts managing physical miniature collections. The UI should feel organised and purposeful — a workshop dashboard rather than a consumer app. Clarity and efficiency matter more than visual flair.

The design system is **Bootstrap 5.3.3 with no custom CSS overrides**. All visual decisions follow Bootstrap defaults. When Bootstrap provides a utility or component, use it without modification. Custom CSS is added only to fill gaps Bootstrap does not cover.

The overall mood is: clean, neutral, grid-based. Information density is moderate — tables for inventory, cards for grouped entities, no decorative chrome.

## Colors

The palette is Bootstrap 5.3.3's default theme, used directly via its utility classes. MechBay does not define a custom brand color palette; Bootstrap's semantic roles apply directly.

- **Primary (`#0d6efd`)**: Bootstrap blue. Used for primary action buttons (`btn-primary`), active nav states, and key interactive affordances.
- **Secondary (`#6c757d`)**: Muted grey. Used for secondary buttons, metadata, and non-critical labels.
- **Success (`#198754`)**: Green. Used exclusively for positive feedback: success alerts, "painted" status badges.
- **Danger (`#dc3545`)**: Red. Used for destructive actions (delete buttons), error alerts, and validation failures.
- **Warning (`#ffc107`)**: Amber. Used for caution states and warning alerts.
- **Neutral (`#f8f9fa`)**: Bootstrap's `bg-body-tertiary`. Used for the navbar background and subtle container fills.
- **Surface (`#ffffff`)**: Card and content area backgrounds.
- **On-surface (`#212529`)**: Bootstrap's default body text color. Primary text on all light surfaces.

Do not introduce additional brand colors. If a new semantic state is needed, map it to one of the eight colors above.

## Typography

MechBay uses Bootstrap's default native font stack — no web fonts are loaded. This keeps the app fast and visually neutral across operating systems.

Font stack: `system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif`

Typography levels follow Bootstrap's scale:

- **`headline-lg`** (`<h2>`, `2rem / 500`): Main page title — one per page.
- **`headline-md`** (`<h5>` or `<h6>`, `1.25rem / 500`): Section headings inside cards.
- **`body-md`** (default, `1rem / 400`): Standard body text, table cells, form labels.
- **`body-sm`** (`0.875rem / 400`): Secondary metadata, timestamps, helper text.
- **`label-md`** (`0.875rem / 600`): Table column headers, inline labels requiring emphasis.

Do not use more than two font weights on a single screen. Do not introduce decorative or monospace fonts for UI text.

## Layout

MechBay uses Bootstrap's fluid grid. All page content sits inside `<main class="container py-4">` defined in `base.html`. Pages do not set their own container; they inherit it.

Spacing follows Bootstrap's spacer scale (base: `1rem` / 16px):

- `xs` (4px) — micro-adjustments, icon gaps
- `sm` (8px) — tight inline spacing
- `md` (16px) — standard element padding, form group gaps
- `lg` (24px) — section separation within a page
- `xl` (48px) — major section breaks, page-level vertical rhythm

Use `.row` / `.col-*` for multi-column layouts. Default to single-column stacked layout for detail pages; use two columns (`col-md-8` / `col-md-4`) where a sidebar pattern is needed.

Use `.table-responsive` wrappers on all data tables to prevent overflow on narrow viewports.

## Elevation & Depth

MechBay uses **flat layering** via Bootstrap's card component rather than drop shadows. Visual hierarchy is conveyed through:

- **Card borders** (`border` on `.card`): separates content groups from the page background
- **Table striping** (`.table-hover`): provides row-level focus feedback without depth
- **Background tones**: `bg-body-tertiary` (neutral) for the navbar; `bg-white` / default for content cards

Do not use heavy box shadows on content areas. Bootstrap's `.shadow-sm` may be used sparingly on floating elements (modals, dropdowns) but is not used on inline content cards.

## Shapes

The shape language is Bootstrap's default minimal rounding. Interactive elements use consistent corner radii from the rounded scale:

- Buttons: `rounded.md` (0.375rem) — Bootstrap default
- Cards: `rounded.md` (0.375rem) — Bootstrap default
- Badges: `rounded.full` (50rem) — pill shape for status indicators
- Inputs: `rounded.md` (0.375rem) — Bootstrap default

Do not mix sharp (0px) and rounded corners in the same view. Do not use `rounded.xl` or `rounded.full` on large container elements.

## Components

Key components and their token mappings. All components derive from Bootstrap classes — tokens reflect the effective computed values, not custom overrides.

**Buttons**: Three variants in regular use — `button-primary` for the single most important action per screen, `button-secondary` for alternative/cancel actions, `button-danger` for destructive operations. Use `button-sm` sizing (`btn-sm`) for table row and inline actions.

**Alerts (flash messages)**: Four semantic variants — `alert-success`, `alert-danger`, `alert-warning`, `alert-info`. Rendered in a fixed toast container (top-right) defined in `base.html`. Auto-dismiss after 6 seconds.

**Cards**: Default Bootstrap `.card` with `rounded.md` and `padding.md`. Group related content inside cards; do not nest cards.

**Tables**: `.table.table-hover.table-sm` for all data tables. Use `table-responsive` wrapper. Column headers use `label-md` weight.

**Badges**: Pill-shaped (`.badge.rounded-pill`) in `success` or `danger` for status indicators (e.g., paint status, active force indicator).

**Navbar**: `bg-body-tertiary border-bottom` styling. Brand link targets Inventory. Five navigation items in fixed order — see `docs/UI-CONVENTIONS.md`.

## Do's and Don'ts

- Do use `btn-primary` for the single most important action per screen only
- Do use `btn-danger` for all destructive actions (delete, remove, clear)
- Do use pill badges for status indicators; do not use colored text alone for status
- Do use `table-hover` on all data tables for row focus feedback
- Do maintain WCAG AA contrast (4.5:1 for normal text); Bootstrap's default palette meets this
- Don't introduce custom colors outside the eight defined in the color palette
- Don't load web fonts; the native font stack is intentional
- Don't use `rounded.xl` or `rounded.full` on cards or large containers
- Don't use box shadows on inline content cards
- Don't place more than one `btn-primary` in the same visible section
