# Runtime architecture

<!-- sourcebound:policy register-v2 -->
<!-- sourcebound:purpose -->
Use this reference when choosing a Sourcebound runtime or diagnosing an MDX capability boundary. It
names the product runtime, the isolated parser adapter, and the behavior available when Node.js is
not installed.
<!-- sourcebound:end purpose -->

**[Check the installed runtime](INSTALL.md#parse-mdx-repositories)**.

## Documentation flow

Sourcebound keeps three inputs separate: authored intent explains why a surface matters, the repository contract declares which relationship may be checked, and change state limits the work to the relevant diff. Typed evidence flows from static adapters or bounded commands into only the declared binding mechanism.

The resulting operations have distinct authority: `drive` repairs planned regions, `check` and `verdict` reject declared drift without writing, `project` refreshes declared context, and `verify` records local state. None of those operations certifies unbound prose, editorial judgment, or a host-level security property.

## Product runtime

Sourcebound is a Python package and CLI. Python owns the manifest, source extractors, policy checks,
receipts, projections, and release artifact. Install the released wheel with a Python tool installer.

## MDX adapter

MDX has a mature syntax ecosystem in JavaScript. Sourcebound keeps that concern behind one
first-party adapter:

| Part | Owner | Contract |
| --- | --- | --- |
| `tools/mdx-parser/src/parser.mjs` | Authored adapter source | Parses MDX into versioned structural JSON |
| `src/clean_docs/adapters/mdx_parser.mjs` | Generated wheel input | Reproducible bundle of the pinned parser dependency graph |
| `src/clean_docs/mdx.py` | Python boundary | Starts the bundled parser with bounded input, validates its response, and exposes typed nodes |

The adapter runs in a temporary directory with a reduced environment. It parses structure only. It
does not evaluate JSX, imports, components, or repository package scripts. The [security model](SECURITY_MODEL.md#trust-tiers)
defines the process controls and their host boundary.

## Availability contract

| Repository | Node.js | Result |
| --- | --- | --- |
| Markdown only | Absent | All supported documentation checks run normally |
| Contains MDX | Absent | MDX documents are explicitly unsupported with an actionable doctor result |
| Contains MDX | Node.js 20 or newer | The bundled parser provides structural MDX checks |

Node.js is not an npm installation requirement and Sourcebound never downloads it. CI tests the
minimum supported Node.js version and a current version against the same MDX adapter contract.
