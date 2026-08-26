# MechBay Campaign Support — Prompt 4: Rules Fidelity and Campaign Corrections

Review and update the existing campaign implementation on the `feature/campaign_support` branch. The campaign architecture is already in place and should not be redesigned wholesale.

The existing implementation already includes Campaign, CampaignUnit, CampaignPilot, Contract, Sortie, SortieUnit, TravelEvent, WarchestTransaction, DamageEvent, RepairOrder, RearmOrder, PilotInjuryEvent, and UnitConfigurationEvent concepts.

The goal of this phase is to correct rules mismatches and fill several structural gaps identified by comparing the current implementation against the BattleTech: Hot Spots — Draconis Reach mercenary campaign rules.

Preserve existing tests and behaviour unless specifically changed below. Add or update tests for all corrected behaviour.

## 1. Correct the starting Warchest

The current campaign creation logic derives the opening Warchest from unused force-building PV.

For a normal Hot Spots mercenary campaign, the default starting Warchest should instead be **3,000 Support Points (SP)**.

Requirements:

* Change the normal default opening Warchest to 3,000 SP.
* Preserve the existing ability for the user to override the opening Warchest when creating a Campaign.
* Do not derive the default starting Warchest from unused force PV.
* Record the opening balance as a normal Warchest ledger transaction.
* Use `SP` / `Support Points` terminology rather than `WP` in new campaign-facing code, labels, help text, and validation messages.

Do not yet implement a separate Aces campaign ruleset.

## 2. Correct Named Pilot defaults and recovery behaviour

The current Named Pilot defaults do not fully match the normal Hot Spots starting pilot rules.

For a normal Hot Spots campaign, a starting named pilot should default to:

* Gunnery 4
* Piloting 5
* Alpha Strike Skill 4

Keep user-editable/custom pilot values supported.

Do not assume every newly-created pilot receives all campaign-start bonuses automatically, because pilots hired later use different rules. Campaign setup may explicitly initialize the starting pilots as needed.

### Injury handling

Remove the existing behaviour where a wounded pilot automatically recovers simply because they sat out one Sortie.

Pilot recovery is month-aware and must not be modelled as `one missed Sortie = healed`.

Use the existing wound/injury history as the basis for availability.

Prefer `wounds` as the authoritative current injury count and derive wounded/available state from it where practical. Avoid duplicated state that can become inconsistent.

Do not fully implement all healing costs and medical modifiers in this correction unless the existing workflow requires it, but ensure the current automatic one-Sortie recovery behaviour is removed.

## 3. Add a Contract Force / Contract Roster layer

The current implementation treats the full Campaign roster as the Contract force. This is incorrect for Hot Spots.

A Campaign may contain more units than can be brought on a particular Contract.

Add a persistent Contract roster concept, such as `ContractUnit`, `ContractRosterEntry`, or an equivalent association model.

The intended hierarchy is:

`Campaign Roster -> Contract Force -> Sortie Force`

Requirements:

* A Contract selects which Campaign Units are committed to that Contract.
* The Contract roster is constrained by Contract Scale rules.
* Campaign Units not committed to the active Contract remain part of the Campaign but are not eligible for Sorties belonging to that Contract.
* Sortie preparation must select from the Contract roster, not from the full Campaign roster.
* Preserve Campaign Unit history and identity; do not copy units unnecessarily if a relationship/association is sufficient.
* Preserve the existing Sortie snapshot behaviour so historical Sorties are not affected by later Campaign or Contract changes.

For Alpha Strike, enforce the applicable Contract PV and unit-count limits for the selected Contract Scale.

If the existing application already centralizes force-limit values elsewhere, reuse that logic rather than duplicating constants.

## 4. Enforce Sortie force limits

The current Sortie builder calculates point totals but does not sufficiently enforce Scale limits before a Sortie becomes Ready.

For Alpha Strike campaign play:

* Enforce the Sortie PV limit for the selected Sortie Scale.
* Enforce the Sortie unit-count limit for the selected Sortie Scale.
* A Sortie Scale may not exceed its Contract Scale.
* A Sortie may only use units committed to its Contract.
* Only available Campaign Units may be fielded.
* Invalid forces must not be allowed to transition to `Ready`.

Keep the force editable while the Sortie is in Planning.

