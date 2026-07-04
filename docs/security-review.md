# Security review · Expense approvals

## Finding CF-01 · A North reviewer could read a South expense

**Impact:** Cross-customer disclosure of expense details. **Lab priority:** High. A valid reviewer token and a foreign claim ID are sufficient. A link copied into a support ticket could supply the ID. This scenario assumes the reviewer already knows it.

### Reproduction

1. Start the local API with `python -m claimfence` from the project root. Use the curl command printed for Mara. It requests Lee's rail fare in North and returns 200.
2. Keep the bearer token and change the path to `/claims/d3ca7323-cc89-4d32-a40a-754329113ae7`. This is Vale's expense in South. The reference service returns 404 with `{"error":"not found"}`.
3. In another terminal run `python -m checks.mutations`. The `unscoped-item` experiment makes the tenant condition ineffective in an isolated copy. The `mara/read/vale` case sends the same request from a fresh Mara session and receives 200. The captured response includes the following synthetic data.

```json
{
  "id": "d3ca7323-cc89-4d32-a40a-754329113ae7",
  "owner": "vale",
  "cents": 9100,
  "purpose": "Airport transfer",
  "status": "pending"
}
```

### Cause and fix

The weakened query still checked whether Mara held a reviewer role. Once it stopped checking the expense's tenant, that role applied to every customer. The list still looked correct, so testing only the list would have missed the direct lookup.

The reference query requires both `id = ?` and `tenant = ?` before evaluating ownership or reviewer privileges. The API gets the tenant from Mara's stored membership. The approval path uses the same lookup, which matters because an incorrect scope there can also authorize a change.

### Retest

The weakened item lookup broke eight matrix cases. They include both cross-tenant reads and approvals. Restoring the tenant predicate brings the full matrix back to 55/55. The legitimate North approval stays available. [Per-request results](../evidence/matrix.json) · [Captured failures](../evidence/mutations.json)

## Three other regressions the suite caught

| Deliberate change | Observable effect | Failed matrix cases |
| --- | --- | ---: |
| Drop tenant filtering on the list | Mara's list gains Vale's expense. Both the correct and broken responses return 200. | 2 |
| Remove the self-approval guard | Mara approves her own lunch. The database records Mara as the reviewer. | 2 |
| Expose the private note in the serializer | Lee's authorized expense read now contains `internal_note`. | 10 |

The counts come from separate runs, each with exactly one change. Four detected faults measures sensitivity to these four mistakes. Untested policy mistakes remain possible.

## Why inspect the database?

Finance needs an approval to mean that a different authorized person reviewed the expense. A response code alone cannot establish who was recorded or whether a denied request changed the claim. Every matrix case therefore snapshots the expense rows and the journal before and after the HTTP request.

The workflow tests also force the journal insert to fail. The service returns 500, the claim stays pending, and a retry succeeds after the injected fault is removed. Another test sends two approvals together. One receives 200, one receives 409, and the database contains one decision.
