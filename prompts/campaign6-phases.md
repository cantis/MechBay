# Prompt 6 — Phase Split

`campaign6.prompt.md` is implemented in four phases. Section numbers refer to that file.

| Phase | Scope | Sections |
| --- | --- | --- |
| **6a** | Named Pilot model, Type, Callsign, SP thresholds, Edge Ability catalogue, advancement events, Service History page, 2–6 limit | 1–11, 49 (Named Pilots) |
| **6b** | Sortie data model: per-Sortie pilot assignment + snapshots, Force Commander, `date_played`, failed Sorties and replay links, Story Keywords | 12–18, 48 |
| **6c** | After-Sortie flow: income/expense categories, Aces repairs (Size-based) and rearming, pilot SP distribution (2:1 weighting), MVP, wounds/recovery, Warchest, Sortie Report, Sortie History, cross-links | 19–33, 40–42, 46 |
| **6d** | Difficulty + experienced-force modifier, Aces creation flow (400 PV / 8 units / opening Warchest), Sortie PV validation, purchases/sales, Omni, Campaign summary | 34–39, 43–47 |

## Decisions recorded

- Pilot `name`, `gunnery`, `piloting` stay non-null on `CampaignPilot` (no table rebuild). Aces pilots set `name = callsign` and ignore gunnery/piloting.
- Skill / Edge Tokens / Edge Abilities on Aces pilots are written only by `aces_pilot_service.apply_advancement`.
- The maximum pilot SP per Sortie is player input.
- MVP selection is required on a successful Sortie; the +20 SP is always awarded and never costs Warchest.
- A pilot who sat out a failed Sortie is still unavailable on the replay.
- A replay copies the failed attempt's force and pilots and may be modified.
- The experienced-force PV modifier is fixed once at campaign creation.
- Aces gets its own creation flow (6d).
- Edge Ability catalogue is a Python constant.
- Duplicate-chassis restrictions (section 38) are on hold.

## Notes from 6c

- Aces repair costs are `Size x 20/40/60/100`; non-BattleMechs use half Size, unrounded until the end. Size comes from the MUL snapshot (`BFSize`); BattleMechs without it fall back to tonnage bands, other types are never guessed.
- A living non-participant's pilot SP cap is `floor(max / 2)`.
- Aces repair orders are prepaid at After-Sortie; completing one only restores the unit.
- Sortie Report purchases/sales fields exist but are filled in 6d (purchases, sales, Omni, Player Force PV difficulty modifiers).

## Notes from 6d

- Aces campaigns are created through `create_aces_campaign` (the route uses it). New force: <= 400 PV, >= 8 units, opening Warchest = unused PV x 40 SP. Experienced force (existing Named Pilot SP > 0): no size cap, opening Warchest = override or 0, fixed PV penalty stored on the campaign. Campaigns created earlier keep their current Warchest.
- Difficulty and experienced-force PV modifiers stack additively; allowed Sortie PV is floored and checked when a Sortie is marked Ready.
- Omni reconfiguration for Aces happens in Sortie Planning with an automatic cost; the Chaos manual-cost form is hidden for Aces.
- Sales retire the CampaignUnit (condition `retired`, sale recorded in the ledger). Purchases and sales roll into the open Sortie Report until it is finalized.
- Section 38 (duplicate chassis/variant restrictions) remains on hold.

## Notes from the time/location addendum

- Aces campaigns are Sortie-based: no starting year/month, current month, location, travel or Contracts are stored or shown. Chaos is unchanged.
- `campaign_month` (events, ledger, Sorties) and `campaigns.current_campaign_month` are nullable; startup rebuilds the affected SQLite tables and clears any stored calendar/location values on existing Aces campaigns. Chaos rows are untouched.
- Aces chronology: Sortie number, then replay attempt, then `date_played`. Pilot Service History orders creation, then each Sortie in sequence (participation, injuries, advancement).

## Notes from the repairs and sales addenda

- Aces repairs are mandatory: the repair order and its cost are created at Apply (part of the Sortie's expenses), and the unit returns to service when the Sortie is **finalized**. Aces repair orders cannot be edited, cancelled or completed by hand; the Repair Orders card is Chaos-only.
- The Warchest does not move until the Sortie is **finalized**: Apply stores the ledger lines on the report (`pending_ledger`) and Finalize posts them. The report's Warchest before/after are therefore always the true figures.
- Between Sorties is derived (no new status): no Aces Sortie is Fought or awaiting finalization. Until then purchases, sales, hires, pilot/unit retirement, manual Warchest entries and creating or readying the next Sortie are blocked. A failed Sortie leaves the campaign free to trade before its replay.
- Purchases and sales no longer touch any Sortie Report (`purchases_total`, `sales_total`, `warchest_after` were removed). The Campaign Timeline shows Sortie results and Between-Sorties transactions as separate entries.
- Aces unit condition is set only by Sortie results; Truly Destroyed is recorded only in the After-Sortie result.
