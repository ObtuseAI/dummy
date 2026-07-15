# Security policy

Dummy is a private repository in the ObtuseAI GitHub organization. It is
evidence-gated prediction-market intelligence and trading research. Its live
execution paths are fail-closed, evidence-gated, and subject to explicit
operator authorization (see the README safety invariants). Access to this
repository does not grant any use, distribution, or execution authority.

## Reporting a vulnerability

Report suspected vulnerabilities privately to the organization owner at
cjharriskc@gmail.com. Do not open a public issue or pull request, and do not
use any other public channel to describe a suspected or confirmed
vulnerability.

Please include enough detail to reproduce the issue and, where relevant, the
affected component. You will receive an acknowledgement and private
coordination on remediation and disclosure timing.

## Disclosure

This is a private, proprietary repository. Suspected or confirmed
vulnerabilities must not be publicly disclosed. Coordinated remediation is
handled privately by the organization owner; no public advisory is published
for this private repository.

## Safety posture

Consistent with the README, live execution remains fail-closed,
evidence-gated, and operator-authorized. A live canary refuses to start until
its evidence gate is satisfied, live orders pass through a hardened firewall
adapter with transport-witnessed truth, and the kill file stops everything
instantly and unconditionally. These controls are part of the security posture
and must not be weakened to work around a report.
