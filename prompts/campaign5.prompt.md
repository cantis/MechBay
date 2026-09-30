# MechBay Campaign Support — Prompt 5: BattleTech Aces Campaign Ruleset

Add support for the **BattleTech Aces campaign ruleset** alongside the existing Hot Spots / Chaos Campaign ruleset.

The existing campaign implementation must remain usable for Chaos Campaign play.

Do not create a completely separate parallel campaign application or duplicate the existing Campaign, CampaignUnit, CampaignPilot, Sortie, Warchest, DamageEvent, RepairOrder, and related infrastructure.

Instead, extend the existing campaign domain so a Campaign has a ruleset that controls the campaign-specific workflow and calculations.

The two initial rulesets are:

- `chaos`
- `aces`

The Aces implementation in this phase is concerned with **persistent campaign management only**.

MechBay does **not** need to implement the Aces tabletop automation system, waypoint AI, card decks, opposing-force logic, movement rules, combat decisions, map rules, or scenario engine.

The physical game/cards handle those systems.

MechBay needs to manage:

- the Player Force
- Named Pilots
- Support Points / Warchest
- Sortie history
- casualties
- unit damage
- repairs
- pilot wounds/deaths
- rearming
- replacement/additional unit purchases
- persistent campaign history

Reference rules: `Aces Rules.pdf`.

---

## 1. Add Campaign Ruleset

Add a Campaign ruleset field or equivalent mechanism.

Initial values:

- `chaos`
- `aces`

Existing Campaigns should continue to behave as Chaos Campaigns unless explicitly migrated or selected otherwise.

Campaign creation should allow the user to choose the ruleset.

Display the selected ruleset clearly on the Campaign detail page.

Do not scatter raw ruleset-string comparisons throughout templates and services if a small centralized helper/strategy layer makes the distinction clearer.

Do not over-engineer a generic campaign-rules framework. Two clean rule paths are sufficient.

---

## 2. Preserve Chaos Campaign behaviour

Prompt 5 must not break the existing Chaos Campaign implementation.

For Chaos Campaigns continue to support:

- Contracts
- Contract rosters
- transportation
- locations/travel
- Contract Scale
- Contract Support
- Sortie/Track Scale
- existing Chaos repair calculations
- Chaos campaign month handling
- existing Warchest ledger behaviour

Run the existing campaign tests after adding Aces support.

Where Aces and Chaos use different calculations, make the calculation ruleset-dependent rather than replacing the Chaos implementation.

---

## 3. Aces has no Contract requirement

An Aces campaign does not require the MechBay Contract layer.

Aces Sorties belong directly to the Campaign.

Update the model and services so:

- Chaos Sorties continue to require a Contract.
- Aces Sorties do not require a Contract.
- `Sortie.contract_id` may therefore need to become nullable.
- A null Contract must only be accepted when the parent Campaign uses the Aces ruleset.
- Existing Chaos validation remains intact.

Do not create artificial placeholder Contracts for Aces campaigns.

For Aces the hierarchy is:

`Campaign -> Campaign Roster -> Sortie`

rather than:

`Campaign -> Contract Roster -> Sortie`

---

## 4. Aces Player Force

The Campaign roster is the persistent **Player Force** for an Aces campaign.

Continue using CampaignUnit as the persistent in-universe unit.

Do not create a duplicate `AcesUnit` model.

The Player Force should support:

- existing Campaign Unit snapshot information
- MUL unit / variant
- PV
- current condition
- availability
- physical Miniature link where available
- active / destroyed / truly destroyed / retired history
- notes

The Aces campaign rules assume Alpha Strike Point Value and Skill 4 unit values for normal force accounting.

Aces campaign support should therefore remain Alpha Strike focused in this phase.

Do not add BattleTech BV campaign parity as part of Prompt 5.

---

## 5. New Aces Campaign setup

Provide an Aces-specific Campaign creation/setup path.

The standard Aces new-force setup uses a **400 PV Player Force**.

Store/display the Player Force's total PV and validate that units have authoritative MUL Point Values.

Do not treat missing PV as zero.

A Campaign Unit without valid PV cannot participate in Aces force accounting until its MUL information is corrected.

Allow Campaign creation from an existing MechBay Force where practical.

Do not automatically include units intended to represent the automated Aces opposing force in the player's persistent Campaign roster.

Campaign setup may permit user overrides/custom campaign starting conditions rather than hard-coding every published scenario requirement.

The campaign should record its starting Warchest as a normal Warchest ledger transaction.

---

## 6. Aces difficulty

Add an optional Aces Campaign difficulty setting.

The Aces rules provide campaign difficulty modifiers that can alter:

- Player Force PV available for Sorties
- SP earned from objectives

Support at least storing/displaying the selected difficulty.

If the exact modifiers are implemented, centralize them in an Aces rules helper rather than scattering them through UI code.

Do not implement any AI/opposing-force difficulty logic.

Difficulty applies only to persistent campaign calculations that MechBay actually manages.

---

## 7. Named Pilots

Reuse CampaignPilot for Aces Named Pilots.

Do not create an Aces-specific pilot table.

Aces campaigns may have multiple Named Pilots and maintain persistent:

- name
- callsign
- Gunnery
- Piloting
- Alpha Strike Skill
- Edge
- Edge Abilities where already supported
- earned/improvement SP
- wounds
- alive/dead/retired state
- preferred Campaign Unit where useful
- injury/history records

Keep Aces-specific pilot advancement calculations separate from Chaos calculations where the rules differ.

Do not implement Aces card behaviour or Edge-card effects.

MechBay only records persistent character state.

---

## 8. Aces Sorties

Continue using the existing Sortie and SortieUnit models.

For an Aces campaign:

- Sortie belongs directly to Campaign.
- Contract is null.
- Sortie force is selected from available Campaign Units.
- SortieUnit remains a historical snapshot.
- Named Pilot assignments remain snapshotted.
- MUL configuration/variant remains snapshotted.

Aces Sortie setup only needs enough information for campaign management.

Support fields such as:

- Sortie name/number
- campaign sequence
- date played if the existing model supports it
- scenario/story name
- notes
- outcome
- selected Player Force units
- named pilot assignments
- After Action notes

Do not model:

- Aces opponent deck
- Command Deck
- Tactics cards
- waypoint behaviour
- scanning waypoints
- keyword resolution
- map movement
- automated enemy movement
- automated target selection
- initiative automation
- tabletop combat

Those remain physical tabletop/card-game responsibilities.

---

## 9. Aces After-Sortie workflow

Add ruleset-aware After Action processing for Aces.

The high-level Aces post-Sortie sequence includes:

1. resolve scenario/story outcome
2. determine casualties
3. calculate income
4. calculate expenses
5. process repairs/rearming
6. process Named Pilot results
7. purchase additional/replacement units
8. update the persistent Player Force and Warchest

MechBay does not need to determine the tabletop result automatically.

The user enters the results produced by the physical Aces game.

---

## 10. Aces damage and casualties

Continue using:

- SortieUnit result
- DamageEvent
- RepairOrder
- CampaignUnit current condition

Do not create separate Aces damage tables.

Allow the user to record the campaign result for each fielded unit.

Support at least:

- no relevant damage
- armour-only damage
- structure/critical damage
- crippled
- destroyed
- truly destroyed

The tabletop game determines the result.

If a destroyed unit fails the applicable recovery/salvage determination during physical play, the user marks it Truly Destroyed in MechBay.

Truly Destroyed Campaign Units:

- remain in campaign history
- are unavailable
- cannot be repaired
- are not deleted
- do not affect the physical Miniature record

Do not automate tabletop casualty/salvage dice rolls in this phase.

---

## 11. Aces repair costs

Aces uses a different simplified repair-cost system from Hot Spots / Chaos Campaign.

Do not reuse the Chaos tonnage-based repair calculation for Aces.

For Aces, use these standard repair costs:

- Armour-only damage: **20 SP**
- Structure damage or critical damage: **40 SP**
- Crippled unit: **50 SP**
- Destroyed but recoverable unit: **100 SP**

Only the highest applicable repair category is charged.

Examples:

- armour + structure damage => 40 SP
- crippled => 50 SP, not 20 + 40 + 50
- destroyed but recoverable => 100 SP

A Truly Destroyed unit cannot be repaired.

Automatically create the Aces RepairOrder with the correct default gross cost during After Action.

Keep the amount overridable for campaign-specific/special rules.

The RepairOrder must preserve its ruleset context so later changes do not cause an Aces repair to be recalculated using Chaos rules.

---

## 12. Aces rearming

Aces uses the Alpha Strike campaign rearming rule.

A unit without the `ENE` special ability requires rearming after a Sortie.

Default Aces rearming cost:

**20 SP per applicable unit**

Reuse the existing MUL snapshot / BFAbilities logic where possible.

Do not automatically charge rearming to units with the `ENE` special ability.

Record rearming through:

- RearmOrder
- Warchest ledger transaction
- historical campaign activity

Keep special-rule override capability.

---

## 13. Aces income

Aces Sorties award SP through the scenario/objective rules.

MechBay does not need to calculate scenario objectives from cards/maps.

Allow the user to enter the SP earned from the physical Sortie.

Support enough structure to record, where useful:

- primary objective SP
- secondary/other objective SP
- difficulty modifier
- adjusted income
- other campaign income
- total Sortie income

At minimum, total Sortie income must be supported.

When After Action is finalized, income should generate appropriate Warchest ledger transactions.

Avoid duplicate posting if the After Action is reopened or edited.

---

## 14. Aces sortie expenses

Aces may incur campaign expenses associated with the Sortie.

Where useful, support user-entered expenses such as:

- reconnaissance
- waypoint-related campaign costs
- repairs
- rearming
- pilot-related SP allocations
- other scenario/campaign expenses

Do not implement the physical Reconnaissance or Waypoint mechanics.

MechBay only records their resulting SP expense if the user enters it.

All actual Warchest changes should be represented by Warchest ledger transactions rather than silently changing a balance.

---

## 15. Aces earnings / Warchest

After a Sortie:

`Net earnings = Sortie income - campaign expenses`

The Warchest remains the persistent store of unspent Support Points.

Continue to use the existing Warchest ledger.

Do not create a separate Aces currency table.

Use user-facing terminology:

- SP
- Support Points
- Warchest

Do not use WP for Aces campaign currency.

If expenses exceed available SP, do not invent debt behaviour beyond what the Aces rules explicitly require and what MechBay already supports.

If a full Aces Warchest Debt implementation would materially expand Prompt 5, defer it and validate/report insufficient funds instead unless existing rules/code make debt straightforward.

---

## 16. Purchasing additional/replacement units

Add an Aces Player Force purchase workflow.

This is an important requirement.

Aces allows accumulated Warchest SP to be spent on additional/replacement units.

Standard purchase price:

`Purchase cost = unit PV × 40 SP`

Use the unit's standard Alpha Strike Skill 4 PV.

Example:

`28 PV × 40 = 1,120 SP`

Requirements:

- Search/select a legal MUL unit/variant using the existing MUL integration.
- Show PV.
- Calculate `PV × 40 SP`.
- Require sufficient Warchest SP unless an explicitly supported debt rule applies.
- Confirm the purchase.
- Create a new CampaignUnit.
- Add it to the Aces Player Force.
- Record the purchase in WarchestTransaction.
- Preserve purchase history.
- Optionally link a physical Miniature after purchase if one exists in the user's collection.

Do not require that an in-universe replacement unit reuse the CampaignUnit identity of a destroyed unit.

A purchased replacement is a **new CampaignUnit**.

The old destroyed/truly-destroyed CampaignUnit remains part of campaign history.

The physical Miniature may later be linked to the new CampaignUnit as its tabletop representation.

---

## 17. Purchases are not physical inventory purchases

Keep the existing distinction between:

- physical Miniature collection
- Campaign Player Force

Purchasing a BattleMech/unit with campaign SP represents an in-universe campaign acquisition.

It must **not automatically create a physical Miniature inventory record**.

Allow:

- CampaignUnit with no physical Miniature link
- later linking/reassigning a suitable physical Miniature

This is required because the user may use the same real miniature to represent different historical campaign units over time.

---

## 18. Force growth and losses

The Aces Player Force is persistent and mutable.

It may change because of:

- Truly Destroyed units
- retired units
- purchased replacements
- purchased additional units

Do not rebuild the Player Force from the original saved Force after Campaign creation.

The Campaign roster is authoritative after creation.

Maintain historical records of units that leave active service.

---

## 19. Named Pilot wounds and deaths

Continue using the Prompt 4 injury model:

- `wounds` is authoritative
- alive + zero wounds => eligible
- wounds > 0 => unavailable
- dead/retired => unavailable

Aces After Action should allow the user to record:

- pilot wounded
- number of wounds gained if needed
- pilot killed

Increment wounds rather than setting a simple boolean.

Preserve PilotInjuryEvent history.

Do not implement automated tabletop crew casualty rolls.

---

## 20. Named Pilot advancement

The Aces rules support persistent Named Pilot improvement through earned SP and MVP awards.

For Prompt 5, support the persistent accounting needed for this without modelling card effects.

At minimum support:

- Named Pilot earned SP
- allocation/history
- MVP indicator/bonus where entered
- updated skill/Edge values where the user applies improvement

If existing CampaignPilot improvement fields are insufficient, extend them minimally.

Do not implement a generic skill-tree engine.

Do not implement Edge Ability card rules.

The user may manually apply the resulting pilot improvements based on the Aces rules.

---

## 21. Aces Campaign log

Provide an Aces-oriented Campaign history/log view using existing historical records.

Useful entries include:

- Sortie played
- Sortie income
- expenses
- Warchest change
- Named Pilot SP
- purchases
- casualties
- repairs
- rearming
- keywords/story notes where manually entered

