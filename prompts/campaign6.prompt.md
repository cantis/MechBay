# MechBay Campaign Support — Prompt 6: Aces Named Pilots, Sortie Reporting, and Full Campaign Rules

Extend the existing Aces campaign support so that it accurately models the persistent campaign-management rules from `Aces Rules.pdf`.

This phase should complete the Aces-specific campaign workflow without attempting to reproduce the physical Aces card-driven opponent system.

The application should manage:

- persistent Player Force
- Named Pilots
- Sorties and replay attempts
- real-world date played
- Story Keywords
- casualties
- repairs
- rearming
- personnel expenses
- Named Pilot advancement
- MVP
- Force Commander
- Warchest accounting
- purchases and sales
- campaign history/reporting

Do not implement:

- Aces AI/opposition automation
- waypoint logic
- card decks
- map movement
- initiative
- targeting
- physical combat
- automatic story branching

The physical Aces game remains authoritative for gameplay. MechBay records and applies the persistent campaign consequences.

---

## 1. Aces Named Pilot model

Reuse `CampaignPilot`.

Do not create an `AcesPilot` table.

For an Aces Campaign, the pilot UI and rules are Aces-specific.

An Aces Named Pilot has:

- Callsign
- Type
- Alpha Strike Skill
- Edge Tokens
- Edge Abilities
- Total SP Earned
- Skill SP allocated
- Edge Token SP allocated
- Edge Ability SP allocated
- MVP count
- wound/recovery state
- alive/dead/retired status
- service history

For Aces:

- personal `name` is not required
- `gunnery` is not used
- `piloting` is not used
- only Alpha Strike `Skill` applies

Existing Chaos fields may remain nullable/hidden where required for compatibility.

---

## 2. Named Pilot Callsign

For Aces, Callsign is the pilot's primary displayed identity.

Do not require a separate personal name.

Examples:

- Hawk
- Ghost
- Warden
- Razor

Display Callsign everywhere an Aces pilot is shown.

---

## 3. Named Pilot Type

Add a permanent Aces pilot Type.

Supported values:

- `BM` — BattleMech
- `CV` — Combat Vehicle
- `BA` — Battle Armor

Conventional Infantry and Emplacements cannot have Named Pilots.

The pilot Type cannot change during the campaign.

The Type controls which Campaign Units may be assigned to the pilot during Sortie setup.

Do not allow incompatible pilot/unit assignment.

---

## 4. Named Pilot limits

An Aces campaign must support:

- minimum 2 Named Pilots
- maximum 6 Named Pilots
- 4 recommended, but not required

Enforce 2–6 where appropriate.

Dead/retired pilots remain in history and do not disappear.

Replacement/additional Named Pilots may be added later subject to the limit.

---

## 5. Starting Named Pilot creation

A newly created standard Aces Named Pilot begins with:

- Skill 4
- 1 Edge Token
- 0 Edge Abilities
- 150 Total SP Earned

The initial 150 SP must be fully allocated among:

- Skill SP
- Edge Token SP
- Edge Ability SP

Before creation is finalized:

`Skill SP + Edge SP + Edge Ability SP = 150`

No unallocated starting SP may remain.

The resulting Skill/Edge/Ability count is derived from the cumulative thresholds below.

The initial creation should create the first immutable pilot advancement/history event.

---

## 6. Aces Named Pilot advancement thresholds

Use the following cumulative allocation tables.

### Skill

| Skill SP | Skill |
| ---: | ---: |
| 0 | 4 |
| 400 | 3 |
| 900 | 2 |
| 1900 | 1 |
| 3400 | 0 |

### Edge Tokens

| Edge SP | Edge Tokens |
| ---: | ---: |
| 0 | 1 |
| 60 | 2 |
| 120 | 3 |
| 200 | 4 |
| 300 | 5 |
| 420 | 6 |
| 560 | 7 |
| 720 | 8 |
| 900 | 9 |
| 1100 | 10 |

### Edge Abilities

| Edge Ability SP | Edge Ability Count |
| ---: | ---: |
| 0 | 0 |
| 60 | 1 |
| 180 | 2 |
| 360 | 3 |
| 600 | 4 |
| 900 | 5 |

