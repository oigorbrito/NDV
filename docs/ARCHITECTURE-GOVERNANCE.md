# NDV Architecture Governance

## Default posture

No NDV architecture component is approved merely because it appears useful conceptually.

The default implementation order is:

`REUSE -> ADAPT -> WRAP -> FORK -> BUILD CUSTOM`

A proposed custom capability must pass both:

1. scientific gate: the capability creates measurable value;
2. engineering gate: existing software does not satisfy the required contract more economically.

## Blocked by default

Until evidence changes their status, do not implement:

- NDV orchestrator
- NDV generic agent framework
- NDV memory system
- NDV generic router
- NDV workflow engine
- NDV model/provider gateway
- NDV sandbox/workspace platform
- NDV architecture-search engine
- learned/adaptive controller

## Candidate minimal NDV-specific artifacts

These may be justified earlier because they encode the research itself rather than duplicate ecosystem infrastructure:

- Evidence Ledger schema
- Execution Ledger schema
- minimal `VerificationResult` contract
- minimal `CapabilityProfile` contract
- minimal decision-policy interface, only if P1/P4 require it

## Capability kill rules

- If `workspace-only ~= structured-state`, reject a custom state/memory layer.
- If an existing context method is equivalent or better, reuse it.
- If `best-fixed ~= oracle`, reject a routing layer.
- If `rules ~= learned/LLM controller`, reject controller sophistication.
- If external orchestration is equivalent at lower total cost, do not build orchestration.
- If prior art satisfies the contract, implementation may be killed before a custom prototype is written.

## Architecture authority

Architecture is an output of evidence, not a prerequisite of the research program. No normative "NDV architecture v1" should be frozen before integrated evidence justifies it.