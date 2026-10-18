## Prompt 6 Addendum — Aces Mandatory Repairs Before Selling

Adjust the Aces After-Sortie and unit-sale workflow to match the Aces campaign rules.

This change applies to `aces` Campaigns only.

Do not change Chaos Campaign repair behaviour.

### Aces repairs are mandatory

For a successful Aces Sortie, every Campaign Unit that is damaged but **not Truly Destroyed** must be repaired as part of After-Sortie processing.

Do not allow the player to:

- defer the repair to a later Sortie
- leave the unit sidelined to avoid the repair expense
- cancel the repair to save SP
- scrap/sell the damaged unit before paying the repair cost

The Aces rules treat repair as a mandatory Sortie expense before later campaign activities.

### Repair timing in the Aces After-Sortie flow

Use this order:

1. Determine casualties
2. Determine required repairs
3. Calculate and apply repair expenses
4. Calculate other Sortie expenses
5. Determine Earnings
6. Allocate Named Pilot SP
7. Apply remaining Earnings to Warchest
8. Purchase or sell units

A unit that survives the Sortie and is not Truly Destroyed should be fully repaired before reaching the purchase/sale step.

### Aces RepairOrder behaviour

Continue using `RepairOrder` for history/accounting where practical, but treat Aces repair orders differently from Chaos repair work orders.

For Aces:

- create the RepairOrder from the After-Sortie damage result
- calculate the Aces Size-based repair cost automatically
- mark the repair as mandatory
- include the repair cost in the current Sortie expenses
- complete/apply the repair as part of successful After-Sortie finalization
- restore the Campaign Unit to fully repaired/available state
- preserve the RepairOrder and DamageEvent as historical records

Do not expose normal Aces repair controls such as:

- Cancel Repair
- Defer Repair
- Repair Later
- Leave Unavailable

unless a future Aces rules source explicitly adds such options.

The existing flexible RepairOrder lifecycle may remain available for Chaos Campaigns.

### Truly Destroyed units

A Truly Destroyed Aces unit:

- is not repaired
- is removed from active Player Force availability
- remains in campaign history
- cannot be sold for normal sale value
- does not delete or alter the physical Miniature record

Do not create a mandatory RepairOrder for a Truly Destroyed unit.

### Selling units

Aces unit sales occur **after repairs and pilot advancement/accounting** in the purchase/additional-units step.

A unit sold from the Player Force must therefore be in its normal repaired state.

Sale value remains:

`standard Skill 4 PV × 20 SP`

Requirements:

- add sale proceeds to Warchest
- retire/remove the CampaignUnit from active Player Force
- preserve the CampaignUnit and its service history
- preserve the physical Miniature separately
- record the sale in WarchestTransaction and campaign history

Do not calculate a discounted damaged-unit sale value.

Do not offer a `scrap` action for recoverable damaged units as part of Aces unless a future rules source explicitly supports it.

### Negative Warchest remains valid

Mandatory repairs may cause Sortie expenses to exceed Sortie income and may reduce the Warchest below zero.

Do not allow the player to avoid mandatory repairs merely because the repair is expensive.

For Aces:

- apply the required repair expense
- allow negative Warchest
- skip Named Pilot advancement if there are no positive Sortie Earnings available
- continue the campaign

Do not substitute Chaos Warchest Debt rules.

### UI

On an Aces After-Sortie screen, make the mandatory nature of repairs clear.

Suggested wording:

`Required Repairs`

rather than a generic optional work-order queue.

For each damaged recoverable unit show:

- unit
- damage category
- Size
- calculated repair cost
- resulting repaired state

Do not show optional defer/cancel controls.

In the later Purchase/Sale section, only show currently active/repaired units as eligible for normal sale.

### Tests

Add or update tests for at least:

- damaged recoverable Aces unit always generates a required repair
- required repair is included in current Sortie expenses
- Aces repair cannot be cancelled/deferred through normal workflow
- recoverable unit is fully repaired after successful After-Sortie finalization
- Truly Destroyed unit does not generate a RepairOrder
- Truly Destroyed unit cannot be sold normally
- damaged unit cannot be sold before repair
- repaired unit can later be sold for `PV × 20`
- mandatory repair may push Warchest negative
- negative Warchest does not cancel required repairs
- Chaos repair deferral/cancellation behaviour remains unchanged

Run the full pytest suite and Ruff after the change.

Do not accept regressions to Chaos Campaign support.