The displayed values are derived from cumulative SP allocations.

Do not treat Skill, Edge Token count, or Edge Ability count as independent editable campaign values during normal use.

---

## 7. SP allocation invariants

For Aces Named Pilots:

`Total SP Earned = Skill SP + Edge Token SP + Edge Ability SP`

All newly earned pilot SP must be allocated before an advancement step is finalized.

It is valid to allocate SP without immediately crossing a threshold.

Example:

- Pilot has 30 Edge Ability SP
- receives 20 more
- now has 50
- still has 0 Edge Abilities

The SP remains invested in that category.

---

## 8. Edge Ability catalogue

Maintain a centralized Aces Edge Ability catalogue.

Current abilities:

- Marksman
- Bulwark
- Patient
- Cautious
- Protector
- Coolant Flush
- Jumping Jack
- Melee Specialist
- Nimble
- Speed Demon
- Assassin
- Forward Observer

Do not store the full physical-card rules text unless it is already useful elsewhere.

The catalogue should be easy to extend in future Aces versions without schema migration.

Avoid using a database enum that would require migration for every new ability.

---

## 9. Edge Ability selection

When a pilot crosses an Edge Ability threshold, they immediately gain the required number of ability slots.

The advancement cannot be finalized until the pilot selects all newly earned abilities.

Rules:

- select from the centralized catalogue
- no duplicate abilities for the same pilot
- selections are permanent
- preserve ability acquisition history

If one advancement crosses multiple thresholds, require the correct number of ability selections before commit.

Example:

- previous Ability SP = 150
- new Ability SP = 390

This crosses:

- 180 => second ability
- 360 => third ability

Require two new abilities before finalizing.

---

## 10. Pilot advancement history

Add an immutable Aces pilot advancement history record, such as `PilotAdvancementEvent`.

Each event should preserve:

- CampaignPilot
- source type
- Sortie when applicable
- date/sequence
- SP received in this event
- MVP bonus
- participation state
- Skill SP allocated this event
- Edge SP allocated this event
- Ability SP allocated this event
- cumulative Skill SP after event
- cumulative Edge SP after event
- cumulative Ability SP after event
- Skill after event
- Edge Tokens after event
- Edge Ability count after event
- newly acquired Edge Ability names
- Total SP Earned after event

Suggested source types:

- `initial`
- `sortie`

Do not silently edit historical advancement records once committed.

If corrections are needed later, implement an explicit correction mechanism in a future phase rather than rewriting history now.

---

## 11. Pilot service history view

Add a dedicated Aces Pilot Service History page.

It should present the pilot's career clearly and chronologically.

At minimum show:

- Callsign
- Type
- current Skill
- current Edge Tokens
- current Edge Abilities
- Total SP Earned
- MVP count
- current status
- current wound/recovery state

Then show a chronological history including:

- pilot creation
- each Sortie
- whether the pilot participated
- whether they were Force Commander
- whether they were MVP
- SP earned
- SP allocation
- Skill/Edge/Ability changes
- new Edge Abilities
- wounds
- death/retirement where applicable

Every Sortie entry should link back to the corresponding Sortie Report.

---

## 12. Sortie Pilot assignment

For Aces Sorties, Named Pilot assignment is per Sortie.

Do not permanently assign pilots to a CampaignUnit.

Do not expose Chaos preferred/default-unit assignment as an authoritative Aces concept.

During Sortie preparation:

- assign available Named Pilots to compatible Campaign Units
- Type compatibility must be enforced
- each pilot may command at most one unit in the Sortie
- unassigned units use generic crew as appropriate

Snapshot the pilot's Callsign, Type, Skill, Edge and abilities on the SortieUnit so historical Sorties remain correct if the pilot later improves.

---

## 13. Force Commander

Aces Sortie setup requires one participating Named Pilot to be selected as Force Commander.

Add:

- `force_commander_pilot_id`

to the Sortie or equivalent relationship.

Requirements:

- must be a Named Pilot participating in that Sortie
- must be alive/eligible when the Sortie begins
- snapshot/display the commander in the Sortie Report

Force Commander and MVP are separate concepts.