Do not create a duplicate ledger if existing Warchest/history entities already contain this information.

Aces Campaign Log presentation can aggregate existing records.

---

## 22. Aces Force roster display

For an Aces Campaign detail page, emphasize the current Player Force.

Display at least:

- unit
- variant
- PV
- current condition
- availability
- Named Pilot/preferred pilot where useful
- active/lost status

Show:

- current total active Player Force PV
- current Warchest
- current Named Pilots
- campaign difficulty
- number of completed Sorties

Keep historical/lost units accessible without counting them as the active Player Force.

---

## 23. Ruleset-specific UI

Avoid showing irrelevant Chaos controls in an Aces campaign.

For Aces Campaigns hide/omit normal workflow controls for:

- Contracts
- Contract roster
- Contract terms
- employer
- transportation
- Contract Support
- Contract Scale negotiation
- travel-to-contract workflow

Existing Campaign travel/location history may remain available as optional narrative/history data if already generic, but it must not be required for Aces play.

For Chaos Campaigns continue showing the existing workflow.

---

## 24. Ruleset-specific calculations

Centralize the campaign calculations that differ by ruleset.

Examples:

### Chaos

Repair cost:

- armour = tonnage / 2
- structure = tonnage × 2
- crippled = tonnage × 3
- destroyed = tonnage × 5

Contract Support may reduce cost.

### Aces

Repair cost:

- armour = 20 SP
- structure/critical = 40 SP
- crippled = 50 SP
- destroyed = 100 SP

No Chaos Contract Support calculation applies.

### Aces purchase

`PV × 40 SP`

Do not use chains of template `if campaign.ruleset == ...` calculations if these rules can live cleanly in campaign services/helpers.

Again, do not build an elaborate plugin framework for only two rulesets.

---

## 25. Migration / compatibility

Existing campaign data must remain usable.

Requirements:

- existing Campaigns default/migrate to `chaos`
- existing Chaos Sorties retain their Contracts
- existing Chaos repair history is unchanged
- making Sortie Contract nullable must not weaken Chaos validation
- JSON/archive/export functionality must preserve the Campaign ruleset
- Aces Campaigns must round-trip through existing backup/export mechanisms

Add database migration logic consistent with the project's current migration approach.

---

## 26. Deferred Aces features

Do not implement these systems in Prompt 5:

- Aces AI decision-making
- Aces decks/cards
- opponent force automation
- Command Deck
- Tactics cards
- waypoint placement
- waypoint scanning
- waypoint resolution
- story-keyword rule engine
- tabletop initiative
- movement
- targeting
- attacks
- terrain/map generation
- physical Aces scenario automation
- automated salvage/casualty dice rolling
- automated campaign-book branching

MechBay is a **campaign manager**, not an Aces game engine.

The user plays the Aces game physically and records persistent consequences in MechBay.

---

## 27. Tests

Add pytest coverage for at least:

- Campaign ruleset defaults existing Campaigns to Chaos
- Aces Campaign creation
- Aces Sortie can exist without Contract
- Chaos Sortie still requires Contract
- Aces Sortie selects from Campaign roster
- Aces unit with missing PV is rejected from force accounting
- Aces After Action creates correct repair costs:
  - armour = 20
  - structure/critical = 40
  - crippled = 50
  - destroyed = 100
- Truly Destroyed Aces unit cannot be repaired
- Aces rearming = 20 SP for units without ENE
- ENE unit does not receive automatic rearm charge
- Aces Sortie income posts correctly to Warchest
- Aces expenses post correctly to Warchest
- Aces purchase cost = PV × 40
- purchased unit becomes a new CampaignUnit
- purchase does not create a physical Miniature
- replacement does not mutate/reuse destroyed CampaignUnit identity
- insufficient SP blocks purchase unless explicitly supported otherwise
- pilot wounds affect Aces Sortie availability
- Aces Campaign backup/export retains ruleset
- existing Chaos tests continue to pass

Run:

- full pytest suite
- Ruff
- any existing application validation/build checks

Do not accept regressions to Chaos Campaign functionality.

---

## Completion criteria

Prompt 5 is complete when MechBay supports two campaign management workflows:

### Chaos Campaign

`Campaign -> Contract -> Contract Force -> Sortie -> After Action -> Between-Sortie Activities`

### Aces Campaign

`Campaign -> Player Force -> Sortie -> After Action -> Repairs / Pilot Results / Purchases`

The Aces workflow must persist the Player Force, casualties, repairs, Named Pilots, SP/Warchest and purchased replacement/additional units without attempting to reproduce the physical Aces card-driven opponent system.