# ClaimFence

**Authorization testing for a multi-tenant expense API** · Python · SQLite · GitHub Actions

Mara reviews expenses at North. She can approve Lee's rail fare, but she cannot sign off on her own lunch or open an expense from South. ClaimFence turns those rules into HTTP tests, then introduces four small policy bugs to find out whether the tests would actually catch them.

**Start with the case study:** [How a missing tenant check exposed a reimbursement](docs/security-review.md). It follows one request from the leaked response through the fix and retest.

## Run it

Open a terminal in the repository root. Use Python 3.11 or newer with SQLite support. All dependencies are in the standard library. Each run starts temporary servers on the loopback interface and creates fresh synthetic data.

```sh
python verify.py
```

On Windows, `py -3 verify.py` also works with the Python launcher. On Linux or macOS, use `python3 verify.py` if that is your Python command. Allow about a minute for the full run. The command exits with an error if the API breaks its policy or the tests miss an expected regression.

| What runs | What to look for |
| --- | --- |
| Workflow and isolation tests | 11 tests, including simultaneous approvals, transaction rollback and role changes |
| Authorization matrix | 55/55 cases pass on the reference service |
| Mutation study | Four deliberate bugs detected. Each produces a named failing request |

Want to inspect a request yourself? Run `python -m claimfence`. It prints the local address, four temporary bearer tokens and a working curl example. Run that example in a second terminal. Replace Lee's claim ID with Vale's ID from the case study while keeping Mara's token. The first request returns Lee's expense. The second returns a 404. Stop the server with Ctrl+C to discard its data.

## What the policy allows

| Caller | List and read | Approve |
| --- | --- | --- |
| Employee | Own claims | Never |
| Reviewer | All claims within their organization | Pending claims belonging to another person in their organization |
| Guest | No access | No access |

An invisible or missing claim returns the same 404 body. A person who can see a claim but cannot approve it receives 403. A second authorized approval returns 409. Internal review notes are private for every API role.

## Where to look

- [Policy table](checks/policy.csv) gives the expected result for each actor and claim owner. The API does not read this file.
- [Service policy](claimfence/policy.py) contains the SQL scopes, public response fields and approval transaction.
- [HTTP checks](checks/matrix.py) compare the response, the stored claims and the approval journal for each case.
- [Mutation runner](checks/mutations.py) changes one rule in a temporary copy and checks for a specific failure. The normal server always loads the reference policy.
- [Threat model](docs/threat-model.md) records trust boundaries, business impact and scope.
- [Matrix evidence](evidence/matrix.json) and [mutation evidence](evidence/mutations.json) contain the machine-readable results. Run `python verify.py` to regenerate both.

## Scope

ClaimFence is a local lab. All customers and expenses are fictional, and the measurements describe its own test suite rather than a production service.