Do not implement the physical Command Deck mechanics.

---

## 14. Real-world date played

Add a real-world `date_played` to Aces Sorties.

This should be a normal calendar date.

It is separate from any abstract campaign sequence.

Display it:

- in Sortie History
- on the Sortie Report
- in Pilot Service History

---

## 15. Sortie numbering and replay attempts

Aces failed Sorties must be replayed.

A failed attempt must remain in history.

Do not overwrite the failed Sortie with its replay.

Support a replay relationship, such as:

- `replay_of_sortie_id`
- or equivalent

A failed Sortie may have:

- status/result indicating failure
- replay required
- link to the replacement attempt

A replay should link back to the failed attempt.

The UI may display numbering such as:

- Sortie 4
- Sortie 4R
- Sortie 4R2

or another clear attempt indicator.

Do not require this exact display format if the existing numbering model has a cleaner equivalent.

---

## 16. Failed Sortie behaviour

If the Aces Sortie fails because its primary objective was not completed:

- record the failed attempt
- preserve date played
- preserve the Sortie force snapshot
- preserve participation history
- preserve notes
- do not apply normal After-Sortie consequences
- no Story Keywords
- no persistent casualties
- no persistent repairs
- no rearming expenses
- no pilot advancement
- no MVP
- no Warchest income/expense changes from normal After-Sortie processing
- replay is required

Damage and casualties from the failed attempt are treated as though the attempt did not happen for persistent campaign state.

The failed Sortie remains visible in Campaign and Pilot history.

---

## 17. Story Keywords

Add persistent Aces Story Keywords.

Use historical records rather than a comma-separated field.

A keyword event should support at least:

- Campaign
- Sortie
- keyword text
- action such as acquired/removed
- date/sequence

Current Campaign keywords should be derived from keyword history.

Failed Sorties do not grant Story Keywords.

Do not implement automatic story branching.

MechBay only records keyword state so later scenario/story decisions can refer to it.

---

## 18. Campaign keyword display

Show current Story Keywords on the Aces Campaign summary.

On Sortie History, show keywords gained by each successful Sortie as compact badges/text.

On the Sortie Report, include a Story Outcome section showing:

- keywords gained
- keywords removed, if applicable
- free-form story notes

---

## 19. Sortie History summary

Add an Aces Campaign Sortie History view.

Each row/card should show at least:

- Sortie number/attempt
- Date Played
- Sortie name
- result
- force PV
- MVP
- net SP / Warchest change
- keywords gained

Example columns:

| Sortie | Date | Result | Force PV | MVP | Net SP | Keywords |
| --- | --- | --- | ---: | --- | ---: | --- |

Each entry links to the detailed Sortie Report.

Failed attempts must remain visible.

---

## 20. Sortie Report

Add a detailed, readable Aces Sortie Report.

This should be a first-class historical view, not merely raw ledger entries.

The report should include:

### Header

- Campaign
- Sortie number/attempt
- Sortie name
- Date Played
- result
- Force Commander
- MVP
- Story Keywords gained
- replay link if applicable

### Player Force

For each fielded unit:

- unit/variant
- PV
- assigned pilot
- pilot Skill at time of Sortie
- unit result
- casualty/damage result

### Income

Show:

- Primary Objective SP
- Secondary/other Objective SP
- difficulty modifier
- other income
- Total Income

### Expenses

Show:

- Reconnaissance
- Waypoint adjustments
- Rearming
- Personnel
- Repairs
- Other
- Total Expenses

### Earnings

Show:

`Earnings = Total Income - Total Expenses`

### Named Pilot Improvement

Show:

- maximum participating-pilot SP
- participating pilots and allocated share
- non-participating living pilots and half-share
- dead pilots and zero share where applicable
- MVP bonus separately
- per-pilot SP allocation across Skill / Edge / Abilities
- newly acquired abilities

### Warchest

Show:

- Warchest before
- earnings remaining after required pilot allocation
- purchases
- sales
- Warchest after

### Narrative

Show:

- After Action notes
- story outcome
- Next Steps / Next Sortie

The report should preserve historical values rather than recalculating from current pilot/unit state.

---

## 21. Cross-links

