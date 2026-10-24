# Dashboard UX contract

Language: Persian (RTL), responsive mobile/desktop. Status-first, no dense operator CLI.
Theme: accessible high-contrast dark and light. No real foreign IPs visible by default; privileged reveal with re-authentication and audit.

## Navigation
- Overview: Maya1, Maya3, ~290 users, combined GB/day, active flow count, uptime, circuit state and warnings.
- Foreign Fleet: F1..F4 cards with transport badge, both gateway paths (Maya1→F# / Maya3→F#) and separate health. Primary vs emergency roles.
- Replace Server: 6-step guided wizard. Step 1 select logical foreign; 2 impact preview; 3 enroll new foreign / one-command pinned install; 4 dual Iran validation; 5 signed prepare/commit/dual ACK + canary; 6 graceful drain + explicit cleanup.
- Incidents: outage reasons; tests, errors, timestamps, first observed, last healthy, active/cleared.
- Policies: capacity targets, quotas, emergency reserve and failover. No weakening of security policy with a toggle.
- Audit & Security: operator activity, device cert rotation status, generations, signed release build hash.

## Buttons and semantics
Replace is gated by RBAC, MFA, healthy old-path fallback and inventory lock. No single-click destructive swap. Preview is never apply.
'Applied' means BOTH gateways acknowledged that generation and active new-flow route validation completed; until then 'Partially applied' is a WARNING with safe rollback.
Delete old foreign is disabled until canary burn-in, dual ACKs, old-flow drain and rollback grace are satisfied. Permit preauthorized automatic cleanup (opt-in at replacement start), otherwise separate confirmation.

## Dashboard/backend API (future)
- GET /api/v1/topology → scrubbed inventory snapshot and current_generation
- GET /api/v1/edges → per-edge health/scores/capacity
- GET /api/v1/replacements → operation timeline / acknowledgements
- POST /api/v1/replacements → propose authenticated change
- POST /api/v1/replacements/{id}/enroll → issue short lived secure enrollment
- POST /api/v1/replacements/{id}/prepare → dual validate and prepare
- POST /api/v1/replacements/{id}/commit → signed generation ACK sequence
- POST /api/v1/replacements/{id}/drain → preserve old node
- POST /api/v1/replacements/{id}/cleanup → step-up MFA + full audit
- POST /api/v1/replacements/{id}/rollback → signed safe prior config

**Not implemented:** API listed above is a contract, not live endpoints. The checked-in HTML is explicitly a static prototype with write actions disabled.
