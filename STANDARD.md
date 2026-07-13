# Documentation style guide: clean, grounded developer docs

This is the single reference for documentation voice across every project. It stays one file
over the 120-line threshold on purpose: its four tiers (sentence voice, single-doc medium
boundary, corpus, and grounding) are read as one system, and splitting them would break the
one-canonical-home rule this doc itself teaches.

Derived from a close reading of a developer-documentation corpus spanning overview,
quickstart, workflows, best practices, memory, hooks, integrations, settings, and CLI
reference pages. Every rule below traces to an observed, repeated convention in that corpus.
clean-docs packages this file as its canonical default standard.

## The one principle everything else follows

**Choose the medium by what the reader is doing at that sentence, not by what the content is about.**

| Reader's current verb           | Medium                 |
| ------------------------------- | ---------------------- |
| Orienting / deciding / "why"    | Prose                  |
| Doing (type or paste this)      | Code block             |
| Choosing among options          | Table                  |
| Looking up one fact by key      | Table (registry)       |
| Following an ordered sequence   | Numbered steps         |
| About to hit a non-obvious trap | Callout (Warning/Note) |
| Doing one task per environment  | Tabs                   |

A page is just this rule applied sentence by sentence. Reference pages look different from
tutorials only because a reference reader looks-up more often than a tutorial reader orients.

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

### Code: confirmatory, never bare
Code proves what the prose just framed. Two hard rules:
- **No bare block.** Every code block has a prose lead-in ending in a colon that says what
  it does, and often a follow-up naming what to notice or what breaks.
- **Comments inside the block do the labeling** the surrounding prose would otherwise repeat,
  and state *intent*, not mechanics (`# Block SQL write operations`, not `# run grep`).

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

### Table: for choosing-among or looking-up, where order doesn't matter
Three jobs only: (a) parallel options the reader picks from, (b) a registry indexed by key,
(c) before/after pairs. Column design mirrors the questions the reader is asking:
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

### Diagram: temporal flow and decision branching only
Reserved for lifecycles and decision trees, and always *after* prose has described the flow.
The diagram confirms a sequence already stated in words; it never carries the first explanation.

### Screenshots: used almost never
The source documentation corpus contains essentially zero screenshots. A text interface is
taught with text: "You'll see the prompt with the version, current model, and working directory
shown above it." Reach for an image only when the thing is inherently visual (a
rendered UI layout, a graph) and prose would be longer and worse. Default to describing.

---

## 2. Voice at the sentence level

- **Second person + imperative for the reader's actions.** "Open your terminal." "Set to
  `true` to disable." Not "one can" or "users should."
- **Name the system as an actor** so behavior reads as fact, not promise: "The tool skips
  that server and reports the error." Behavior is stated, not sold, which is why the docs
  never read as marketing.
- **One claim per sentence.** Couple two tightly-related facts with a semicolon; otherwise
  use a period. "Undefined = no restrictions, empty array = lockdown. Denylist takes precedence."
- **Plain, concrete verbs.** Things fill, skip, block, load, collide. Never "leverage", "utilize", "seamlessly", "powerful", "simply", or "comprehensive". <!-- slop-ok: naming banned booster words as negative examples -->
- **State facts without hedging.** "The tool always asks for permission before modifying
  files" is absolute, not "usually." When advice is *genuinely* situational, mark the
  uncertainty explicitly ("Sometimes you *should* let context accumulate…") rather than blur it.
- **Contractions are fine** ("you'll", "won't", "let's"); the register is a helpful senior
  colleague, not a spec.

---

## 3. How to explain something technical simply (the actual techniques)

The bar: a competent reader who has never seen this system grasps what it is and does from the
first screen. Concretely, the first sentence is a plain definition ("X is a Y that does A, B, C"),
every abstraction is grounded on first use or cut, and each sentence carries one claim. The
measure is a blind read: hand the doc to a reader with no prior context and check whether they can
state back what the system is. The docs hit that bar with specific, repeatable moves:

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

**Tutorial** (linear): blockquote tagline stating the payoff and time cost → `## Step N: <imperative verb>`
spine → each step is prose lead-in + code + optional Tip → close with an "Essential commands"
table and outbound links.

**Conceptual** (teaches an idea): definition → the one constraint / problem it solves → a
"This page covers:" bullet map → H2 sections that are imperative verb phrases, each running
**orient (prose) → instruct (code) → warn (callout)**.

**Reference** (lookup): one-line descriptor → minimal conceptual preamble *only* where the
reader must reason across items (precedence, scope) → the lookup table(s), ordered by the
reader's journey (what you do, then how you modify it), with an Example column on every row.

**Universal:** order sections by the reader's journey, not the alphabet (except a pure
registry, indexed by key). End every section by linking outward rather than expanding inline;
keep each page to what only that page can say. Inline version/currency notes at the claim they
modify; never add a "changelog" section.

---

## 6. Beyond the single doc: does it earn its existence?

