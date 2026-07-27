# DumbMoney Core integration

Dummy remains the sovereign Kalshi venue cell. DumbMoney supplies an
additional signed ceiling; it does not supply a live session, enable
`configs/live_submit.json`, change local caps, resolve credentials, or bypass
`LiveBrokerFirewall`.

## Wire contract

`CapitalEnvelopeAdapter` verifies:

- `dumbmoney.signed-envelope.v1` using Ed25519 over canonical JSON of every
  wrapper field except `signature`;
- unpadded URL-safe base64 signatures and a signer key ID equal to the
  lowercase SHA-256 of the raw 32-byte public key;
- an event ID equal to the lowercase SHA-256 of canonical wrapper fields
  excluding `event_id` and `signature`;
- a `dumbmoney.capital-envelope.v1` body whose digest, venue, account hash,
  equal-count strategy/passport/promotion hashes, exact broker instrument IDs,
  UTC window, policy epoch, and integer-cent limits all match exactly;
- strictly increasing source sequence and global fencing generation, with a
  maximum-ever fence high-water mark so an older lease cannot revive after a
  newer lease expires;
- `max_order_risk_cents <= max_correlated_risk_cents <=
  max_open_risk_cents`, plus enough remaining daily-loss capacity for the
  proposed order rather than only checking whether the prior loss reached the
  ceiling.

The cross-repository fixture is mirrored at
`tests/fixtures/dumbmoney/signed-capital-envelope.v1.json`. It contains a
public key and signed envelope but no private key.

## Local authority intersection

When an adapter is installed on `LiveBrokerFirewall`, a request must carry the
exact envelope ID, strategy hash, passport hash, promotion hash, and fencing
generation. Dummy derives `event_contract:<exact contract ticker>` at the
trusted sink and requires that exact identifier in `authorized_instruments`;
prefixes, classes, and globs do not authorize an order.
Dummy evaluates all existing local risk, authority, allowlist, exposure,
frequency, and order caps first. The signed grant is then evaluated as another
deny-only ceiling. Both the external reservation and Dummy's existing
exposure reservation must persist before the broker transport can be called.

The adapter is opt-in at construction so the standalone Dummy runtime remains
backward compatible. Supplying capital-binding fields without an installed
adapter fails closed.

## Broker bootstrap and journal

An adapter cannot reserve risk until it has a fresh, account-bound broker
bootstrap receipt:

- `dummy.broker-bootstrap.flat.v1` proves a broker-observed empty order and
  position book.
- `dummy.broker-bootstrap.inherited-exposure.v1` records inherited open risk
  and consumes the signed grant before any new request.

No receipt means unknown exposure, never a flat account. Observations must be
strictly increasing and are bound to a broker-snapshot digest.

Production uses indexed SQLite WAL journals with `synchronous=FULL`,
`BEGIN IMMEDIATE` cross-process conditional appends, immutable-event
triggers, an event hash chain, bounded indexed kind/outbox reads, and a full
rescan whenever SQLite reports an external data-version change. The
broker-bootstrap and command-feed polling hot paths validate only their
indexed latest kinds, so five-second polling does not repeatedly materialize
the full journal. JSONL remains a compatibility implementation for isolated
tests, not the Windows service hot path.

An internal database hash chain cannot detect replacement with an older,
byte-for-byte valid database image. The runner therefore anchors three exact
local heads in Core's independently persisted signed ledger:
`capital-operational`, `command-feed`, and the revisioned semantic digest of
`live-exposure`. Each stream is account-, schema-, and name-bound. Core rejects
a lower sequence or a different digest at the same sequence. Dummy verifies
the Core envelope, independently recomputes the ledger-event proof, verifies a
fresh Core-signed request-bound checkpoint, and anchors before broker reads and
again after cycle mutations. A rollback cannot regain execution readiness.

Caller-authored local-failure receipts cannot release a capital reservation.
Terminal order and settlement recovery instead require typed, service-signed
broker witnesses exactly bound to the dispatch claim, account, subaccount,
client order ID, broker order ID, order terms, terminal state, observation
window, and local exposure projection. Ambiguous outcomes remain reserved;
filled capital is released only after venue exposure is projected, and that
position exposure remains until a stable position-absence read plus a matching
settlement witness.

## Core contract authority

Each passport and promotion resolution must include the frozen
`dumbmoney.cell-authority-state.v1` projection inside the Core-signed
checkpoint. Dummy verifies current kill-clear and LIVE desired mode, policy
and mandate identity, capital/fence/strategy/passport/promotion bindings,
capital and contract ledger-event continuity, at least two unique current
PASS facts from at least two courts, and evaluator signer IDs from a sealed
role-disjoint keyring. Promotion and passport must resolve from the same
authority state. The binding expires at the earliest contract, capital, or
`authority_valid_until` boundary and is resolved again at final use.

## Core command feed

`CoreCommandFeedConsumer` is an injected, local-only `poll_once` API. It has
no HTTP client, retry loop, scheduler, background thread, broker writer, or
import-time side effect. A supervised runner must inject:

- a GET-only loopback transport for
  `/v1/cells/dummy_kalshi/commands?after=N&cursor=<digest>&limit=L`;
- an OS-secret-backed `dummy_kalshi` cell bearer provider distinct from the
  operator token;
- a sealed release-role bundle containing disjoint pinned keyrings: Core keys
  for page checkpoints and capital grants, and operator keys for kill and
  desired-mode envelopes;
- the account-pinned capital adapter and a separate operational journal for
  feed state;
- idempotent authority-reducing handlers that assert local KILL or PAUSE.