Do not add BattleTech BV campaign support in this phase unless it already exists cleanly in the project. The current campaign workflow may remain Alpha Strike focused.

## 5. Correct Contract percentage validation

The current shared percentage validator limits Base Pay, Support, and Transportation to 0–100.

This is too restrictive because Hot Spots contracts can have Base Pay above 100%, including 110%.

Replace the generic assumption with term-specific validation.

Requirements:

* Base Pay must support values above 100% used by campaign contracts.
* Support and Transportation should use validation appropriate to their rule values rather than inheriting an arbitrary Base Pay limit.
* Avoid a single `0..100` validator if the terms have different legal ranges.
* Keep validation explicit and testable.

## 6. Separate transportation payment from actual travel expense

The current transportation calculation treats employer transportation coverage as a percentage of the actual travel expense.

Hot Spots allows the employer transportation entitlement/payment and the mercenary company's actual transportation cost to differ.

This distinction is important when company assets or special rules reduce actual transportation cost. In those cases, the mercenary may retain the excess employer transportation payment.

Refactor transportation accounting to distinguish at least:

* standard/gross transportation amount used by the Contract term
* employer transportation percentage
* employer transportation payment/entitlement
* actual transportation expense incurred by the Campaign
* net Warchest effect

The Warchest ledger should represent the true financial effect while retaining enough detail to explain how it was calculated.

Do not assume:

`employer payment = percentage × actual expense`

The user should still be able to manually override travel costs where campaign-specific rules require it.

## 7. Bind Support coverage to the originating Contract

Repair and rearming coverage must come from the Contract under which the damage or expenditure occurred, not whichever Contract happens to be active when the repair is completed.

The existing RepairOrder and RearmOrder already originate from a Sortie, and a Sortie belongs to a Contract. Use that historical relationship.

Example that must work correctly:

* Contract A provides 80% Support.
* A unit is damaged during Contract A.
* Contract A ends.
* Contract B begins with 20% Support.
* The original Repair Order is completed during Contract B.
* The repair must still use Contract A's applicable Support terms.

Requirements:

* Determine repair/rearm Support from the originating Sortie's Contract.
* Preserve this rule even after that Contract is completed.
* Do not recalculate historical Support using the currently active Contract.
* If an order has no originating Contract, fall back to an explicit/manual coverage value rather than silently using an unrelated active Contract.

## 8. Automatically calculate standard Repair Order costs

The current After Action flow creates Repair Orders with a gross cost of zero and expects manual entry later.

MechBay already has enough information to calculate the normal Hot Spots repair cost in most cases.

For standard units, calculate the suggested/default gross repair cost from unit tonnage and damage category:

* Armour only: tonnage / 2 SP
* Structure / Critical: tonnage × 2 SP
* Crippled: tonnage × 3 SP
* Destroyed but repairable: tonnage × 5 SP

Requirements:

* Calculate the default Repair Order gross cost automatically when After Action creates the order.
* Keep the repair cost editable/overridable for special campaign rules.
* Continue to apply applicable Support coverage separately.
* Preserve the existing rule that only the highest applicable damage category is paid.
* Do not generate a Repair Order for a truly destroyed unit.

Where existing campaign rules already model Clan/Mixed-Tech or other modifiers, preserve them. If they are not yet implemented, leave extension points rather than adding a large new subsystem in this phase.

## 9. Standardize campaign currency terminology on SP

Audit the campaign code and UI for `WP`, `Warchest Points`, or variable names/messages such as `salvage_wp`, `penalty_wp`, and similar campaign-facing terminology.

For the Hot Spots mercenary campaign system, standardize user-facing terminology on:

* `SP`
* `Support Points`
* `Warchest`

Internal field/parameter renames may be performed where they improve clarity and can be migrated safely.

Do not perform risky schema churn solely for cosmetic renaming if a user-facing terminology change is sufficient.

## 10. Preserve current architecture and history behaviour

Do not collapse the existing campaign models.

Preserve these existing design decisions:

* CampaignUnit is distinct from the physical Miniature.
* Physical miniatures are not deleted or marked destroyed when a Campaign Unit is destroyed.
* Named Pilots belong to the Campaign and may have a preferred/default Campaign Unit without being permanently attached to it.
* SortieUnit snapshots preserve the unit configuration and pilot actually fielded.
* Omni configurations are changed between Sorties, not during Sortie preparation.
* Damage, injury, repairs, rearming, configuration changes, travel, Contracts, Sorties, notes, and Warchest transactions retain historical records.
* Campaign time remains month-based rather than day-based.
* Multiple Sorties may occur during one Campaign month.

