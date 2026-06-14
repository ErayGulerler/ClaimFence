# Threat model

## System and assets

Two fictional organizations use one expense service. Each person belongs to one organization. Each claim has one owner. The assets are expense details, a private review note, the approval state and the identity recorded for each decision. An approval represents authorization to reimburse someone. Money movement is outside this lab.

```text
Client holding a session token
       |  untrusted HTTP method, path, headers and body
       v
Loopback API  ->  session lookup  ->  person ID
                                         |
                                         v
SQLite transaction: membership + claim scope + decision
                                         |
                                         v
                            approved claim + journal row
```

A local operator creates test identities and owns the database. API callers may supply any ID and header, know a foreign UUID, replay a request or send competing requests. The service trusts the session map and the database. An API caller has no direct database access.

## Abuse cases and controls

| What someone tries | Business consequence | Control and evidence |
| --- | --- | --- |
| Change a claim ID or use the list to see another organization | Exposure of another customer's expense details | Scope both lookups by tenant. Matrix tests cover existing foreign IDs and a nonexistent ID. |
| Read a coworker's claim as an employee | Disclosure within one organization | Employees can see only their own claims. `lee/read/oren` verifies a same-tenant denial. |
| Send a role or tenant override, or keep using old reviewer rights after a demotion | Unauthorized review | Resolve the person's current role inside the database transaction. Tests spoof headers and demote a live session. |
| Approve one's own expense | A person can authorize their own reimbursement | Compare owner and reviewer before the write. The self-approval mutant demonstrates the effect on the journal. |
| Read a private note or submit arbitrary approval fields | Internal notes leak or clients influence accounting state | Return an explicit public projection. Approval accepts an empty body. Tests validate the full JSON shape. |
| Race or retry an approval, or interrupt journal creation | Duplicate decisions or an approved expense with missing evidence | Serialize the decision and commit the claim and journal together. Test concurrent requests and a forced write failure. |

## Design choices and limits

- **Why SQLite?** A real transaction lets the test force the second write to fail and inspect whether the first one rolled back. SQLite serializes writers, which keeps this demonstration easy to reason about. It does not measure throughput for a busy expense platform.
- **Why a separate policy table?** Reviewers can inspect expected permissions without reading SQL. The matrix runner never asks the service which permissions it should expect. The table covers five callers, four seeded claims and a missing ID. A separate test adds 24 foreign claims across three other organizations and checks whether North's observable view changes.
- **Why temporary tokens?** The project focuses on authorization after authentication. The local operator sees every demo token for manual testing. Sessions last for the process lifetime. Federation, token theft, TLS and production rate controls would need their own design.
- **What is still exposed?** The 404 tests compare the HTTP status and parsed JSON. They do not evaluate timing differences. A database operator can edit the journal. A real audit trail would need restricted access, retention and independent storage. There is no accounting integration, attachment processing or partial reimbursement flow.

## References

OWASP's object-level authorization guidance informs the foreign-ID tests. Its authorization testing guidance informs the independent role, operation and resource matrix. [OWASP API1:2023](https://api-security.owasp.org/editions/2023/en/0xa1-broken-object-level-authorization/) · [OWASP Authorization Testing Automation](https://cheatsheetseries.owasp.org/cheatsheets/Authorization_Testing_Automation_Cheat_Sheet.html)
