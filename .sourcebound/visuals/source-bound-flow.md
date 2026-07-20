# Visual: source-bound-flow

- Schema: `sourcebound.visual.v1`
- Kind: `diagram`
- Canonical record: `docs/visuals/source-bound-flow.yml`
- Record sha256: `7aac3b9ae0f17df1536361fd9e25d2940eaf79c42e860c4975def003eca9cb1e`
- Source image: [docs/assets/sourcebound-social.svg](../../docs/assets/sourcebound-social.svg)
- Intrinsic size: 1280 × 640
- Alternative text: Three connected cards show repository sources, source bindings, and a deterministic check.
- Caption: sourcebound keeps source facts, prose bindings, and verification connected.

## Complete text equivalent

The flow starts with repository sources, where code and structured files own facts.
Source bindings connect those facts to specific documentation regions, command output,
or symbols. A deterministic check then detects drift before merge and can repair,
reject, or project the declared documentation surface.

## Annotations

1. **Repository sources** (`x=17%`, `y=66%`)
   Code and structured repository files own the facts that documentation may claim.
2. **Source bindings** (`x=49%`, `y=66%`)
   A declared relationship connects a source fact to its documentation owner.
3. **Deterministic check** (`x=80%`, `y=66%`)
   Verification detects drift before merge and can repair, reject, or project declared outputs.
