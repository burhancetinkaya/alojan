# ADR 0009: Configurable server capacity and fifty concurrent calls

Date: 2026-10-24.
Status: Capacity target accepted by the owner's explicit request; detailed topology
proposed for implementation planning. No deployment or capacity acceptance claimed.
Supersedes the unimplemented two-call proposal.

## Context and owner decision

The owner requires an architecture supporting 50 simultaneous AI calls, with
server-specific configurable admission and busy rejection above available capacity.
The existing Linux RTX 4080 host must support a `max_calls = 5` configuration profile.
This amends DEC-02 and requirements §1–2: one owner/number remains, but a fixed
single-call product ceiling and two-call-only test scope no longer define the target.
Actual current runtime capacity remains unchanged until implementation and testing.

## Proposed architecture

Follow the [capacity plan](../CALL_CAPACITY_PLAN.md): Kamailio SIP ingress,
RTPengine media anchoring and horizontally replicated complete call servers with
local ASR/TTS/agent services. Preserve C++ conversation control and existing models.
Use static node quotas totaling at most 50 plus atomic local admission. Calls stay
on one node; ring/setup reservations count. A single five-slot host rejects the
sixth call; a qualified 50-slot deployment rejects the 51st. Zero means drain.
A full node can be bypassed for another with capacity before establishment.

Keep the existing host as the primary development environment under ADR 0003.
New deployment servers are self-hosted capacity additions, not hosted voice-agent
orchestration. Retain DEC-03/04/07–15 boundaries. Document actual carrier-facing
network changes under DEC-05 before deployment; SIP/RTP never uses Cloudflare.
The five/50 limits are targets requiring full GPU/API/carrier evidence, not hardware
performance facts. No automatic model substitution or hidden target relaxation.

## Alternatives and consequences

Raising the gateway limit alone fails because ASR/TTS globally admit one stream
and the agent allows two active turns. A model instance per caller wastes resources;
prefer bounded concurrent contexts and the existing EMA scheduler. A shared remote
GPU pool, distributed quota service and Kubernetes add complexity unnecessary for
the initial statically partitioned deployment. Reconsider only with measured need.

Static allocation may leave capacity unused after node failure. Reassign only after
fencing/draining; this intentionally favors a provable upper bound. Active-call
migration and transparent failover are not promised. Ingress/media/DB recovery needs
separate hardening. Exact hardware count follows measured node capacity.

Keep single-call defaults compatible, validate all new config, and add compatible
protobuf lifecycle changes only if needed. Record infrastructure source pins,
licenses, NAT/port rules and operational costs before installation. This user turn
authorizes the design revision; implementation, infrastructure provisioning and
live activation are not performed as part of this planning task.
