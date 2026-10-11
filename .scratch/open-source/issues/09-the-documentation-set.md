# The documentation set

Type: grilling
Mode: HITL
Status: resolved
Blocked by: 01, 03, 08

## Question

Which markdown documents does the release ship, and what does each hold? A README that takes an adopter from `uv tool install naiad` to a finished Run of the starter; an authoring guide, which today is `docs/workflow-authoring.md` written for one file; something on the Protocol and hooks from the agent's side; something on the Answerer, notifications (`NAIAD_NTFY_URL`) and tmux as prerequisites. Decide the set, what each document is for and who reads it, which existing documents are rewritten versus retired, and where the personal workflow's example documentation sits.

## Comments

2026-09-19, from "The starter workflow": three facts the starter's Run surfaced that the documentation has to carry. The starter adds no rules of its own, so the adopter's `CLAUDE.md` and global instructions apply inside a Run (the prototype's plan spoke of the operator's TDD rule). At a Gate the human types a verdict into the Session and sends it, and today has to name the State that follows ("announce implement"), pending ticket 14. And a Question asked from a starter Run parks it for the human, since the file declares no Answerer.

2026-09-26, from "The public repository": the install line is `uv tool install naiad-cli`. The ADRs, `CONTEXT.md` and `docs/smoke/` are untracked and never cited by shipped documents, so `docs/workflow-authoring.md` loses its per-State ADR index and states each reason inline or drops it. The set gains a short `CONTRIBUTING.md`: an issue before a non-trivial PR, tests first, contributions under MIT and 0BSD with no CLA.

## Answer

2026-09-26, grilled with the human in two rounds. No ADR: nothing here is hard to reverse.

### The set

- **`README.md`**, for the adopter's first hour. It opens with the problem in two sentences: a multi-phase Claude Code task means starting each phase's Session by hand, and one long Session bloats its context. One sentence follows on what Naiad does: it drives one Session through a Workflow you declare, clears between phases, and calls you only when it needs you. Its Prompts can run any slash command or skill you have, and no skill set is named. Then:
  - a boxed `bypassPermissions` warning just above Install: every Session runs with permission prompts off, acts on the named repo with your credentials, so try the first Run on a throwaway repo (wording follows "What an adopter can configure, and where");
  - prerequisites: tmux, Claude Code logged in, `gh` optional;
  - `uv tool install naiad-cli`, then `naiad install --starter`;
  - `naiad queue add starter "<task>" --repo .`, then `naiad queue watch`, then `tmux attach`;
  - the folder-trust dialog on a repo Claude Code has never opened, answered in the pane;
  - at `review`: read `PLAN.md`, then type **and send** the verdict (the exact words follow "What the agent and the human each know at a Gate");
  - where the result lands: a pull request, or the branch;
  - the adopter's own `CLAUDE.md` and global rules apply inside a Run, since the starter adds none;
  - a Question with no Answerer parks the Run for you;
  - a Concepts list of about ten terms, one line each, only the terms an adopter meets, written fresh rather than copied from `CONTEXT.md`;
  - a "How it works" of about four bullets, with no ADR citations: the agent announces and Naiad reacts; one Session, cleared between States; nothing is written into your repo except what the Prompts do; the hooks do nothing outside a Run;
  - manual uninstall: which hook entries in `~/.claude/settings.json`, the skill in `~/.claude/skills`, `~/.naiad`, and `uv tool uninstall naiad-cli`;
  - Status: built on macOS and used by one person; Linux works without desktop notifications; tracks Claude Code's hook surface as of 2026;
  - a one-line pointer to `CONTRIBUTING.md`;
  - links to the three guides.
- **`docs/running.md`**, the operator's day-to-day: the queue, watching and attaching, Gates, Questions and the Answerer, reading a Run's Answers, notifications and `NAIAD_NTFY_URL`, `NAIAD_HOME`, Adoption and the `naiad-adopt` skill, tmux as a prerequisite, and troubleshooting, including `naiad doctor`. It is the landing place for the documentation consequences of the configuration, doctor, Reading-Answers and Gate tickets.
- **`docs/workflow-authoring.md`**, rewritten task-first:
  1. start from the starter and change it with the verbs;
  2. build a Workflow from scratch (`workflow new`, `state add`, `workflow check`, then queue it);
  3. State kinds and marks;
  4. slots (`{task}`, `{branch}`, `{predecessor}`, `{subject}`, `{next_state}`): what each renders and when it is empty;
  5. Prompt conventions;
  6. the file by hand: one annotated TOML with each key once, with `workflow check` as the net.

  It also carries a section, "Why the starter is shaped this way": `PLAN.md` at a fixed path so that three cold contexts find it; `verify` as its own cleared State that never parks; one Gate before `implement` and none before `ship`; no settings and no Answerer.
  
  Prompt conventions, each restated inline without ADRs:
  - Kept: a skill's slash command opens the Prompt; what follows is an argument, never a procedure; never restate the Protocol; declare a setting only where it changes; `autocompact` is the file's key; a branching State writes its successors out.
  - Dropped: the implement/triage shared scan and the "pin what a skill leaves loose" exception, both specific to one Workflow.
  - New: after a Clear the agent remembers nothing, so no "you just…"; name the State's hand-off artifact by path.
- **`docs/how-it-works.md`**, the agent's side:
  - The Protocol, paraphrased: announce on entry; `announce`/`ask`/`wait`/`hold`/`branch` and when each is used; rejection of unknown States. Includes one sample block marked illustrative (`naiad protocol` prints nothing outside a Run).
  - The three hooks and what `install` writes.
  - Clears, Switches and the Belief.
  - Why `bypassPermissions`: an unattended Session cannot answer a permission prompt.
  - The terms the README leaves out (Belief, Tick, Switch, Nudge) are explained here where they arise.
- **`CONTRIBUTING.md`**: an issue before a non-trivial PR; tests first and passing; contributions under MIT and 0BSD with no CLA; the README's former Development section (`uv sync`, `pytest`, `mypy`, the layout table); and a sentence saying tmux and Claude adapter changes need a manual Run.
- **`AGENTS.md`**: the agent-facing counterpart to `CONTRIBUTING.md`. It restates the Workflow-files rule with no ADR pointer and retargets it at the starter.
- **No command reference.** `naiad <noun> --help` is the reference. The guides show verbs in task-shaped prose and point at `--help` where the full list matters.
- **No `CHANGELOG.md`** for 0.1. GitHub release notes carry each release, and a changelog returns once the Workflow format is versioned.
- **A drift test**: every `naiad …` line in the fenced code blocks of the shipped docs must parse against the real argparse parser. Prose is not tested.

### Retired or moved

- The README's current content is rewritten into the set above. Its `matt-pocock` example, ADR citations and Development section leave it.
- The excluded `docs/smoke/` becomes the untracked `docs/maintainer/`, holding `matt-pocock-smoke.md` and `matt-pocock-notes.md`. The notes are the old authoring guide's tuning section and its per-State ADR index. This amends "The public repository"'s exclude and filter path list by one rename.
