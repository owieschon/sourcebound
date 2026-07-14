# Learn clean-docs

<!-- clean-docs:purpose -->
This learning path is for maintainers deciding whether source-bound documentation fits their repository. It replaces vague confidence in prose with a mental model, a runnable drift repair, and a clear authority boundary, so you can choose the shortest page for the question in front of you.
<!-- clean-docs:end purpose -->

Documentation drift is a source-derivation problem before it is a discipline problem. Review can
catch a stale sentence, but it cannot make the relationship between that sentence and its defining
source repeatable. clean-docs makes that relationship explicit and checks it again after the code
moves.

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
