# Learn clean-docs

<!-- clean-docs:policy register-v2 -->
<!-- clean-docs:purpose -->
This learning path is for maintainers deciding whether source-bound documentation fits their repository. It replaces vague confidence in prose with a mental model, a runnable drift repair, and a clear authority boundary, so you can choose the shortest page for the question in front of you.
<!-- clean-docs:end purpose -->

**[Catch a lying doc](tutorial-catch-a-lying-doc.md)** to see a source edit fail, repair the bound
region, and return the repository to green.

The tutorial ends with a [`clean-docs.outcome.v1` receipt](../SUPPORT.md#record-local-outcomes)
whose `"ok"` field is `true`.

The useful question is not "who forgot the docs?" It is "which source should have made this claim
fail?" Follow the path that matches your current job:

| If you need to... | Start with | You will leave with... |
| --- | --- | --- |
| Decide what the product is | [Product overview](../../README.md) | The category, fit, architecture, and installation route |
| Protect one fact yourself | [Catch a lying doc](tutorial-catch-a-lying-doc.md) | A working binding, a failed drift check, and a repaired page |
| See the problem at repository scale | [The README that lied](postmortem-the-readme-that-lied.md) | A concrete cleanup case and the limits of its evidence |
| Understand the model boundary | [The deterministic seam](deep-dive-the-deterministic-seam.md) | A precise account of who owns facts, prose, and gate results |

The tutorial is the fastest proof. The postmortem explains why the proof matters beyond a toy
fixture. The deep dive names the mechanism after you have seen it move.

## What this path does not replace

These pages teach a sequence and a mental model. Use the existing [CLI reference](../CLI.md),
[support guide](../SUPPORT.md), and [security model](../SECURITY_MODEL.md) when you need exact current
commands, installation variants, or trust boundaries. The lessons link to those canonical homes
instead of growing stale copies.
