# Security policy

Dummy is a public-source, evidence-gated prediction-market intelligence and
trading-research system. Its live execution paths are fail-closed,
evidence-gated, and subject to explicit operator authorization (see the README
safety invariants). Public visibility does not grant use, distribution,
credential, broker, capital, or execution authority.

## Supported versions

Security fixes are applied to the current `1.0.x` release line. Historical
snapshots are retained for auditability and are not separately supported.

## Reporting a vulnerability

Report suspected vulnerabilities privately to the organization owner at
cjharriskc@gmail.com. Do not open a public issue or pull request, and do not
use any other public channel to describe a suspected or confirmed
vulnerability.

Please include enough detail to reproduce the issue and, where relevant, the
affected component. You will receive an acknowledgement and private
coordination on remediation and disclosure timing.

## Disclosure

Do not publish a suspected or confirmed vulnerability before coordinated
review. Remediation and disclosure timing are handled privately with the
organization owner; a public GitHub advisory may follow after a fix is
available.

## Safety posture

Consistent with the README, live execution remains fail-closed,
evidence-gated, and operator-authorized. A live canary refuses to start until
its evidence gate is satisfied, live orders pass through a hardened firewall
adapter with transport-witnessed truth, and the kill file stops everything
instantly and unconditionally. These controls are part of the security posture
and must not be weakened to work around a report.