Make history navigable.

From Sortie Report:

- clicking a Named Pilot opens that pilot's Service History

From Pilot Service History:

- clicking a Sortie opens that Sortie Report

From a failed Sortie:

- link to replay attempt

From replay attempt:

- link back to failed attempt

---

## 22. Aces After-Sortie flow

Use this Aces workflow:

1. Read/record Sortie outcome
2. Apply Story Keywords if successful
3. Check casualties
4. Calculate Income
5. Calculate Expenses
6. Apply repairs/rearming/personnel expenses
7. Determine Earnings
8. Allocate mandatory Named Pilot SP
9. Select MVP
10. Allocate each pilot's gained SP among Skill / Edge / Edge Abilities
11. Select newly earned Edge Abilities immediately
12. Apply remaining earnings to Warchest
13. Purchase/sell units
14. Record Next Steps / Next Sortie
15. Finalize immutable Sortie Report

Failed Sorties do not run the normal persistent After-Sortie workflow.

---

## 23. Named Pilot SP eligibility

After a successful Sortie, the player enters the **maximum SP that a participating Named Pilot may receive**.

Use this maximum to calculate pilot entitlements.

### Participating pilots

A living Named Pilot who participated may receive up to:

`maximum pilot SP`

A pilot wounded during this Sortie still counts as participating and receives the full participating share.

### Non-participating pilots

A living Named Pilot who did not participate receives up to:

`maximum pilot SP / 2`

This includes pilots who sat out because they were previously wounded.

Use whole-SP integer handling consistent with the rest of the campaign system.

### Killed pilots

A Named Pilot killed during the Sortie receives no pilot SP.

---

## 24. Insufficient Sortie earnings for pilots

Pilot improvement comes from the current Sortie's positive Earnings.

It does not draw from the existing Warchest.

If there is insufficient current-Sortie Earnings to pay all pilot maximum shares, preserve the intended **2:1 weighting**:

- participating living pilot weight = 1
- non-participating living pilot weight = 0.5
- killed pilot weight = 0

Distribute available pilot-improvement SP proportionally by these weights.

Do not split evenly by headcount.

Do not exceed any pilot's applicable maximum.

Use a deterministic whole-SP rounding/remainder method so the total allocated to pilots never exceeds available Earnings.

Document the chosen remainder handling in code/tests.

---

## 25. No positive earnings

If:

`Total Income - Total Expenses <= 0`

then:

- no Named Pilot advancement SP is distributed
- no MVP SP allocation from Sortie earnings occurs
- the campaign continues
- negative Earnings reduce the Warchest

The MVP bonus remains rules-specific; do not create pilot advancement from the Warchest.

---

## 26. MVP

Every successful Aces Sortie should support selecting one MVP.

The MVP must:

- be a Named Pilot
- have participated in the Sortie
- have survived

The MVP receives:

`+20 SP`

This is a bonus and does **not** come from Sortie Earnings or Warchest.

Track:

- MVP on the Sortie
- +20 SP on the pilot advancement event
- pilot lifetime `mvp_count`

The MVP bonus must still be fully allocated among Skill / Edge / Edge Abilities as part of that pilot's advancement.

---

## 27. Pilot wounds and Aces recovery

Do not use the Chaos wound model literally.

For Aces:

- a Named Pilot wounded during a successful Sortie incurs 100 SP treatment expense
- the pilot becomes unavailable for the next Sortie
- after sitting out that next successful Sortie, the pilot recovers and becomes available again
- the previously wounded pilot still receives the non-participant half-share of pilot improvement SP for that Sortie

Represent this as a one-Sortie recovery state rather than accumulating multiple long-term wound boxes.

Preserve PilotInjuryEvent history.

A failed Sortie does not advance wound recovery because its persistent After-Sortie consequences are ignored.

If the current shared `wounds` field must remain for compatibility, use ruleset-specific service logic so Aces behaviour remains correct.

---

## 28. Pilot death

If a Named Pilot is killed:

- status becomes dead
- they receive no pilot SP from that Sortie
- they cannot be MVP
- they remain in Pilot Service History
- they remain linked to the historical Sortie

Do not delete the pilot.

---

