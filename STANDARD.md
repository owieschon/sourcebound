# Documentation style guide: clean, grounded developer docs

<!-- clean-docs:policy register-v2 -->
<!-- clean-docs:purpose -->
STANDARD.md is the canonical writing and documentation policy packaged with clean-docs. Use it when writing or reviewing repository documentation for people or agents: it prevents correct facts from becoming hard to find, easy to misread, or detached from source, and it defines how to choose the right medium, voice, canonical home, and evidence boundary for each claim.
<!-- clean-docs:end purpose -->

**[Start with the governing principle](#the-one-principle-everything-else-follows)**.

The [pre-publish checklist](#pre-publish-checklist) is the proof surface for an authored review.

<!-- clean-docs:allow audience reason="This standard names agent-workflow signals as policy examples rather than addressing an agent" -->

Derived from a close reading of a developer-documentation corpus spanning overview,
quickstart, workflows, best practices, memory, hooks, integrations, settings, and CLI
reference pages. Every rule below traces to an observed, repeated convention in that corpus.
clean-docs packages this file as its canonical default standard.

## The one principle everything else follows

**Choose the medium by what the reader is doing at that sentence, not by what the content is about.**

| Reader's current verb | Medium |
| --- | --- |
| Orienting, deciding, or asking why | Prose |
| Doing something in code or a shell | Runnable code block |
| Acting in a visual interface | Cropped screenshot or short video |
| Choosing among options or comparing attributes | Table |
| Looking up one fact by key | Registry or generated reference |
| Following a sequence | Numbered steps |
| Comparing state transitions | State table or state model |
| Tracing cross-actor timing, retries, or overlap | Sequence or event model with an accessible text projection |
| Understanding spatial, cyclic, or branching topology | Structured graph; rendered diagram when it helps |
| Avoiding a non-obvious trap | Semantic callout |
| Doing the same task in one of several environments | Deep-linkable tabs |
| Checking whether the task worked | Expected result or verification command |

A page is just this rule applied sentence by sentence. Reference pages look different from
tutorials only because a reference reader looks-up more often than a tutorial reader orients.

### The rule constitution

Rules resolve in this order: **truth and honesty → grounding → reader budget → register → warmth**.
A lower rule never degrades a higher one. A repair must not widen a claim beyond its evidence, drop
a limitation, detach a receipt, or weaken the page's point to make a lower-priority check pass.

Classify the document's job before applying a rule. An overview orients. A tutorial teaches ordered
steps, a task page gets work done, and troubleshooting moves from symptom to recovery. A reference
supports lookup. An architecture record preserves boundaries and time horizons, while an evidence
record preserves observations. An agent procedure constrains actions, and a template is runtime
input.

Prefer path, filename, frontmatter, title, and repository convention as role evidence. When those
signals are ambiguous, declare `<!-- clean-docs:role reference -->` with the narrowest matching role.
The supported roles are `overview`, `component-overview`, `tutorial`, `task`, `troubleshooting`,
`reference`, `architecture`, `plan`, `evidence`, `agent-procedure`, and `template`. A role marker
scopes rules; it never suppresses broken links, source drift, unreadable bytes, or concrete residue.
A rule that helps one role can damage another. Purpose and routing checks help an overview; they
corrupt a two-line prompt template. Fixed page budgets can expose a sprawling guide; they can split
a safety constraint from the step it governs or make a reference harder to scan.

Repositories may adopt the clean-docs register for one document by adding
`<!-- clean-docs:policy register-v2 -->` after its title. The marker selects a policy profile; it
does not decide which rules fit. The document's role still selects rules one by one. The marker
never changes that role, overrides a repository-native form, or turns an uncertain editorial call
into a mechanical failure.

Every rule passes three gates. **Applicability** asks whether the rule helps this document role.
**Evidence strength** separates a demonstrable defect from an editorial inference. **Enforcement
ownership** asks whether the repository accepted that compatible policy rule as a gate.

A provably broken local link, unreadable document, concrete machine-specific residue, or stale
source binding has a mechanical witness, but a witness alone is not authority to gate an untouched
repository. Before setup, integrity defects, role-compatible writing-policy candidates, and
repository-neutral corpus signals cannot become blockers. The default assessment reports integrity
and corpus signals; `audit --preview-policy` adds bounded, role-compatible house-policy candidates.
A manifest accepts repository integrity checks as gates. A policy marker accepts compatible
deterministic policy rules for that document. Neither activates an incompatible rule, makes a guess
true, nor certifies that the chosen motivation matters, the teaching sequence works, or the page
has earned its personality.

When two rules cannot both pass, move the detail one layer deeper before cutting it. Depth is the
standard pressure valve: the overview keeps the choice and route. A guide or lookup page keeps the
caveat, source proof, or schema. Delete only material that no reader layer needs.

Mark an unavoidable loss instead of hiding it:

```markdown
<!-- clean-docs:yield rule="qualifier-density" to="truth-honesty"
     reason="The sentence preserves two independent safety boundaries" -->
```

The reason names the winning rule and the fact that would otherwise be lost. A repeated yield at
the same boundary means the threshold is wrong. Fix the rule instead of teaching the corpus to
ignore it.

Author all applicable rules before rewriting a page. Then make one whole-document repair against
the complete battery and this precedence order. Sequential per-rule repair is forbidden because
the last repair silently wins.

---

## 1. The medium boundary (the decisions to get right)

### Prose: carries the "why" and any logic spanning multiple items
Prose is for cause and effect: anything with a *because* in it. It always comes *before*
code, never after as cleanup. Precedence rules, tradeoffs, and mechanism are prose (or a
numbered list), never a table, because they're an *ordering*, not a *lookup*.

> "An agent stops when the work looks done. Without a check it can run, 'looks done' is the
> only signal available, and you become the verification loop: every mistake waits for you
> to notice it."

Three sentences of pure mechanism before any command is named. That's the job of prose.

### Code: executable evidence, never bare
Code can teach the action directly once the reader knows why they are taking it. Two hard rules:
- **No bare block.** Every code block has a prose lead-in ending in a colon that says what
  it does, and often a follow-up naming what to notice or what breaks.
- **Comments are sparse.** Use one only when the code cannot express a constraint or intent.
  Do not make comments narrate the example line by line.

When placement matters, name the file. Use realistic names and values that expose the shape of the
task. Use tabs for language or platform variants, visual diffs for a progressive edit, focus or
collapse markers for the lines that matter, and a copy action for install commands. A reader must be
able to tell whether a block is runnable, configuration, output, or a prompt before copying it.
Every fenced block declares a language. Use `text` for literal output or prompts rather than leaving
the label empty.

The escalation ladder inside a single block is a signature move. It goes abstract form, then a
real named instance, then the complication:
```bash
# Basic syntax
docs-tool integration add --transport http <name> <url>

# Real example: Connect to Notion
docs-tool integration add --transport http notes https://api.example.com/integration

# Example with Bearer token
docs-tool integration add --transport http secure-api https://api.example.com/integration \
  --header "Authorization: Bearer your-token"
```
Placeholders (`<name>`, `YOUR_TOKEN`, `/path/to/x`) and real recognizable values (Notion,
Stripe) are **never mixed on one line**. The language tag sets the reader's action: `bash` = run in a
shell, `json`/`yaml` = config, `text` = type this *to* the agent (a prompt). Keep that split.

### Table: for comparison or lookup, where order doesn't matter
Tables compare several items across several attributes, index facts by key, define terms in context,
or show before-and-after states. Column design mirrors the questions the reader is asking:
`Scope | Loads in | Shared with team | Stored in`. Cell rule: **left column is a bare token
in code font; right columns are sentences that scale with complexity.** A simple flag gets a
fragment; a hard one gets a paragraph *in the same cell* until it earns its own section. The
"do this / not that" two-column ✅/❌ table is the canonical way to show a rule at scale.

### Callout: an off-ramp, never where a concept is first taught
Callout type is semantic, not decorative:
- **Warning** = this will hurt you (data, security, a silent violation of what you expect).
  Name the wrong assumption explicitly: "…even though 1 is the conventional Unix failure code."
- **Note** = a true-but-easily-missed clarification or a scope boundary.
- **Tip** = optional power-user extra, often a `Tips:` bullet list.

### Architecture: structured text first, diagrams only when topology earns them

For documentation consumed by people and agents, one structured source owns the architecture. It
may be a numbered contract, nested list, state table, or machine-readable graph, state, sequence, or
event model. Record only the dimensions that change interpretation: applicable actors, inputs,
transformations, branches, outputs, unknown states, and authority boundaries. Empty slots are not
completeness.

Render a diagram when spatial shape or timing lets readers see a relationship that another form
would force them to reconstruct: fan-in or fan-out, cycles, retries, overlapping work, nesting, or
a genuinely nonlinear branch. Rendered pixels are never the canonical source. Pair them with an
accessible projection that preserves the applicable relationships on a narrow screen, through a
screen reader, in search, and in a text-only context window. If the image merely puts boxes around
an ordered list, delete it. Alt text identifies the image and its purpose; it does not carry the
only complete explanation.

Every Mermaid diagram has an adjacent text equivalent after the block. Start it with `Diagram:` so
renderers, screen readers, search, and agent projections can identify the canonical description.

### Screenshots and video: teach recognition and interaction
Use a screenshot when the reader must find, distinguish, or verify something visual. Crop unrelated
UI, use a consistent viewport, annotate the target, remove personal or sensitive data, write useful
alt text, and provide light and dark variants when appearance changes. A caption states what to
notice rather than repeating the image.

Every image has useful alternative text unless it is decorative. Mark a decorative Markdown image
with `<!-- clean-docs:decorative-image -->`; native HTML uses `alt="" role="presentation"`.

Video is optional. Use it only when motion is necessary to understand a multi-step interaction or
temporal UI behavior and the team can maintain it. Prefer a controllable video to an animated image.
Provide a complete text path to the same outcome and make code legible at full screen. A person or
agent must be able to complete and verify every documented task without watching it. Do not use media
as decoration or as the only record of a fact.

---

## 2. Voice at the sentence level

- **Second person + imperative for the reader's actions.** "Open your terminal." "Set to
  `true` to disable." Not "one can" or "users should."
- **Name the system as an actor** so behavior reads as fact, not promise: "The tool skips
  that server and reports the error." Behavior is stated, not sold, which is why the docs
  never read as marketing.
- **Every clause adds information.** Split a sentence when its claims need separate evidence or
  differ in scope. Keep tightly coupled cause and effect together.
- **Plain, concrete verbs.** Things fill, skip, block, load, collide. Never "leverage", "utilize", "seamlessly", "powerful", "simply", or "comprehensive". <!-- slop-ok: naming banned booster words as negative examples -->
- **State facts without hedging.** "The tool always asks for permission before modifying
  files" is absolute, not "usually." When advice is *genuinely* situational, mark the
  uncertainty explicitly ("Sometimes you *should* let context accumulate…") rather than blur it.
- **Contractions are fine** ("you'll", "won't", "let's"); the register is a helpful senior
  colleague, not a spec.
- **Use present tense and active voice.** Use future tense only for behavior that has not happened.
  Passive voice is useful only when the actor is unknown or irrelevant.
- **Remove trivializers.** Words such as "easy", "obvious", and "just" dismiss the reader's
  difficulty. State the action and its prerequisites instead. <!-- slop-ok -->
- **Use sentence case for headings, American English, and the Oxford comma.** Spell out zero through
  nine; use numerals from 10 onward and for percentages or technical values.
- **Format interface paths consistently.** Bold control labels and write nested paths as
  **Parent > Child > Control**. Reserve bold for semantic labels, definitions, and UI controls,
  not general emphasis.
- **Link the first meaningful mention.** Use descriptive link text, point to the exact destination,
  and deep-link into the product when the reader's next action happens there. Never use "click here".

### Whimsy: give precision a pulse

Precise does not mean bloodless. Dry wit, a physical metaphor, or a lightly playful example can
make a mechanism easier to remember. That personality is part of the teaching, not frosting spread
across the page.

- **Personality has a budget.** Overview, conceptual, and tutorial pages get at least one
  subject-derived memorable element unless the entire topic sits in a literal zone. Spend at most
  one flourish in a conceptual section. A page does not owe the reader a joke.
- **Earn the whimsy from the mechanism.** A metaphor must preserve how the system works. "The cache
  has not developed opinions; two configuration layers disagree" earns its dry aside by naming the
  real failure immediately. A generic quip teaches nothing.
- **Give examples a small, coherent world.** Prefer plausible names with a little character, such as
  Acorn Bakery or Moonbase Support, over `foo`, `test123`, and a different joke in every block. Keep
  runnable commands and security-sensitive values literal.
- **Keep the searchable noun in playful headings.** "Retries: when the queue refuses to take a
  hint" is findable. "Here we go again" is not.
- **Let visuals carry character only when the motif explains the system.** A tether can represent a
  source binding; a decorative mascot cannot. Preserve high contrast, useful alt text, and the
  adjacent structured contract.

Commands, configuration, error messages, repair steps, security and privacy boundaries,
accessibility text, and API or option reference are literal zones. Do not put wit between a reader
and an exact action, failure, or fact. Never use sarcasm at the reader, stacked puns, meme or
pop-culture references, emoji decoration, or anthropomorphism that invents agency.

Run two judgment checks. The **truth test** asks whether the source or mechanism supports the
metaphor. The **deletion test** removes the flourish and confirms that the technical claim, warning,
and next action remain complete. If either test fails, cut it.

---

## 3. How to explain something technical simply (the actual techniques)

The bar: a competent reader who has never seen this system grasps what it is and does from the
first screen. The first sentence plainly names its category ("X is a Y that does A, B, C").
Ground each new term on first use or cut it, and give each sentence one claim. The
measure is a blind read: hand the doc to a reader with no prior context and check whether they can
state back what the system is. The docs hit that bar with specific, repeatable moves:

### Define the subject, then state the BLUF purpose contract

Definition and purpose are separate reader contracts. An ontological definition names what category
the subject belongs to: "X is a Y." A purpose contract states who should continue, what problem the
page addresses, and what the reader can do afterward. A capability list or value proposition can
answer what a system does while leaving its category ambiguous, so neither substitutes for a
definition.

Every product, system, or concept overview opens with a plain category definition before explaining
value or mechanism. Name the narrowest category the sources support, then add the distinguishing
boundary a reader needs. "QueueKit is a Python task queue that stores jobs in PostgreSQL" defines a
category and boundary. "QueueKit processes jobs quickly" states behavior but never says what it is.
Procedural pages whose subject is already established link to its canonical definition and open with
the purpose contract instead of repeating it.

Every standalone overview, concept, tutorial, and task page opens with the documentation equivalent
of a function contract. State the bottom line before the explanation so the wrong reader can leave
and the right reader knows what the page will change for them. A reference opens with scope and
authority. An architecture record, plan, or evidence record opens with status and time horizon. An
agent procedure opens with typed identity and execution constraints. A template adds no reader
preamble because its bytes are product input.

| Contract slot | The opener answers |
| --- | --- |
| Precondition | Who this is for and when it applies |
| Job | What problem leaves the reader stuck without this page |
| Postcondition | What the reader can do after reading |

Keep the contract falsifiable and true to the code. A title restatement adds no contract. A feature
list describes the implementation instead of the reader's problem. Booster prose cannot be checked.
A scope claim the page or product does not deliver is documentation drift.

For applicable, registered reader pages, the deterministic floor checks that one purpose block
exists, appears before body content, and does not restate the H1. A reviewer checks whether an
overview names a true category and whether the purpose contract names who should read, what problem
they face, and what they can do afterward without overselling the tool. Category truth cannot be
inferred from sentence shape: "X is a platform" passes a regex and can still be false. A mechanical
pass never substitutes for that truth check.

### Use repeatable explanation techniques

1. **Open with a definition, then the one constraint that explains everything downstream.**
   Best-practices names it once ("The context window fills up fast, and performance
   degrades as it fills") and refers back to it for the rest of the page. Find your page's
   single governing constraint and name it early.
2. **Restate the mechanism as a plain cause-and-effect chain with the reader as the actor,
   *then* show code.** "When an event fires and a matcher matches, the tool passes JSON to
   your hook handler… Your handler can then inspect the input, take action, and return a decision."
3. **Hand over a testable heuristic instead of an abstract rule.** "For each line, ask: 'Would
   removing this cause the agent to make mistakes?' If not, cut it." A question the reader can run
   beats a principle they have to interpret.
4. **Teach terms in use, not in a glossary.** New terms ("matcher", "scope") first appear
   inside a working sentence that makes their meaning obvious from context.
5. **Ground the abstract in a physical metaphor.** "Before they touch disk", "so the edits
   don't collide", "keep your context clean."
6. **Lead a conceptual section with a one-line takeaway, then earn it** in the prose that follows.

---

## 4. "Don't do this" and gotchas

- **Every "don't" ships with its "instead."** "'Use 2-space indentation' instead of 'Format
  code properly.'" Never state a prohibition alone.
- **A warning states the failure's *mechanism*, not just its existence.** The reader is
  trusted to generalize. "JSON output is only processed on exit 0. If you exit 2, any JSON is
  ignored."
- **Tier by severity:** reasoned platform gotchas stay inline mid-paragraph; the non-obvious
  thing that silently bites goes in a `Warning`; recurring behavioral mistakes get *named* and
  collected ("The kitchen sink session", "The over-specified agent instructions") with a `Fix:` under each.

---

## 5. Page shape by genre


**Overview** (decide): plain definition and value → supported environments and essential capabilities
→ visual model where useful → routes to setup, concepts, and common jobs. It answers what this is,
whether it fits the reader's stack, and where to start.

**Getting started** (first outcome): prerequisites shared before any platform branches → minimal
installation → one useful result → explicit verification → next task. Exclude advanced configuration.

**Start here** (adoption syllabus): visible milestones → required, recommended, and optional work →
the goal of each milestone → links to the focused procedure → next useful outcome. Progress markers
reduce abandonment; they are not decoration.

**Tutorial** (linear learning): payoff and prerequisites → imperative step spine → each step combines
only the media needed to act → observable result → next experiment or related guide. State a time cost
only when it is grounded.

**Conceptual** (mental model): definition → the constraint or problem it explains → relationships,
data flow, or terms → consequences for the reader. Use diagrams for shape and tables for definitions.
Do not force an instruction into a concept page.

**Guide** (one job): outcome-shaped title → brief applicability and prerequisites → practical steps →
verification → next related job. Name the job the reader is doing, not the feature they happen to use.

**Troubleshooting** (recover): searchable symptom → likely cause → diagnostic → repair → expected
result → escalation. When several causes are possible, expose the decision path. Put setup off-ramps
first and escalation last.

**Reference** (lookup): one-line descriptor → minimal context for precedence or scope → generated or
structured entries → examples where they resolve ambiguity. Order by the reader's journey unless it
is a pure alphabetic registry. Generate signatures, parameters, schemas, and defaults from the source
that defines them; hand-write only the context needed to use them correctly.

**Safety, privacy, or cost controls** (choose a boundary): state what is protected, where the control
executes, and what remains outside it → order options from least to most restrictive → name defaults,
inheritance, and overrides → show how to verify the boundary.

**Universal:** teach through **orient → act → observe → verify → extend**, omitting verbs the genre
does not need. Order sections by the reader's journey, not the alphabet except in a pure registry.
Link outward rather than expanding a second job inline. Keep version notes beside the claim they
modify; never add a changelog section to current reference.

---

## 6. Beyond the single doc: does it earn its existence?

The rules above make one doc good. These decide whether a doc should exist, how long it may
be, and whether its content already lives elsewhere. This is the level most prose fails at: a
corpus of individually-clean docs still sprawls. Each rule below is a check a reviewer can run.

- **A record must earn its surface, but its filename does not decide.** Ephemeral worktree state,
  branch ownership, or task accounting belongs in git history, a PR, or an issue. A package-owned
  review or incident record may be durable evidence. The same holds for a longitudinal study or
  live plan. Preserve the record until its owner and time horizon prove it is exhaust. A scanner may
  flag the ambiguity; it must not move or delete the file.
- **Match the document to its real reader.** A published guide addresses a person doing its task.
  An agent skill or prompt legitimately addresses an agent and may use imperative execution
  constraints, typed frontmatter, and deliberate repetition. Do not rewrite an executable agent
  procedure into a generic human guide. Do not disguise a branch handoff as durable agent
  documentation.
- **One canonical home per fact.** A fact shared by a family of docs lives in exactly one doc;
  siblings cite it and state only their own deviations. (Same invariant as the second brain:
  link, never copy.) N sibling pages each re-deriving one shared spec is the tell.
- **Reference states current truth; provenance goes in a changelog.** Verification receipts,
  deltas from a prior baseline, and `(Program N)` / `(Wave N)` tags do not belong inside a
  reference doc. Test: if a passage would be equally true with its history deleted, delete the
  history.
- **No sentence restates a prior one without a local reason.** This is the highest-yield concision
  check for explanatory prose. Repeat a safety boundary at each irreversible action when distance
  would make the procedure easier to misuse; preserve the constraint, not merely the wording.
- **Each section leads with its takeaway in one sentence, then supports it or is cut.** A
  section whose takeaway is "see the table" means the prose should *be* the table.
- **Length prompts a depth review.** README pages over 90 lines and guides over 150 lines receive an
  advisory. A section over 40 lines receives the same review. A line count cannot prove that a
  second job exists. Move one behind a link when it does; keep a complete safety sequence,
  diagnostic chain, or lookup surface together when splitting would make the page harder to use.
  A length allowance is a subtraction receipt naming what moved, split, or was cut; breadth alone
  and "keeps everything together" are not reasons.
- **Prefer the denser medium.** An inline 3-to-7-item enumeration (vendor classes, data
  sources, tested dimensions) is a table or list, not a sentence.

### Put the point, action, and proof on the first screen

The first 15 lines of a reader-facing page contain three things: the marked purpose prose, the
primary action, and one proof. The action is a runnable command or a bold route to the next task.
The proof is a receipt or result link, a badge, or a verification command. A reader who stops there
can answer what this is, what to do first, and how to know it worked.

The README is a hub, not a warehouse. It owns the point, first action, proof, and a routing table.
Reference facts, schemas, and configuration examples longer than 12 lines live on reference pages.
An explanatory section over 80 words links to the deeper page that owns its detail. Link to the
canonical home instead of making the overview carry both the decision and its appendix.

Use this routing-table shape:

| If you need to... | Start with | You will leave with... |
| --- | --- | --- |
| Reach a first verified result | A focused tutorial | A working baseline and its proof |
| Look up exact behavior | The reference | The current command, schema, or boundary |

### Keep the register concrete

The deterministic register floor catches five repeatable failures:

<!-- clean-docs:yield rule="nominalization-density" to="truth-honesty"
     reason="The rule definition must name nominalization and its abstraction suffixes" -->
1. **Nominalization density.** A reader-facing sentence with three or more abstraction-suffix
   tokens (`-tion`, `-sion`, `-ment`, `-ance`, `-ence`, `-ivity`) fails after the narrow allowlist
   for `documentation`, `application`, `section`, and `configuration`.
<!-- clean-docs:yield rule="nominalization-density" to="truth-honesty"
     reason="The rule definition must preserve its exact sentence-variance terms" -->
2. **Sentence variance.** A paragraph of at least three sentences fails when every sentence is
   15-35 words. Give the reader one short beat.
<!-- clean-docs:yield rule="nominalization-density" to="truth-honesty"
     reason="The rule definition must preserve its exact assurance and execution terms" -->
3. **Assurance deduplication.** Each authority or execution boundary has one canonical home.
   Overview pages link to it instead of repeating it.
<!-- clean-docs:yield rule="significance-narration" to="truth-honesty"
     reason="The rule definition must quote each phrase that it rejects" -->
4. **Significance narration.** Cut "exactly the", "the very", "this demonstrates",
   "deliberately", "is itself", and "which is precisely" when the page praises its own system.
   State the consequence instead.
5. **Qualifier density.** Overview and learning prose gets at most two `may`, `only`, `unless`,
   or `except` guards in one sentence. Limits and security sections are exempt because guarding is
   their job.

These diagnostics do not license flat prose. The constitution decides which rule wins. Each rule
ships with a collision fixture that pins that choice.

### Give the corpus a navigation contract

Readers should be able to predict where a fact lives. Use a stable taxonomy such as overview,
getting started, concepts, guides, troubleshooting, and reference. A product area does not need every
category, but a label must keep the same reader intent everywhere it appears. Navigation names the
reader's destination, not the repository's internal architecture.

Treat each path as a contract:

| Path | Reader question |
| --- | --- |
| Overview | What is this, does it fit, and where do I begin? |
| Getting started | What is the shortest verified path to a useful result? |
| Concepts | Why does the system behave this way? |
| Guides | How do I complete this job? |
| Troubleshooting | How do I recover from this symptom? |
| Reference | What is the exact current value, shape, or behavior? |

### One source, purpose-built projections


The documentation corpus is a maintained teaching system, not a pile of readable files. Encode
meaning once, then project it for the audience's task. A human surface may use progressive
disclosure, diagrams, and narrative. An agent surface may use stable identifiers, typed metadata,
compact context bundles, and explicit relationships. Neither projection may invent a second source
of truth. When both audiences need an architecture, its canonical source may be structured prose or
a machine-readable model; a rendered image is one projection of it.

Canonical content should carry the fields each projection needs: what it is, where it applies, who
controls it, which release it describes, what must exist first, what it changes, how to check it,
and where related concepts, tasks, choices, and definitions live. Keep those fields only
when they change behavior; metadata without a consumer is another form of documentation theater.

Teach every consequential surface at three levels:

1. **Model:** name the entities, ownership, lifecycle, state transitions, trust boundaries, and
   invariants that let a reader reason beyond the example.
2. **Procedure:** state prerequisites, ordered actions, observable intermediate states, success,
   failure handling, cleanup, rollback, and retry behavior.
3. **Judgment:** state when to choose the path, when not to, what evidence changes the choice, and
   when the documentation is insufficient and the reader must abstain or escalate.

Structure is semantic. Label content as concept, tutorial, task, lookup, troubleshooting, design
choice, upgrade, policy, or ADR when tooling relies on that label. A high-consequence task
also states permissions, reversibility, side effects, blast radius, approval, and rollback. Agents
must not infer authorization from capability.

Design retrieval units to survive extraction. Each unit names its system, version or applicability,
subject, normative status, and authority without dangling pronouns. Stable anchors let a person,
agent, test, or support record cite the exact governing rule. Controlled terminology preserves
entity boundaries; preferred terms and deprecated synonyms are part of the contract.

Examples are executable lessons. Reuse tested assets, pin their environment, show expected output,
and include the failure or counterexample that defines the negative boundary. Documentation tests
therefore ask readers to choose the right path, supply parameters, meet preconditions, recover,
stop when needed, and cite the governing rule. Schema, spelling, and link checks cannot prove that
the material teaches correct behavior.

Authority and uncertainty stay visible. Distinguish requirements, guidance, examples, history,
experiments, generated reference, and deprecated behavior. State non-guarantees and conflicts, and
give an escalation path for missing policy. A correct answer from the wrong version or a tutorial
treated as normative is still a documentation failure.

### Keep facts next to the behavior that owns them

Place a fact's canonical source as close as practical to the code, schema, configuration, or product
surface that defines it. Render other surfaces from that source. A web guide, in-product onboarding,
command help, and an agent projection may differ in presentation, but they must not independently
restate shared facts.

Generated reference and hand-written explanation are complements. Generate signatures, options,
defaults, and schemas. Hand-write motivation, mental models, examples, failure modes, and the links
between tasks. When generation cannot prove a prose claim, label that boundary instead of implying
that inventory coverage validates the prose.

### Enforce rules at the narrowest honest layer

Layer checks by scope and severity. Corpus rules inspect ownership and duplication. Page rules inspect
structure and links. Sentence rules inspect terms, voice, and mechanics. Errors block demonstrably
wrong or unsafe output; warnings flag likely defects; suggestions expose judgment calls.

Every deterministic rule needs a positive fixture, a negative fixture, and a documented repair.
Classify exceptions by kind, such as proper names, case-sensitive technology terms, or accepted
jargon. Do not hide unrelated failures behind a blanket suppression. Use a model or human to judge
truth, usefulness, and pedagogy, not to rediscover punctuation that a linter can identify exactly.

### Assign ownership and learn from failed tasks

The owner closest to a fact writes or approves its current truth. The documentation-system owner
maintains structure, tooling, navigation, and the reading experience. Every published area names an
owner so stale pages have a destination.

Prioritize changes from observed reader failures: repeated support questions, failed setup attempts,
unhelpful-page feedback, missing search results, and tasks an agent cannot complete from published
material. Record the evidence outside the reader-facing page. Repair the canonical source, regenerate
its projections, and rerun the failed task.

### What only judgment can check (the honest seam)

`clean-docs audit` sees document roles, names, structure, lengths, links, token overlap, registered
prose tells, and exact accepted debt. Its role classifier is evidence for applicability, not proof
of editorial intent. Patterns cannot decide several corpus and teaching rules. A reviewer or an
advisory judge owns them. Each rule is stated so a human can run it today; none is faked into a
brittle regex, because a pattern pretending to judge purpose or pedagogy misfires in both
directions.

- **An executed or superseded plan is process exhaust; a live plan is a reference.** The
  filename does not separate them: `EVAL_PLAN.md` is an active landing page, while a
  `RESEED_PLAN.md` whose first line reads "EXECUTED by Program 9" is history. Read the status
  line, not the name. Instead of a filename rule, an LLM-judge reads the opening lines and asks
  whether the plan's work is finished.
- **A doc about agent operation is not a doc written for a future agent.** An agent profile
  legitimately says "worktree" and "DoD table" because that is its subject; the
  vocabulary-density check flags it anyway. Instead of raising the threshold, judge the second
  person: is the reader a human learning the system, or the next executor picking up a branch.
- **Each section leads with its takeaway.** A section whose first sentence is "see the table"
  buries its point, and no token pattern detects a missing lead. Instead of a mechanical check,
  an LLM-judge scoring the first sentence of each section is where this one slots in.

**A rule enforced mechanically is a floor, not a finish.** This document's own no-em-dash rule,
applied by find-replace, once turned every em dash into a double hyphen: rule-compliant, and a
typewriter-ism in the one file that cannot afford one. The repair rephrased each line by hand,
choosing a colon, a period, or a new structure according to the line's job. Only a reviewer can
choose. That is the same seam as the sentence gate and the three rules above:
a checker enforces the letter of a rule, but whether the result reads well is the judgment it
cannot make. Read every mechanical pass as the floor you start from, never the standard you ship.

---

## 7. Grounding: the doc must be true to the code (and stay true)

A doc can be perfectly voiced, well structured, and accessible and still be wrong, because the
code moved and the prose did not. The other tiers check how a doc reads; grounding checks whether
it matches the system. It is the truth tier.

- **Derive the factual spine from source; do not paraphrase it.** Capability lists, CLI flags,
  config options, routes, counts, and version facts each have a source of truth in the code (a
  registry, a signature, a test). Render them from that source. A human paraphrasing an old draft
  is how a doc goes stale.
- **A factual defect is fixed at the code, not in a better sentence.** When a doc misstates what
  the system does, re-derive the claim from the code. Editing the prose is the wrong altitude.
- **Verify a claim against its source, never against a commit message or narrative.** "24 of 24
  tests pass" is checked by running the tests. A changelog entry comes from the code delta, not
  from what a commit said it did.
- **Bind a factual claim to its source so drift is detectable:** a generated region re-renders and
  diffs, an accepted source-claim check compares bounded prose with static evidence, and a cited
  symbol is checked to still exist. A command pin checks configured output, not anchored prose.
- **State the honest boundary.** Grounding makes the derivable spine drift-proof. It does not make
  the judgment prose (the why, the framing, the positioning) drift-proof; that stays a human or
  advisory-review concern, never a silent gate. Claim "the documented spine cannot silently
  drift," never "the doc can never be stale."

This tier is the newest, added after a real doc described a nine-action system as one that "drafts
customer emails." No amount of voice or structure work catches that; only grounding does.

---

## 8. Pre-publish checklist


Run this against any doc before shipping. Each line is a fail/pass check.

- [ ] In an overview, the first 15 lines contain the purpose, a primary action, and one proof;
      other roles open with the information their reader needs first.
- [ ] Review a README over 90 lines, a guide over 150 lines, or a section over 40 lines for a second
      job. Split by reader job, but keep one complete safety, diagnostic, or lookup sequence intact.
- [ ] The README routes decisions, first tasks, concepts, and lookup work through an
      `If you need to... | Start with | You will leave with...` table.
- [ ] Each explanatory section over 80 words links to the deeper page that owns its detail.
- [ ] No reader-facing sentence crosses the nominalization, significance-narration, or scoped
      qualifier-density thresholds.
- [ ] Paragraph rhythm includes a short sentence when three or more sentences would otherwise all
      land between 15 and 35 words.
- [ ] Authority and execution assurances have one canonical home; overview pages link there.
- [ ] A rule collision resolves by truth, grounding, budget, register, then warmth; any unavoidable
      loss has an explicit yield naming the winning rule.
- [ ] Every code block has a prose lead-in ending in `:` and (where useful) a follow-up.
- [ ] Every fenced code block declares its language; literal output and prompts use `text`.
- [ ] No table encodes precedence or an ordering rule; those are prose or numbered lists.
- [ ] Every comparison table's columns are the reader's actual questions; ordered logic stays
      in prose or numbered steps.
- [ ] Every "don't" is paired with an "instead"; every warning states a *mechanism*.
- [ ] Callouts are semantic (Warning = harm, Note = easily-missed, Tip = optional) and none
      carries a concept's first explanation.
- [ ] Placeholders and real values are never mixed on one line; language tags are correct
      (`bash` vs `text` vs `json`).
- [ ] Code examples are realistic and sparse in comments; filenames, diffs, focus, or tabs expose
      placement and variants when needed.
- [ ] Screenshots are cropped, scrubbed, annotated, captioned, and described; optional video has a
      complete text path. Architecture has one structured source, records only applicable
      dimensions, and remains usable without rendered pixels; a diagram appears only when topology
      or temporal interaction adds information.
- [ ] Every Mermaid diagram has an adjacent text equivalent beginning with `Diagram:`.
- [ ] Every image has useful alternative text or an explicit decorative-image marker.
- [ ] The page names its one governing constraint early.
- [ ] No booster adjectives (`seamless`, `powerful`, `simply`, `comprehensive`, `leverage`, `utilize`). <!-- slop-ok: banned-word registry for the checklist -->
- [ ] Every clause adds information; claims needing separate evidence are split; the system is named
      as an actor; reader actions are imperative.
- [ ] Every overview, conceptual, or tutorial page has at least one subject-derived memorable element
      unless its topic is wholly literal; each flourish passes the truth and deletion tests.
- [ ] Commands, configuration, errors, repair steps, security and privacy boundaries, accessibility
      text, and reference facts stay literal; whimsy never carries a required fact or action.
- [ ] Headings use sentence case; UI controls use semantic bold; link text names its destination.
- [ ] Sections end by linking outward; version notes are inline at the claim.
- [ ] The document's role is explicit in its structure, and every applied rule helps that role.
- [ ] Ephemeral task state lives in git, PRs, or issues; durable evidence records and live plans
      retain their declared owner, time horizon, and evidence boundary.
- [ ] The audience matches the role: human task pages address people; executable agent procedures
      preserve their runtime contract instead of imitating human prose.
- [ ] No fact is restated across sibling docs; shared facts have one canonical home, cited.
- [ ] The page fits the corpus navigation contract and its genre follows the reader's intended path.
- [ ] Procedures include an observable result and verification; troubleshooting proceeds from
      symptom through diagnosis and repair before escalation.
- [ ] Generated reference comes from the defining source; hand-written prose supplies context rather
      than copying signatures, schemas, defaults, or option lists.
- [ ] Every deterministic rule has positive and negative fixtures, a repair, a severity, and a scoped
      exception model.
- [ ] No reference doc carries provenance, receipts, or baseline deltas; those go in a changelog.
- [ ] No sentence restates a prior sentence without a local safety or execution reason; each
      explanatory section leads with its takeaway.
- [ ] Each standalone reader page names its job near the opening. Overview, tutorial, and task pages
      over their budgets split only when the split preserves safety and lookup; references,
      architecture records, evidence, agent procedures, and templates do not inherit those budgets.
- [ ] Every factual claim (capabilities, flags, counts, routes) traces to a source in the code,
      not to memory or an old draft.
- [ ] For every product, system, or concept overview, the first screen defines what category the
      subject belongs to with an ontological definition, not merely what it does; a reader with no
      context could state it back.
- [ ] Every overview, concept, tutorial, and task page opens with the applicable part of a BLUF
      purpose contract: reader situation, consequential problem, and resulting capability are
      explicit, falsifiable, and true to the code. References, evidence, agent procedures, and
      templates use their role-specific opening instead of filler.
- [ ] Purpose prose names the project-specific subject, operator, consequential failure, and
      authority boundary; it does not use a stock sentence shared across unrelated projects.
- [ ] Canonical meaning has purpose-built human and agent projections rather than separately
      maintained copies; each projection identifies its authority and applicability.
- [ ] Consequential tasks teach the model, procedure, and judgment boundary. They state permissions
      and side effects, show how to verify and recover, and tell the reader when to stop or ask.
- [ ] Executable examples and audience-task evaluations prove correct action and at least one
      negative boundary; retrieval units remain intelligible outside their original page.