The consumer first verifies the Core Ed25519 signature over the exact
`dumbmoney.cell-command-checkpoint.v1` canonical JSON. Every top-level cursor,
head digest, observation time, required action, and ordered command projection
must byte-canonically mirror that checkpoint. `has_more` is derived from the
signed next/head sequences rather than trusted as an unsigned assertion.
Each poll generates 32 cryptographically random bytes and sends the lowercase
hex value as `request_nonce`; the same value must appear in the page and its
signed checkpoint. A captured response therefore cannot satisfy a later
request even while its observation timestamp remains fresh. A repeated or
noncanonical locally generated nonce fails before any GET.
Every projected `dumbmoney.ledger-event-proof.v1` is also checked
independently: its payload digest must bind the envelope body, all duplicated
identity and provenance fields must agree, its event digest is recomputed, and
observable adjacent global/source chain links must extend the known cursor.

Each kill or desired-mode envelope must then verify under the operator
keyring; each capital envelope must verify under the Core keyring. The
keyrings are required to be disjoint and every key ID must equal the SHA-256
of its raw Ed25519 public key. A valid signature under the wrong role is still
rejected.

The consumer persists `(next_sequence, next_digest)` and the resulting
controls in one fsynced journal event. Its append also compares the expected
starting cursor under the interprocess writer lock, so two runners cannot both
commit from one cursor. A backlog (`has_more=true`),
authentication/transport failure, stale or future signed checkpoint, unknown
schema or signer, cursor mismatch, projection/proof tamper, or dispatch failure
remains fail-closed. One call performs at most one GET and never retries a
write.

Historical signed events still advance the durable cursor. Expired
kill-active and non-LIVE mode events remain authority-reducing and persist.
Expired or future kill-clear, LIVE-mode, and capital grants update only their
monotonic high-water marks and never activate authority. Unsigned
page fields cannot change the checkpoint-signed `required_action`, and even a
valid signed positive action can never clear a local kill latch.
`has_more` requires another explicit `poll_once`; there is no autonomous drain
loop.

## Kalshi write boundary

The central firewall constructs the current event-order V2 wire shape and
uses `POST /portfolio/events/orders`: one YES-denominated `bid`/`ask` book,
fixed-point `count` and `price` strings, explicit time-in-force,
self-trade prevention, subaccount zero, pause cancellation, and `post_only`
for makers. Buying NO maps to an ask at the complementary YES price. The
transport capability gate recognizes both the V2 collection and the legacy
collection so the new route cannot bypass the chokepoint.

A write waits for its private mutation lane before the final Core resolution,
then consumes a single-use permit before exactly one socket attempt.
Timeouts, request errors, HTTP 429, malformed acknowledgements, and immediate
fill/remainder projections are ambiguous outcomes: they are never resent and
retain the deterministic `client_order_id` reservation for reconciliation.
The default production REST origin is
`https://external-api.kalshi.com/trade-api/v2`. Conflicting ambient
host/version overrides are rejected, HTTP clients do not inherit proxy or
netrc settings, and broker JSON is decoded as bounded strict UTF-8 with
duplicate keys and non-finite numbers rejected.

## Kill and cancellation behavior

Queueing kill reconciliation can mirror `authority.cancel_only` into the
operational journal. This always removes submission authority. It does not
create cancellation authority or contact Kalshi. A cancel-reconciliation
command is written to the outbox only when a distinct existing
cancellation-authority receipt is supplied.

## Activation status

The sealed Windows runner, public config schema/template, Credential Manager
targets, signed readiness, Core command/contract transports, and SQLite
journals exist. The production runner now constructs a credential-owned,
read-only Kalshi truth provider without exporting its RSA key or key ID into
the process environment. The provider pins
`https://external-api.kalshi.com/trade-api/v2`, disables ambient proxy and
redirect behavior, signs only the documented balance, positions, and resting
orders GET paths, bounds every response, and performs no retry. Reconciliation
also reads the documented current and historical order/fill tiers plus
settlements so archival movement cannot manufacture an absent order or fill.
Positions, orders, fills, and settlements are fully paginated, constrained to
subaccount `0`, then read twice; any cursor truncation, duplicate identity,
cross-subaccount row, schema drift, aggregate disagreement, or change between
the two projections fails closed. The stable fixed-point projection is
recorded in both the local and Core-capital exposure domains.

Every reservation now includes the submitted notional plus the general
worst-case Kalshi taker fee, including post-only maker intents. A terminal
broker observation is accepted only as a typed, domain-separated witness
signed by the sealed Dummy service identity and tied to the exact reservation,
account, subaccount, order, fills, observation window, and projection digest.
The restart-safe sweeper first idempotently projects fills into venue-local
exposure, then releases the order reservation. Filled exposure remains
reserved independently until a second stable position-absence read and
matching settlement witness have been persisted. These service signatures
attest which local service observed the authenticated broker response; they do
not imply that Kalshi signed the response.

The service still intentionally starts and remains
`RECONCILIATION_ONLY`. Production installs
`SealedDisabledExecutionCycle`, which accepts the exact broker snapshot and
returns its digest but owns no broker client, credential, callback, or submit
method. It always returns `BLOCKED`, `broker_contacted=false`, and
`orders_submitted=0`. This proves the production cycle boundary and snapshot
binding without creating order authority.

Live activation is blocked until all of the following are sealed and tested
end to end:

- a real authenticated target-account validation of the implemented,
  fully-paginated double-read broker and reconciliation projections;
- a separately reviewed, sealed order-capable execution adapter replacing the
  disabled harness while preserving the exact verified broker-snapshot digest;
- witnessed place/reconcile/settle/kill/restart drills against the intended
  account, beginning with an attended mechanical canary.

Do not interpret signed readiness, passing unit tests, or a fresh flat-book
receipt as live authorization or profitability evidence.