## 29. Personnel expenses

Aces After-Sortie expenses should support:

- replacement generic crew: 100 SP
- wounded Named Pilot treatment: 100 SP
- new/replacement Named Pilot: 150 SP

A newly hired/replacement Named Pilot starts with their own 150 SP for initial pilot allocation.

Do not model anonymous generic crews as persistent named characters unless the existing application already does so.

Record personnel expenses in the Warchest ledger and Sortie Report.

---

## 30. Aces repair costs

Do not use Chaos tonnage-based repair costs for Aces.

Aces uses Size-based repair costs.

For BattleMechs:

- Armour-only damage = `Size × 20 SP`
- Structure damage and/or Critical damage = `Size × 40 SP`
- Crippled = `Size × 60 SP`
- Destroyed but recoverable = `Size × 100 SP`

Only the highest applicable category is charged.

For:

- Combat Vehicles
- Battle Armor
- Conventional Infantry

use **half printed Size** for the repair calculation.

Do not round the halved Size before applying the multiplier.

Example:

- Size 3 Combat Vehicle
- crippled
- effective Size = 1.5
- repair cost = `1.5 × 60 = 90 SP`

A Truly Destroyed unit cannot be repaired.

Use appropriate whole-SP handling after the final calculation if required by the current integer schema.

Create RepairOrders automatically with the calculated Aces cost.

Preserve ruleset context so an Aces repair is never later recalculated using Chaos rules.

---

## 31. Aces rearming

For each fielded unit that is not Truly Destroyed:

- if unit has ENE => no rearming cost
- otherwise => 20 SP rearming cost

Use the existing MUL/BFAbilities snapshot logic where possible.

Record via RearmOrder and Warchest ledger.

---

## 32. Casualties and Truly Destroyed units

The physical Aces game determines whether a destroyed unit is:

- recovered/repairable
- truly destroyed

MechBay records the result.

Do not automate the casualty/salvage die rolls.

Truly Destroyed units:

- remain in campaign history
- are removed from active Player Force availability
- cannot be repaired
- do not delete the physical Miniature record

---

## 33. Aces Omni reconfiguration

Aces has its own Omni configuration cost rules.

During Sortie preparation, an Omni unit may change configuration.

If new configuration PV is equal to or lower than current configuration:

`cost = unit Size × 5 SP`

If new configuration PV is higher:

`cost = (new PV - old PV) × 40 SP`

Requirements:

- unit must actually be Omni-capable
- preserve configuration history
- update the CampaignUnit's current configuration
- SortieUnit snapshots the configuration actually fielded
- record SP cost in Warchest ledger
- do not apply Chaos Omni cost rules

---

## 34. Aces Campaign Difficulty

Implement Aces difficulty modifiers.

Supported levels:

### Rookie

- Player Force PV allowed: +20%
- Objective SP earned: 120%

### Standard

- Player Force PV allowed: 100%
- Objective SP earned: 100%

### Veteran

- Player Force PV allowed: -10%
- Objective SP earned: 90%

### Elite

- Player Force PV allowed: -20%
- Objective SP earned: 80%

### Legendary

- Player Force PV allowed: -30%
- Objective SP earned: 70%

Use the selected difficulty during:

- Sortie force limit validation
- objective SP calculation

Do not modify physical-opponent behaviour.

---

## 35. Existing-force difficulty modifier

For an experienced Aces Player Force reused in a new campaign, apply an additional Player Force PV modifier based on the **total SP earned by all Named Pilots**:

| Total Named Pilot SP | Player Force PV modifier |
| ---: | ---: |
| 0–3000 | 0% |
| 3001–6000 | -10% |
| 6001–9000 | -20% |
| 9001–12000 | -30% |
| 12001+ | -40% |

This stacks with Campaign Difficulty.

Centralize the calculation in Aces rules logic.

Do not modify Objective SP earned with this modifier unless the rules explicitly require it.

---

## 36. Aces new Player Force creation

A standard new Aces Campaign Player Force starts with:

- 400 PV
- at least 8 units

Support the Alpha Strike unit categories allowed by the Aces rules where MechBay/MUL data supports them:

- BattleMech
- Battle Armor
- Combat Vehicle
- Conventional Infantry

Do not include physical Aces-box-product restrictions in application validation.

Missing PV must block Aces force accounting.

Do not treat `None` as zero.

---

## 37. Starting Warchest from unused PV

For a new Aces force:

`unused PV × 40 SP`

becomes starting Warchest.

Example:

- force = 395 PV
- unused = 5 PV
- starting Warchest = 200 SP

Record this as the opening Warchest ledger entry.

Do not use Chaos's fixed 3,000 SP starting Warchest for Aces.

---

## 38. Starting-force duplicate restrictions

Implement the Aces duplicate chassis/variant restrictions if current MUL data can reliably identify:

- chassis
- variant

Keep the validation in Aces rules logic.

If the existing MUL model cannot reliably enforce a specific published restriction, do not guess; document and defer only that narrow validation.

Do not compromise the rest of Aces force creation because of one unavailable metadata field.

---

## 39. Sortie force PV validation

For each Aces Sortie:

- start from the Campaign's current Player Force
- include only available units
- apply Campaign Difficulty Player Force modifier
- apply experienced-force modifier if applicable
- validate the selected Sortie force against the resulting allowed PV

Use authoritative MUL PV.

Do not use Chaos Contract Scale.

---

## 40. Income

Allow structured Aces income entry.

Support:

- Primary Objective SP
- Secondary/other Objective SP
- Other Income

Apply Campaign Difficulty objective-SP multiplier to the applicable objective values.

Show both:

- base amount
- adjusted amount

Then calculate Total Income.

Do not automate physical objective determination.

---

## 41. Expenses

Support structured Aces expense categories:

- Reconnaissance
- Waypoint adjustments
- Rearming
- Personnel
- Repairs
- Other

Keep the categories visible in the Sortie Report.

All expenses should create ledger entries or be represented in the finalized Sortie accounting in a way that remains auditable.

Avoid double-posting when saving/finalizing.

---

## 42. Earnings and negative Warchest

Calculate:

`Earnings = Total Income - Total Expenses`

If Earnings are negative:

- deduct the negative amount from Warchest
- allow Warchest to reach zero or become negative
- do not block the campaign
- do not distribute pilot advancement SP from the existing Warchest

Do not invent Chaos Warchest Debt behaviour for Aces.

---

## 43. Purchases

After pilot improvement allocation and Warchest update, allow Aces unit purchases.

Purchase cost:

`standard Skill 4 PV × 40 SP`

Requirements:

- use existing MUL search
- select unit/variant
- show PV
- calculate cost
- deduct from Warchest
- create a new CampaignUnit
- preserve purchase history
- do not create a physical Miniature automatically

A purchased replacement is a new CampaignUnit.

Do not reuse the identity of a destroyed CampaignUnit.

---

## 44. Selling units

Allow selling an active/repaired CampaignUnit during the Aces purchase step.

Sale value:

`standard Skill 4 PV × 20 SP`

Requirements:

- add proceeds to Warchest
- retire/remove the CampaignUnit from active Player Force
- preserve the unit in campaign history
- preserve physical Miniature separately
- record sale in Warchest ledger and campaign history

Do not delete the CampaignUnit.

---

## 45. Player Force persistence

The Aces Player Force is mutable and authoritative after Campaign creation.

It may change through:

- destroyed/truly destroyed units
- retired/sold units
- new purchases
- replacements

Do not rebuild it from the original saved Force.

---

## 46. Next Steps / Next Sortie

Add a free-form or simple structured field to successful Aces Sortie completion:

- Next Steps
- Next Sortie

This records the instruction from the physical campaign book.

Display it:

- at the bottom of the Sortie Report
- on the Campaign summary where useful

Do not implement automatic story branching.

---

## 47. Campaign summary

The Aces Campaign summary should clearly show:

- Campaign name
- Difficulty
- current active Player Force PV
- current Warchest
- current Named Pilots
- current Story Keywords
- completed Sortie count
- next Sortie / Next Steps
- recent Sortie history

Do not show irrelevant Chaos Contract workflow controls.

---

## 48. Reporting principles

Aces historical reporting is important.