## 11. Deferred work — do not expand scope into these features yet

Do not implement the following as part of this correction unless a very small change is required to keep the corrected model extensible:

* full Named Pilot advancement / SP allocation system
* Named Pilot handicap calculations
* Battlefield Support Points (BSP) calculation and selection
* Hiring Hall automation
* Warchest debt
* full salvage purchase/ransom workflows
* automatic random contract generation
* BattleTech BV campaign-mode parity
* star-map/jump-route calculation
* Campaign PDF/Dossier generation

These belong in later campaign phases.

## 12. Tests and validation

Add or update pytest coverage for at least:

* default Campaign opening Warchest = 3,000 SP
* opening Warchest override
* named pilot 4/5 default
* wounded pilot does not automatically recover after sitting out one Sortie
* Contract roster selection
* units outside the Contract roster cannot be added to its Sorties
* Contract Scale PV/unit-count enforcement
* Sortie Scale PV/unit-count enforcement
* Sortie cannot become Ready when over its limits
* Base Pay values above 100%, including 110%
* transportation employer payment differing from actual travel expense
* excess transportation payment producing the correct net Warchest result
* Repair Order Support remains tied to the originating Contract after a new Contract becomes active
* automatic repair cost calculation for armour, structure/critical, crippled, and destroyed damage
* Repair Order cost override
* truly destroyed units cannot be repaired
* existing Sortie snapshots remain unchanged after later Campaign Unit changes

Run the existing test suite and Ruff checks after the changes. Fix regressions introduced by this phase.

## Completion criteria

This phase is complete when the existing campaign architecture remains intact, the rules mismatches above are corrected, the missing Contract Force layer exists, and the Campaign -> Contract -> Sortie -> After Action -> Repair workflow behaves consistently with the Hot Spots mercenary campaign rules currently implemented by MechBay.

## Prompt 4 Clarifications

Use the following decisions while implementing Prompt 4. These clarify rules and lifecycle questions that should not be guessed.

### Contract / Sortie Scale limits

For Alpha Strike, use these formulas:

- Contract unit count limit = `3 × Scale`
- Sortie unit count limit = `3 × Scale`
- Contract PV limit = `150 × Scale`
- Sortie PV limit = `100 × Scale`

This produces:

| Scale | Contract PV | Contract Units | Sortie PV | Sortie Units |
| --- | ---: | ---: | ---: | ---: |
| 1 | 150 | 3 | 100 | 3 |
| 2 | 300 | 6 | 200 | 6 |
| 3 | 450 | 9 | 300 | 9 |
| 4 | 600 | 12 | 400 | 12 |
| 5 | 750 | 15 | 500 | 15 |

The published Hot Spots table explicitly shows Scales 1–3 with this progression. Scales 4–5 should follow the same formula because MechBay already supports those Scale values.

Contract and Sortie limits are therefore **different for PV**, but use the **same unit-count limit**.

Do not implement the infantry half-unit rule in this phase unless it is already trivial within the current unit model.

### Contract roster lifecycle

Use the following lifecycle rules:

1. Contract roster membership may be edited while a Contract is `draft` or `active`.
2. A newly-created Contract roster starts **empty**.
3. The user explicitly selects which Campaign Units are committed to the Contract.
4. Units not committed to the Contract are not eligible for its Sorties.
5. A unit may not be removed from the Contract roster if it is referenced by a historical/non-editable Sortie.
6. If the unit is currently on a `planning` Sortie, block Contract-roster removal with a clear validation message such as:
   - `Remove this unit from the Planning Sortie first.`
7. Ready, Fought, After Action, and Closed Sorties must remain historically intact.

Do not silently remove units from existing Sorties when changing Contract roster membership.

### Pilot injury behaviour

For this phase, use the simple rule:

- `wounds > 0` => Named Pilot is unavailable and cannot be assigned to a Sortie.
- `wounds == 0` and pilot status is alive => Named Pilot may be assigned.

Remove the existing automatic behaviour where sitting out one Sortie clears the wounded state.

