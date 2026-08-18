# MechBay Campaign Support — Prompt 3: After Action and Between-Sortie Activities

Extend the existing Campaign, Contract, and Sortie system with After Action processing and the core between-sortie campaign activities.

Preserve campaign history rather than overwriting or deleting historical state.

## After Action

Once a Sortie has been fought, allow it to enter After Action.

Add structured results for each Sortie Unit.

Support at least these campaign-level damage outcomes:

* no damage
* armour damage
* structure / critical damage
* crippled
* destroyed
* truly destroyed

Do not implement detailed tabletop armour-location or critical-hit tracking.

MechBay only needs enough detail to determine campaign consequences.

Also capture:

* pilot wounds/injury
* pilot death
* ammunition/rearming requirement
* Sortie victory/loss/result
* objectives/result summary
* combat pay
* salvage notes/data as appropriate
* MVP
* free-form After Action narrative notes

The narrative notes are important and must be retained for future campaign-history reporting.

## Campaign Unit History

Applying After Action results should update the Campaign Unit's current condition but must preserve historical damage events.

A repaired unit returning to Operational status must still retain its previous damage/repair history.

A truly destroyed Campaign Unit remains in history but cannot be fielded again.

Do not delete the associated physical MechBay miniature.

## Repair Orders

Add `RepairOrder` as a persistent object.

A Repair Order should support:

* Campaign
* originating Sortie
* Campaign Unit
* damage category
* gross repair cost
* Contract Support coverage
* other modifier/discount fields where useful
* actual Warchest cost
* campaign month
* repair status
* resulting unit availability
* notes

Suggested lifecycle:

`Pending -> Approved -> In Progress -> Completed / Cancelled`

Completing the Repair Order updates Campaign Unit condition and availability.

The Warchest impact must be recorded using the existing ledger.

## Repair Availability

Support the distinction between:

* Operational
* damaged but fieldable if applicable
* unavailable due to repair
* destroyed
* truly destroyed

Multiple Sorties may occur in the same campaign month, so repair availability must not assume one Sortie equals one month.

## Pilot Injury and Healing

Track pilot wounds/injuries historically.

Pilot availability should be derived from current injury/death state rather than only a manually toggled boolean.

Add a healing/recovery activity that:

* belongs to Campaign
* occurs in a campaign month
* updates wounds/injury state
* records any Warchest cost
* preserves injury history

Dead pilots remain in campaign history.

## Omni Reconfiguration

For Campaign Units identified as Omni units, add a between-sortie reconfiguration action.

Requirements:

* unit must be an Omni-capable unit
* unit must be fully repaired
* user selects another valid MUL configuration
* configuration history is preserved
* current Campaign Unit configuration is updated
* any SP/Warchest cost is recorded
* completed Sorties retain their original configuration snapshots

Do not allow normal non-Omni units to freely change variants.

## Rearming

Add a basic between-sortie rearming activity where needed.

Record:

* Campaign Unit
* campaign month
* gross cost
* Contract Support coverage if applicable
* actual Warchest cost
* notes

Use the Warchest ledger.

## Monthly Campaign Processing

Add an explicit `Advance Campaign Month` workflow.

Before committing the month advance, show a summary of relevant state such as:

* current location
* active Contract
* current Contract month
* maintenance due
* Base Pay due
* travel status
* outstanding repairs
* pilot recovery
* current Warchest

Require explicit confirmation before applying monthly transactions.

Do not automatically advance the month when a Sortie closes.

## History

Preserve history for:

* Campaign locations/travel
* Contracts
* Sorties
* pilot assignments
* unit configurations
* damage events
* Repair Orders
* pilot wounds/healing
* Warchest transactions
* notes

Prefer append/history records over destructive overwrites.

## Reporting Preparation

Do not yet generate a PDF.

Ensure the data model retains enough structured and narrative history for a later Campaign Dossier report containing:

* campaign timeline
* contracts
* travel
* roster
* pilot history
* Sorties
* After Action narratives
* damage and repairs
* losses/acquisitions
* Warchest history

## Tests

Add tests for:

* After Action damage application
* Repair Order generation
* Contract Support coverage
* Repair completion
* truly destroyed unit behaviour
* pilot wounds/recovery
* dead pilot history
* Omni reconfiguration restrictions
* Sortie configuration snapshot preservation
* rearming ledger transactions
* explicit month advancement
* multiple Sorties in the same month