Preserve historical snapshots rather than recalculating old reports from current state.

Examples:

- if Hawk is Skill 2 today but fought Sortie 1 at Skill 4, Sortie 1 shows Skill 4
- if a unit later changes Omni configuration, old Sorties show the configuration actually used
- if a Story Keyword is later removed, the Sortie that originally granted it still shows that historical event
- if a pilot later dies, earlier Sorties still show them as alive/participating at the time

---

## 49. Tests

Add or update pytest coverage for at least:

### Named Pilots

- Aces pilot requires Callsign but not personal name
- Aces pilot uses Skill only
- Aces pilot Type is required and immutable
- pilot limits 2–6
- starting Total SP = 150
- starting 150 SP must be fully allocated
- Skill threshold calculation
- Edge Token threshold calculation
- Edge Ability threshold calculation
- Edge Ability selection required when threshold crossed
- duplicate Edge Ability rejected
- advancement event immutable
- MVP +20 SP
- MVP count increments
- dead pilot cannot receive Sortie SP
- non-participating living pilot receives half-share entitlement
- insufficient earnings preserve 2:1 weighting
- pilot SP never draws from existing Warchest

### Wounds

- Aces wound adds 100 SP personnel expense
- wounded pilot unavailable for next Sortie
- wounded pilot receives non-participant half-share
- pilot recovers after sitting out next successful Sortie
- failed Sortie does not advance recovery

### Sorties

- Date Played stored/displayed
- Force Commander must be participating Named Pilot
- failed Sortie remains historical
- failed Sortie requires replay
- failed Sortie applies no persistent After-Sortie consequences
- replay links work
- successful Sortie Report snapshots historical pilot/unit values

### Story Keywords

- successful Sortie can award keyword
- failed Sortie cannot award keyword
- keyword history preserved
- current keyword set derived correctly

### Repairs

- BM armour repair = Size ×20
- BM structure repair = Size ×40
- BM crippled = Size ×60
- BM destroyed = Size ×100
- CV/BA/CI use half Size
- half-Size calculation is not rounded before multiplier
- Truly Destroyed cannot be repaired

### Rearming

- non-ENE fielded unit = 20 SP
- ENE unit = 0
- Truly Destroyed unit not rearmed

### Omni

- lower/equal PV configuration = Size ×5
- higher PV configuration = PV difference ×40
- configuration history preserved

### Difficulty

- Rookie +20% Player Force / 120% objective SP
- Standard 100/100
- Veteran -10/90
- Elite -20/80
- Legendary -30/70
- experienced-force pilot-SP modifier stacks with Player Force modifier

### Player Force

- new force = max 400 PV
- minimum 8 units
- missing PV blocked
- unused PV converts to opening Warchest at ×40

### Accounting

- income categories total correctly
- expense categories total correctly
- negative Earnings reduce Warchest
- zero/negative Earnings skip pilot advancement
- MVP bonus does not reduce Earnings/Warchest
- pilot allocation happens before Warchest remainder

### Purchases / Sales

- purchase = PV ×40
- purchase creates new CampaignUnit
- purchase does not create Miniature
- sale = PV ×20
- sold unit leaves active roster but remains in history

### Navigation / reports

- Campaign Sortie History links to Sortie Report
- Sortie Report pilot link opens Pilot Service History
- Pilot Service History Sortie link returns to Sortie Report

Run:

- full pytest suite
- Ruff
- existing application validation/build checks

Do not accept regressions to Chaos Campaign support.

---

## 50. Completion criteria

This phase is complete when Aces Campaign play supports the full persistent campaign-management loop:

`Campaign -> Player Force -> Sortie -> After-Sortie -> Casualties -> Income -> Expenses -> Repairs -> Pilot Improvement -> MVP -> Warchest -> Purchases/Sales -> Story Keywords -> Next Sortie`

and when:

- Named Pilot advancement matches the Aces cumulative-SP rules
- pilot history is preserved and readable
- Sortie history/reporting is clear
- failed Sorties remain historical and require replay
- Story Keywords persist
- repairs/rearming use Aces-specific rules
- Aces accounting remains independent from Chaos Contract logic
- physical Aces gameplay remains outside MechBay