Provide a minimal manual recovery mechanism that can reduce/clear wounds while preserving injury/recovery history.

Do not implement full month-based wound healing limits, healing SP costs, MedBay modifiers, or other medical rules in this phase.

Named Pilot create defaults must be:

- Gunnery 4
- Piloting 5
- Alpha Strike Skill 4

Apply these defaults consistently in:

- model/service defaults
- campaign detail `Add Pilot` form
- any other campaign-facing pilot creation UI

### Contract percentage ranges

Use term-specific validation:

- Base Pay: `0–200%`
- Support: `0–100%`
- Transportation: `0–100%`

Do not use a shared `0–100` validator for all contract terms.

Allow arbitrary integer values within those ranges rather than forcing only published negotiation-step values.

Do not implement full `Straight` vs `Battle` Support semantics in this phase unless required by existing functionality. Keep the model extensible enough that a support type can be added later without redesigning Contract.

### Transportation accounting

Refactor travel accounting to distinguish:

1. **Standard transportation amount**
2. **Employer transportation payment**
3. **Actual transportation expense**
4. **Net Warchest effect**

Use:

`employer payment = standard transportation amount × Transportation %`

and:

`net SP = employer payment - actual transportation expense`

The employer payment must be editable/overridable.

For the standard Hot Spots transportation value:

- default standard transport amount = `300 SP × Contract Scale`

If optional jump tracking is already being used:

- allow a calculated travel amount from manually-entered jump count
- do not build a star-map or jump-route calculator
- manual override remains available

Do not assume employer transportation payment must equal actual expense.

This must allow cases where reduced actual transport cost results in the Campaign retaining excess employer transportation payment.

Do not implement travel-time Base Pay coverage rules in this phase unless required by the existing monthly workflow.

### Repair cost handling

After Action records one highest applicable damage outcome per Sortie Unit.

Generate at most one standard Repair Order for that unit from that After Action result.

Use:

- Armour only = `tonnage / 2 SP`
- Structure / Critical = `tonnage × 2 SP`
- Crippled = `tonnage × 3 SP`
- Destroyed but repairable = `tonnage × 5 SP`

Do not stack repair costs for multiple categories.

Do not generate a Repair Order for a Truly Destroyed unit.

The published rule states `tonnage / 2` for armour repair but does not provide a rounding rule.

Preferred implementation:

- support half-SP values cleanly if this can be done without disproportionate schema churn

If the current SP storage must remain integer-based for this phase:

- use `ceil(tonnage / 2)`
- document this as a MechBay implementation convention rather than a Hot Spots rule

Repair Order gross cost remains editable so special campaign rules can override the calculated amount.

### Opening Warchest ledger entry

For normal Campaign creation, default opening Warchest is 3,000 SP unless explicitly overridden.

Use:

- transaction type: `opening_balance`
- description: `Opening Warchest`
- gross amount: opening SP
- covered amount: `0`
- actual amount: opening SP
- resulting balance: opening SP

Remove wording that describes the opening Warchest as leftover force-building points.

### Deferred scope

Do **zero implementation work** for the deferred items unless a correction in Prompt 4 requires a small compatibility change.

Do not add speculative tables, fields, empty services, stubs, or placeholder UI for:

- full Named Pilot advancement
- Named Pilot handicap calculations
- Battlefield Support Points
- Hiring Hall automation
- Warchest debt
- salvage purchase/ransom workflows
- random contract generation
- BattleTech BV campaign parity
- star-map/jump-route calculation
- Campaign PDF/Dossier generation
- other deferred campaign subsystems

Prefer implementing only the current requirements rather than creating unused abstraction layers.

### Contract roster is an eligibility boundary

Treat the Contract roster as a real campaign rule boundary, not merely an organizational grouping.

The intended selection flow is:

`Campaign Roster -> Contract Roster -> Sortie Force`

A Sortie may only field Campaign Units that:

- are committed to its Contract
- are currently available
- fit within the selected Sortie Scale limits

Preserve SortieUnit snapshots so later changes to Campaign Units or Contract roster membership do not rewrite historical Sorties.

## Prompt 4 Clarifications — Addendum 2

Use the following decisions for the remaining implementation questions.

### 1. Jump-based transportation amount

Hot Spots provides two transportation modes.