The rules above make one doc good. These decide whether a doc should exist, how long it may
be, and whether its content already lives elsewhere. This is the level most prose fails at: a
corpus of individually-clean docs still sprawls. Each rule below is a check a reviewer can run.

- **Published surface ≠ process log.** A per-run report, handoff, dispatch ledger, status
  update, or blocked-note is build exhaust; it belongs in git history, a PR, or an issue,
  never as a committed reader-facing doc. Enforce it by location (gitignore / an `archive/`
  outside the doc tree), not by willpower. Test: if a doc's second person is "the next
  executor" and its body is worktree state, branch ownership, or task accounting, it fails.
- **Every published doc's audience is a reader, not a future agent.** If it reads as
  agent-to-agent pickup, it is not documentation; cut it from the surface.
- **One canonical home per fact.** A fact shared by a family of docs lives in exactly one doc;
  siblings cite it and state only their own deviations. (Same invariant as the second brain:
  link, never copy.) N sibling pages each re-deriving one shared spec is the tell.
- **Reference states current truth; provenance goes in a changelog.** Verification receipts,
  deltas from a prior baseline, and `(Program N)` / `(Wave N)` tags do not belong inside a
  reference doc. Test: if a passage would be equally true with its history deleted, delete the
  history.
- **No sentence restates a prior one in different words.** This is the highest-yield concision
  check. The per-sentence "does this add information" test is blind to redundancy at paragraph
  scale; this one catches it.
- **Each section leads with its takeaway in one sentence, then supports it or is cut.** A
  section whose takeaway is "see the table" means the prose should *be* the table.
- **Length forces a justification.** A section over ~40 lines splits or states in its first
  line why it stays whole; a doc over ~120 lines justifies being one file. Name the doc's one
  job in its first line; content serving a second job links out. This is the only check that
  bites a 300-line dossier of individually-tight sentences.
- **Prefer the denser medium.** An inline 3-to-7-item enumeration (vendor classes, data
  sources, tested dimensions) is a table or list, not a sentence.

### What only judgment can check (the honest seam)

The deterministic linter (`doc-hygiene.py`) sees names, lengths, token overlap, and
vocabulary. Three corpus rules resist mechanization, so a reviewer or an eventual LLM-judge
pass owns them. Each is stated so a human can run it today; none is faked into a brittle
regex, because a judge-by-pattern check for a judgment call misfires in both directions.

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
typewriter-ism in the one file that cannot afford one. The repair was to rephrase each sentence
by hand, choosing a colon, a period, or a restructure by what the sentence was doing, because
only judgment knows which. That is the same seam as the sentence gate and the three rules above:
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
  diffs, a claim assertion re-runs, a cited symbol is checked to still exist.
- **State the honest boundary.** Grounding makes the derivable spine drift-proof. It does not make
  the judgment prose (the why, the framing, the positioning) drift-proof; that stays a human or
  advisory-review concern, never a silent gate. Claim "the documented spine cannot silently
  drift," never "the doc can never be stale."

This tier is the newest, added after a real doc described a nine-action system as one that "drafts
customer emails." No amount of voice or structure work catches that; only grounding does.

---

## 8. Pre-publish checklist

Run this against any doc before shipping. Each line is a fail/pass check.

- [ ] Every code block has a prose lead-in ending in `:` and (where useful) a follow-up.
- [ ] No table encodes precedence or an ordering rule; those are prose or numbered lists.
- [ ] Every table's left column is a bare token; every "choose among" table's columns are the
      reader's actual questions.
- [ ] Every "don't" is paired with an "instead"; every warning states a *mechanism*.
- [ ] Callouts are semantic (Warning = harm, Note = easily-missed, Tip = optional) and none
      carries a concept's first explanation.
- [ ] Placeholders and real values are never mixed on one line; language tags are correct
      (`bash` vs `text` vs `json`).
- [ ] The page names its one governing constraint early.
- [ ] No booster adjectives (`seamless`, `powerful`, `simply`, `comprehensive`, `leverage`, `utilize`). <!-- slop-ok: banned-word registry for the checklist -->
- [ ] Sentences are one-claim; the system is named as an actor; actions are imperative.
- [ ] Sections end by linking outward; version notes are inline at the claim.
- [ ] No process artifact (report, handoff, dispatch, status, blocked-note) is on the
      reader-facing doc surface; that content lives in git, PRs, or issues.
- [ ] Every published doc's audience is a reader, not a future agent.
- [ ] No fact is restated across sibling docs; shared facts have one canonical home, cited.
- [ ] No reference doc carries provenance, receipts, or baseline deltas; those go in a changelog.
- [ ] No sentence restates a prior sentence; each section leads with its takeaway.
- [ ] Each doc names its one job in its first line; docs >120 lines and sections >40 lines
      justify staying whole or split.
- [ ] Every factual claim (capabilities, flags, counts, routes) traces to a source in the code,
      not to memory or an old draft.
- [ ] The first screen defines what the system is and does; a reader with no context could state
      it back.
