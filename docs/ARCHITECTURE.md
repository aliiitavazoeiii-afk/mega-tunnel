# System architecture

## Physical and logical view

```
Client's unchanged VLESS/REALITY configuration
          |                      |
       MAYA1                   MAYA3
     x-ui 2.9.4             x-ui 2.9.4
          |                      |
   Mega Router A           Mega Router B
    primary F1,F2           primary F3,F4
    emergency F3,F4         emergency F1,F2
       \       \             /      /
        F1      F2          F3      F4
      Naive    XHTTP      Naive    XHTTP
```

No fifth external server. No Cloudflare, Bridge or required UDP link. Both gateways have authenticated access to all four foreign exits, but normal traffic uses local primaries. Emergency cross-routing is enabled only with real spare capacity.

## Data path

x-ui forwards approved client traffic to a local Mega Router SOCKS endpoint only after authenticated configuration validation. The Router chooses an **egress flow** using live edge health, shared daily-byte budget, effective capacity, sticky affinity and transport compatibility. Transport adapters do real outbound traffic; the controller never carries client data.

**One TCP flow = one chosen foreign node** until closed. Do not pool everybody into one shared TCP stream or switch live connections between foreign IPs. Reconnect on new sockets is the honest failover contract.

Transport candidate A: NaiveProxy over TCP/TLS HTTP/2. Candidate B: Xray XHTTP+REALITY over TCP. These are not interchangeable until measured under real load. UDP support for apps is a distinct release track and must not be falsely promised with TCP-only upstream links.

## Control plane and replacement

Inventory is keyed by stable `foreign_id` (F1...F4), transport and `generation`; IP address is an attribute, not the identity. A controller with a **durable transactional state store** coordinates changes:

1. User selects logical F2 and enters replacement foreign endpoint out of band.
2. Generate a short-lived **single-use enrollment** token; show one authenticated/pinned installer command; never embed permanent secrets.
3. Replacement foreign enrolls through an authenticated channel. Check transport binary digest, server identity, egress, resource/capacity.
4. Both Maya1 and Maya3 agents independently validate candidate foreign from their networks.
5. Controller writes immutable new generation `G+1` and performs **prepare** on both gateways. Either rejection aborts.
6. Commit a signed generation. Both gateways switch *new flows only* to candidate in canary/ramp; the old node keeps draining.
7. Controller marks **COMPLETE only after BOTH apply ACKs**, reconciles timeouts, and retains old generation for rollback.
8. Old server cleanup is explicit and delayed.

A single controller loss is allowed (control plane temporarily unavailable); existing agents keep last-known-good signed config. The controller must enforce leader fencing and transactional epochs. Eventually use Postgres or equivalent with leases/fencing, never unsynchronized editable JSON on the two gateways. When partitioned, **NO mutation**, not best-effort divergent updates.

## Health and balancing

Edge identity: `(iran_id, foreign_id, transport_id)`. State machine:
HEALTHY → SUSPECT → QUARANTINED → PROBATION → HEALTHY. Passive failures trigger suspicion; targeted active checks can confirm; cooldown plus minimum success streak prevents thrash. A health check OK doesn't prove user app QoE.

Router fairness targets *measured bytes* and capacity rather than counting users or sessions. Sticky destination policies favor IP continuity without pinning indefinitely to a failed node. Fair-share 500GB/day ÷ 4 = 125GB per foreign, *not* a hard anti-filter limit; 250GB/day on one foreign when one of a pair fails unless cross reserve absorbs traffic.

No claims of hiding total bytes: encryption conceals content, not traffic volume/timing. Different independent transports reduce correlated failures but cannot guarantee DPI resistance.

## Operations and deployment

- Foreign enrollment: one audited command **only after signed installer exists**.
- Gateway deployment: canary with x-ui detach/rollback and no active x-ui restart during routine foreign rotation.
- Observability: edge success/failure, rtt percentile, connection setup, sustained byte-rate, cap pressure, circuit transitions, generation drift.
- Secrets: encrypted at rest on management controller, short-lived certs, no key in argv/logs.
- This design is a specification, not an already deployed system.