#### Standard transportation

If jump tracking is not being used:

`Standard transportation amount = 300 SP × Contract Scale`

#### Optional jump tracking

If jump tracking is being used:

`Transportation amount = (50 SP + (50 SP × jump_count)) × Contract Scale`

Example:

- Contract Scale 2
- 3 jumps
- Base travel amount = `50 + (50 × 3) = 200 SP`
- Scale-adjusted transportation amount = `200 × 2 = 400 SP`

Do not multiply the normal 300 SP amount by jump count.

The player should be able to choose/use either:

- standard transportation
- jump-tracked transportation
- manual override where special campaign rules require it

Jump count is therefore mechanically meaningful when jump tracking is selected, not merely informational.

Travel time from jump tracking should continue to use the campaign month abstraction, but do not expand Prompt 4 into additional travel-time automation beyond what already exists.

### 2. Armour repair half-SP convention

Keep the existing integer-based SP and ledger fields for Prompt 4.

Do not introduce decimal/half-SP storage as part of this correction.

For Armour-only repairs use:

`ceil(tonnage / 2)`

Examples:

- 70 tons => 35 SP
- 65 tons => 33 SP
- 55 tons => 28 SP

Document this as a **MechBay implementation convention** because Hot Spots specifies `tonnage / 2` but does not specify how fractional SP should be rounded.

Do not change the broader Warchest schema to decimal values in this phase.

### 3. Wounds and the existing `wounded` flag

Make `wounds` the authoritative injury state.

#### After Action wound

When a named pilot receives a wound:

`wounds += 1`

Do not merely set the value to 1 because pilots may accumulate multiple wounds.

#### Pilot death

When a named pilot is killed:

- set status to `dead`
- clear any derived/legacy wounded flag if it still exists
- retain the current `wounds` value for historical information unless existing code requires otherwise

Pilot death/status takes precedence over wounds for availability.

#### Availability

Named Pilot eligibility should be derived from:

- `status == alive`
- `wounds == 0`

Therefore:

`status != alive OR wounds > 0 => unavailable`

Do not rely on the legacy `wounded` boolean for campaign rules.

If removing the `wounded` database field would create unnecessary schema churn, it may remain temporarily for compatibility, but:

- keep it synchronized from `wounds > 0`
- do not use it as an independent source of truth
- new business logic should use `wounds`

#### Manual recovery

The minimal recovery action should:

`wounds -= 1`

to a minimum of zero.

Do **not** automatically set all wounds to zero.

This allows a pilot with two wounds to require two recovery actions and leaves room for proper month-based healing limits later.

Each recovery action should create/preserve the existing pilot injury/recovery history record.

### 4. Manual pilot recovery UI

For Prompt 4, place the minimal recovery action on the **Campaign Pilots table/detail area only**.

For a wounded living pilot, expose a simple action such as:

`Recover 1 Wound`

Display the remaining wound count.

Do not add recovery controls to:

- Sortie screens
- After Action screens after the AAR has been committed
- monthly processing
- separate medical-management screens

Those can be added when the full healing system is implemented.

After Action records the wounds.

Campaign Pilot management performs the temporary/manual recovery action.

### 5. Contract roster limit enforcement timing

Hard-block Contract roster additions immediately when the proposed roster would exceed the Contract Scale limits.

Do not permit an intentionally invalid Contract roster.

For Alpha Strike:

- Contract PV limit = `150 × Scale`
- Contract unit-count limit = `3 × Scale`

When adding a Campaign Unit, calculate the resulting roster total before committing the change.

If the new unit would exceed either limit:

- reject the addition
- show a clear validation message containing the current and maximum values where practical

Example:

`Cannot add Warhammer WHM-6R: Contract force would be 167 / 150 PV.`

The Contract may remain `draft` with fewer than the maximum allowed PV/units.

The limits are maxima, not required targets.

Contract activation should also validate the roster as a defensive integrity check, even though normal UI operations should prevent an over-limit roster from being created.

Sortie Ready should independently validate its own Sortie limits.

### 6. Campaign Units with missing PV

A Campaign Unit with `point_value = None` must **not** be treated as zero PV.

Block that unit from being committed to an Alpha Strike Contract roster or added to an Alpha Strike Sortie until it has valid MUL/PV information.

Use a clear validation message, for example:

`This unit has no Alpha Strike Point Value and cannot be added to a campaign force.`

Do not provide a manual arbitrary PV field as part of Prompt 4.

The preferred correction is for the user to resolve/reselect the MUL variant so MechBay has authoritative unit data.

This prevents unknown unit values from silently bypassing Contract and Sortie Scale limits.

### Implementation principle

For these rules, prefer enforcing validity when the user performs the action rather than allowing invalid intermediate campaign state and detecting it much later.

Use defensive validation again at important lifecycle transitions such as:

- Contract activation
- Sortie Ready

but normal UI/service actions should already prevent invalid rosters and Sortie forces from being constructed.

## Prompt 4 Clarifications — Addendum 3

### 1. Campaign Units on multiple Contract rosters

A Campaign Unit may belong to multiple `draft` Contract rosters.

A Campaign Unit may belong to at most one `active` Contract roster at a time.

Therefore:

- Draft + Draft: allowed
- Active + Draft: allowed
- Active + Active: blocked
- Completed/Cancelled Contract membership is historical and does not restrict future Contracts

When activating a Contract, validate that none of its committed Campaign Units are already committed to another active Contract.

Do not make Contract roster membership globally unique across all unfinished Contracts.

Draft Contracts represent planning; an active Contract represents the actual current deployment.

### 2. Travel without a linked Contract

Continue allowing Campaign TravelEvents without a Contract.

Travel is a Campaign/location-history concept and may occur outside a Contract, such as travel to a Hiring Hall.

For travel with no linked Contract:

- standard transportation calculation may still be used
- jump-tracked transportation calculation may still be used
- actual transportation expense is charged to the Campaign
- employer transportation payment is always `0`
- Contract Transportation percentage does not apply
- manual transport-cost override remains available

Do not require a Contract simply to create travel.

### 3. Employer transportation payment rounding

Campaign SP fields remain integer-based.

For:

`employer payment = standard transportation amount × Transportation %`

round to the nearest whole SP using **half-up rounding**.

Examples:

- 112.4 => 112 SP
- 112.5 => 113 SP
- 112.6 => 113 SP

Do not rely on Python's default bankers-rounding behaviour for exact `.5` values.

The Hot Spots rules do not specify a percentage-rounding convention; treat half-up rounding as a MechBay implementation convention.

### 4. Contract roster Add Lance UX

Support both:

- add individual Campaign Unit
- add Campaign Lance

`Add Lance` should be atomic.

Before making changes:

1. resolve the eligible Campaign Units in the selected Lance
2. verify they all have valid PV
3. calculate the resulting Contract unit count
4. calculate the resulting Contract PV
5. verify the complete addition fits the Contract Scale limits

If the entire eligible Lance cannot be added:

- add none of it
- return a clear validation message explaining the limit or invalid unit

Do not silently add only the subset that happens to fit.

Individual unit add remains available for building mixed Contract forces.

### 5. Transportation mode control

Use three Travel transportation modes:

#### Standard

Calculate:

`standard transportation amount = 300 SP × Contract Scale`

If there is no linked Contract, use the relevant Campaign/default Scale if available, or require the player to provide the Scale/amount rather than inventing one.

#### Jump-tracked

Calculate:

`standard transportation amount = (50 SP + (50 SP × jump_count)) × Contract Scale`

Jump count is manually entered.

Do not build route calculation or a star map.

#### Manual

Allow the player to directly enter the standard/expected transportation amount.

### Employer payment

For a linked Contract:

`employer payment = standard transportation amount × Contract Transportation %`

Use half-up whole-SP rounding.

Employer payment should auto-fill but remain editable as an override.

For unlinked travel:

`employer payment = 0`

### Actual transportation expense

Actual expense must remain separately editable.

When a transportation mode calculates a standard value, default actual expense to that same calculated value:

- Standard mode => actual expense defaults to `300 × Scale`
- Jump-tracked => actual expense defaults to calculated jump cost
- Manual => actual expense defaults to the manually entered transportation amount

The player may then override Actual Expense to represent:

- owned transport
- subsidies
- special campaign rules
- DropShip benefits
- scenario-specific transportation modifiers
- other actual-cost differences

Calculate final Warchest impact as:

`net SP = employer payment - actual transportation expense`

Do not conflate employer payment with actual expense.