# A Run carries a Working branch and a Predecessor

Status: ready-for-agent
Blocked by: None — can start immediately
Spec: `.scratch/queue/PRD.md`

## What to build

An operator starts a Run and says which branch the work belongs on and, optionally, what that work stands on. Both facts reach every Prompt the Run delivers.

`naiad run <workflow> <task> --branch MC-AGENT-8546 [--base <branch>]` records the Working branch and the Predecessor on the Run, and `{branch}` and `{predecessor}` substitute wherever a Prompt names them.

**They are Run-level facts, like the task.** That means every delivered Prompt, not only the first, and it means they survive a Clear — which is the whole point, because both heads of the shipped Workflow Clear and the State that opens a pull request Clears again. A State that has forgotten everything can still name the branch it is working on.

**The Working branch is required, and refused before anything exists.** No derivation is attempted and none is possible: a correct branch name needs the affected application and an issue number, which are conventions of the target repository, and Naiad knows no repository's conventions (ADR 0015). An operator who omits it is standing at the terminal and pays the error message only — the same trade the missing-Subject refusal already makes, and the error should name the flag the way that one names the command to retype.

**The Predecessor is optional and opaque.** When `--base` is given it is recorded verbatim and substituted without being read, exactly as a Subject is; when it is not, `{predecessor}` renders as nothing. Naiad does not check that the branch exists, does not ask git anything, and does not decide whether the Run should actually stand on it — that judgment belongs in the Prompt and arrives in the next ticket.

Substitution keeps the existing discipline: only placeholders Naiad defines are replaced, an absent value renders as nothing rather than raising, and text that merely looks like a placeholder is left alone, because Prompts routinely carry JSON and code.

A Run written before these fields existed must still load, so both read with a default.

**Prefactor, and it is the named Refactor candidate for this ticket.** Prompt rendering reaches five keyword arguments here, three of which are Run-level facts and two of which are not. Consider grouping the Run-level ones into a single object passed through rendering, and record a verdict even if the verdict is to keep the arguments as they are.

## Acceptance criteria

- [ ] Red → Green → Refactor throughout, with the Refactor step named and a verdict recorded even when the verdict is to keep as-is
- [ ] `naiad run` accepts `--branch` and `--base`, and records both on the Run
- [ ] `naiad run` without `--branch` is refused before the Run directory or the session exists, with an error naming what to pass
- [ ] `{branch}` and `{predecessor}` substitute in a State's Prompt, including a State that Clears and a State reached after the first
- [ ] An absent Predecessor renders as nothing rather than raising
- [ ] Text resembling a placeholder that Naiad does not define is left untouched
- [ ] A Run saves and reloads both fields, and a Run's metadata written without them still loads
- [ ] The Refactor verdict on grouping the Run-level rendering arguments is recorded
