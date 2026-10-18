## Prompt 6 Addendum — Aces Between-Sorties Purchases and Sales

Adjust the Aces campaign workflow so that unit purchases and sales occur in a distinct **Between Sorties** phase.

This applies to `aces` Campaigns only.

Do not change Chaos Campaign workflow unless required for shared infrastructure.

### Campaign flow

Use the following Aces progression:

`Play Sortie -> After-Sortie Resolution -> Finalize Sortie Report -> Between Sorties -> Prepare Next Sortie`

The After-Sortie phase should contain only the consequences of the Sortie itself.

The Between-Sorties phase is where the player may change the persistent Player Force before preparing the next Sortie.

### After-Sortie Resolution

Complete all of the following before the Sortie is finalized:

- record Sortie outcome
- apply Story Keywords
- determine casualties
- calculate Income
- calculate Expenses
- apply mandatory repairs
- apply rearming/personnel expenses
- determine Earnings
- allocate Named Pilot SP
- award MVP bonus
- allocate each pilot's gained SP
- update pilot advancement/history
- apply the remaining Sortie Earnings to the Warchest
- record Next Steps / next scenario guidance
- finalize the immutable Sortie Report

Do not include later unit purchases or sales in the Sortie's own Income, Expenses, Earnings, or Net SP result.

### Finalized Sortie Report

The Sortie Report should end with the Campaign state immediately after that Sortie has been resolved.

At minimum show:

- Total Income
- Total Expenses
- Earnings
- Named Pilot allocation
- MVP bonus
- Warchest before Sortie
- Warchest change from Sortie
- Warchest after Sortie

Example:

`Warchest after Sortie: 2,490 SP`

Purchases and sales made afterward must not retroactively change this value.

Historical Sortie Reports remain immutable.

### Between Sorties phase

Once the previous successful Sortie is finalized, the Campaign enters a normal **Between Sorties** state.

During this phase allow:

- purchase additional units
- purchase replacement units
- sell eligible existing units
- review Player Force
- review Named Pilots
- review Warchest
- review Story Keywords
- review Next Steps
- begin preparation for the next Sortie

Do not require the purchase/sale step to occur. The player may proceed directly to preparing the next Sortie if no roster changes are desired.

### Purchases

Aces unit purchases occur Between Sorties.

Purchase cost remains:

`standard Skill 4 PV × 40 SP`

When purchasing:

- use existing MUL search/select functionality
- show unit/variant and PV
- calculate purchase cost
- deduct cost from the current Warchest
- create a new CampaignUnit
- add it to the active Player Force
- preserve purchase history
- do not create a physical Miniature automatically

The purchase should create a normal Campaign/Warchest transaction associated with the Between-Sorties activity, not with the preceding Sortie's Income/Expense totals.

A purchased replacement is always a new CampaignUnit.

Do not reuse the identity of a destroyed CampaignUnit.

### Sales

Aces unit sales also occur Between Sorties.

Sale value remains:

`standard Skill 4 PV × 20 SP`

Only eligible repaired active units may be sold.

When selling:

- add proceeds to current Warchest
- retire/remove the CampaignUnit from active Player Force
- preserve CampaignUnit history
- preserve physical Miniature separately
- create a normal Warchest/Campaign history transaction

The sale must not be recorded as income from the previous Sortie.

### Mandatory repairs still occur first

A damaged recoverable unit cannot avoid the required Aces repair expense by moving directly into the Between-Sorties sale workflow.

Required sequence:

`Sortie damage -> mandatory repair expense -> Sortie finalized -> unit may then be sold Between Sorties`

Truly Destroyed units:

- are not repaired
- are not eligible for normal sale
- remain historical only

### Campaign activity history

Campaign history should make the distinction between Sortie results and Between-Sorties transactions clear.

Example timeline:

- Sortie 5 completed
- Sortie 5 Earnings: +410 SP
- Warchest after Sortie: 2,490 SP
- Purchased Phoenix Hawk PHX-3PL: -1,440 SP
- Sold Locust LCT-1V: +400 SP
- Warchest before Sortie 6: 1,450 SP

Do not fold the purchase/sale transactions back into Sortie 5's report.

### Campaign summary

When the Campaign is Between Sorties, show a clear section such as:

`Between Sorties`

with:

- current Warchest
- current active Player Force
- purchases/sales since last Sortie
- current Named Pilots
- Story Keywords
- Next Steps / Next Sortie
- action to prepare the next Sortie

### Sortie lifecycle

Do not allow a new Sortie to become `Ready` while the previous successful Sortie still has unfinished After-Sortie processing.

Once the previous Sortie is finalized:

- campaign roster changes are allowed
- purchases/sales are allowed
- the next Sortie may be created/prepared

Do not require a separate persisted Campaign status if the existing lifecycle can derive this state cleanly from the most recent Sortie.

Avoid unnecessary schema changes.

### Reporting

The distinction must remain clear in reporting:

**Sortie Report**
- only that Sortie's persistent consequences

**Campaign Timeline / History**
- Sortie results
- purchases
- sales
- other Between-Sorties roster/accounting changes

**Player Force**
- current active roster after any Between-Sorties changes

### Tests

Add or update tests for at least:

- purchase cannot alter a finalized Sortie Report
- sale cannot alter a finalized Sortie Report
- purchases occur after Sortie finalization
- sales occur after Sortie finalization
- damaged recoverable unit must be repaired before it can be sold
- Truly Destroyed unit cannot be sold
- purchase creates a new CampaignUnit
- sale removes unit from active Player Force but preserves history
- purchase transaction changes current Warchest
- sale transaction changes current Warchest
- purchase/sale transactions are not included in preceding Sortie Income/Expenses
- next Sortie cannot become Ready while previous After-Sortie processing is incomplete
- next Sortie can be prepared once previous Sortie is finalized
- Campaign history shows Between-Sorties purchases/sales separately
- Chaos Campaign behaviour remains unchanged

Run the full pytest suite and Ruff after the change.

Do not accept regressions to Chaos Campaign support.