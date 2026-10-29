## Prompt 6 Addendum — Aces Reconnaissance Actions

Expand the Aces Sortie workflow to model **Reconnaissance** as a first-class Sortie Setup activity.

This applies to `aces` Campaigns only.

Do not implement the physical reconnaissance resolution rules, dice/cards, waypoints, or story logic.

MechBay records what reconnaissance actions the player undertakes and their persistent campaign/accounting consequences.

### Reconnaissance occurs during Sortie Setup

Aces Sortie Setup includes a `Perform Reconnaissance` step before the Player Force is finalized.

Reconnaissance must therefore be entered while the Sortie is in Planning/Setup.

A Sortie may contain:

- no reconnaissance actions
- one reconnaissance action
- multiple reconnaissance actions

Do not model Reconnaissance as a single numeric expense field only.

### Reconnaissance Action model

Add a persistent Sortie-level reconnaissance action concept, such as `SortieReconAction`.

Each Reconnaissance Action should support at least:

- Sortie
- action name / description
- optional CampaignUnit
- SP cost
- notes
- stable ordering within the Sortie

Example actions:

- `Scout northern approach`
- `Sweep industrial district`
- `Probe enemy defenses`
- `Electronic reconnaissance`

The action name/description is required.

### Optional roster unit assignment

A Reconnaissance Action may optionally identify a Campaign Unit used to perform it.

Example:

`Scout northern approach — Pegasus Scout Hover`

Requirements:

- the unit must belong to the Aces Campaign Player Force
- preserve the unit relationship historically
- snapshot enough identifying information for historical reporting if needed
- do not require a unit for every reconnaissance action

Reconnaissance unit assignment does not automatically mean that unit is part of the final Sortie force unless the physical Aces rules/story also require it and the player selects it normally.

Do not invent automatic unit eligibility rules beyond what the physical Aces scenario tells the player.

### Reconnaissance SP cost

Each Reconnaissance Action may have:

- `0 SP`
- a positive SP cost

The player enters the SP cost produced by the physical Aces reconnaissance rules.

Do not attempt to calculate the reconnaissance cost automatically unless a later explicit rules requirement provides enough structured information.

The total reconnaissance expense for the Sortie is:

`sum(all Reconnaissance Action SP costs)`

### Accounting timing

Reconnaissance is **planned/performed during Sortie Setup**, but its SP cost is included in the Sortie's After-Sortie expense accounting.

Do not deduct the Warchest immediately when the Reconnaissance Action is entered during setup.

During successful After-Sortie settlement:

`Reconnaissance Expense = sum(Reconnaissance Action costs)`

Include that total in Total Expenses and Earnings calculation.

Avoid double-posting the same reconnaissance cost to the Warchest.

For a failed Sortie, follow the existing failed-Sortie rules: normal After-Sortie persistent accounting is skipped, so reconnaissance costs from that failed attempt should not persist unless the Aces rules explicitly state otherwise.

### Sortie Setup UI

Add a `Reconnaissance` section to Aces Sortie Planning.

Allow the player to:

- add reconnaissance action
- edit action
- remove action while Sortie remains editable
- enter action name/description
- optionally select a Campaign Unit
- enter SP cost
- enter notes

Show:

- each action
- associated unit where present
- individual SP cost
- total planned Reconnaissance SP cost

Do not show this workflow for Chaos Campaigns unless Chaos already has its own unrelated reconnaissance system.

### Sortie locking

Once the Sortie is moved out of editable Planning/Setup state, preserve its reconnaissance records as historical Sortie data.

Do not allow later Player Force changes to rewrite the historical reconnaissance-unit identity.

### Sortie Report

Add a dedicated **Reconnaissance** section to the Aces Sortie Report.

Example:

**Reconnaissance**

| Action | Unit | SP |
| --- | --- | ---: |
| Scout northern approach | Pegasus Scout Hover | 20 |
| Electronic sweep | — | 10 |

`Total Reconnaissance: 30 SP`

This section should appear before or alongside the After-Sortie accounting.

The Expenses section should then show:

`Reconnaissance: 30 SP`

Do not require the reader to reconstruct the total from raw ledger transactions.

### Campaign history

Reconnaissance belongs to the historical Sortie, not to the Campaign generally.

Campaign timeline/history may summarize it, but the detailed actions remain on the Sortie Report.

### Failed Sorties and replays

Each Sortie attempt has its own Reconnaissance Actions.

If a Sortie fails and must be replayed:

- preserve the failed attempt's Reconnaissance records
- do not copy them automatically into the replay unless the user explicitly chooses to repeat/re-enter them
- the replay may use different reconnaissance actions
- failed-attempt reconnaissance remains visible historically

### Tests

Add or update pytest coverage for at least:

- Aces Sortie may contain zero reconnaissance actions
- Aces Sortie may contain multiple reconnaissance actions
- reconnaissance action requires a description/name
- reconnaissance action may have no CampaignUnit
- reconnaissance action may reference a valid CampaignUnit
- unit from another Campaign is rejected
- reconnaissance SP may be zero
- reconnaissance total equals sum of action costs
- reconnaissance is editable during Sortie Planning
- reconnaissance becomes historical once Sortie is locked/finalized
- successful Sortie includes reconnaissance total in expenses
- reconnaissance expense is not double-posted
- failed Sortie preserves reconnaissance history but does not apply normal persistent expense settlement
- replay maintains its own independent reconnaissance actions
- Sortie Report displays reconnaissance action details and total
- Chaos Campaign behaviour remains unchanged

Run the full pytest suite and Ruff after the change.

Do not accept regressions to existing Chaos or Aces campaign functionality.