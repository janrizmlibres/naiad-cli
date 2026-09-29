# Naiad

Naiad drives a multi-phase Claude Code workflow to completion without a human at each step.

You describe a workflow as an ordered list of states in a TOML file. Each state carries a prompt (usually a slash command invoking a skill), an optional model and reasoning effort, and whether entering it clears the session's context. Naiad opens one Claude Code session in tmux, delivers the first prompt, and from then on reacts to what the agent announces: it clears context between states, types the next prompt, switches models, answers the agent's questions, parks at gates for a human, and notifies you when it needs you or when it is done.

The shipped workflow, `workflows/matt-pocock.toml`, takes a task from classification through diagnosis or a grilling interview, a spec, tickets, implementation, triage, and a pull request. Overnight, if you let it.

## How it works

- **The agent owns workflow state.** The agent declares which state it is in with `naiad announce <name>`. Naiad only reacts. It never guesses where the agent is.
- **Naiad never reads Claude Code internals.** Turn boundaries come from a `Stop` hook and a `SessionStart` hook, and a `UserPromptSubmit` hook confirms each Prompt arrived whole. `naiad install` writes all three into your user settings. The hooks do nothing when no run is attached.
- **One session per run, cleared between states.** A prompt is delivered only after the `/clear` is confirmed. An unconfirmed clear is retried a bounded number of times before a human is told. Artifacts in the repository (ADRs, specs, tickets) carry state across the clears.
- **Per-state model and effort.** A state may pin a model and reasoning effort. Switches are typed into the session one per tick, and Naiad keeps a belief of the session's current settings so an unchanged setting costs nothing.
- **Gates and branches.** A gate state has no prompt. The run parks and you type directly into the session. A branching state lets the agent choose the next state (a task classifies itself as a bug or a feature, for example).
- **A headless answerer.** When the agent runs `naiad ask`, a separate headless Claude invocation answers on its own model, with a fallback list, one question at a time.
- **A queue, one run per working tree.** `naiad run` adds an entry to the queue and then becomes the supervisor if nothing else is. Entries for different working trees run concurrently. A parked run blocks its lane.
- **Nothing is written into the target repository.** Runs, the queue, and logs live under `~/.naiad` (override with `NAIAD_HOME`).

Every one of those rules has an ADR under `docs/adr/`. The vocabulary (Workflow, State, Prompt, Pin, Gate, Session, Clear, Switch, Belief, Tick, Announcement) is fixed in `CONTEXT.md`.

## Requirements

- Python 3.11+ and [uv](https://docs.astral.sh/uv/)
- tmux
- [Claude Code](https://claude.com/claude-code) on your PATH, logged in
- For the shipped workflow: a repository set up for the Matt Pocock skills (`/setup-matt-pocock-skills`), and a GitHub or Gitea MCP server configured if you want the final state to open a pull request. A `naiad.toml` marker at the repository root opts out of the pull request.

## Install

```
git clone git@github.com:janrizmlibres/naiad-cli.git
cd naiad-cli
uv sync
uv run naiad install
```

`naiad install` writes the three hooks into `~/.claude/settings.json` (preserving everything else there), installs the `naiad-adopt` skill into `~/.claude/skills`, and links the shipped workflow into the library so it can be named as `matt-pocock` from anywhere.

Optional phone notifications go through [ntfy](https://ntfy.sh). Export `NAIAD_NTFY_URL=https://ntfy.sh/<your-topic>` (and `NAIAD_NTFY_TOKEN` if the topic is protected). Terminal and desktop notifications need no setup.

## Run a workflow

```
uv run naiad run matt-pocock "Add rate limiting to the public API" \
  --repo /path/to/repo --branch feat/rate-limiting
```

Naiad prints the entry id, the run id, and the Claude session id as it starts. Watch the agent work with `tmux attach -t naiad-<run-id>` and detach with `C-b d`.

Useful flags on `naiad run`:

| Flag | What it does |
|---|---|
| `--repo` | The target repository. Defaults to the working directory. |
| `--branch` | The working branch. Omit it and the agent derives one from the repository's conventions. |
| `--base` | A branch this work stands on, so the run's branch is created from it when it has not landed yet. |
| `--at` | Start at a named state instead of the first. |
| `--subject` | What the starting state is about, for states whose prompt names one. |
| `--skip-gates` | Resolve past gate states for a fully unattended run. |

`naiad states matt-pocock` lists what a workflow declares, to choose a state for `--at`.

## The queue

```
uv run naiad queue add matt-pocock "<task>" --repo /path/to/repo   # queue without supervising
uv run naiad queue add --file tasks.toml                             # queue several at once
uv run naiad queue list                                              # entries in order, with what became of each and the State it stands in
uv run naiad queue watch                                             # take the queue in order and keep following it
uv run naiad queue rm <entry-id>                                     # cancel an entry and free its session
uv run naiad queue prune                                             # remove done entries and their runs
```

Entries in the same working tree run one after another, so a second entry can build on the branch the first one made. Entries in different working trees run side by side.

## Adopt the session you are in

From inside a live Claude Code session, ask the agent to run the `naiad-adopt` skill (for example "naiad, spec this out"). The agent runs `naiad adopt`, which queues a run that takes over the current session, with the conversation so far still in context, and drives the remaining states from there.

## Commands the agent uses

These are typed by the agent, not by you. The `SessionStart` hook prints the protocol that teaches them to every fresh context.

| Command | Meaning |
|---|---|
| `naiad announce <name> [--subject ...]` | Announce the state the agent is in. |
| `naiad ask "<question>" --option ... ` | Ask a question the agent cannot decide alone. The answerer replies. |
| `naiad wait "<reason>" [--seconds N]` | Declare a wait so silence is not misread as a stall. |
| `naiad hold "<reason>"` | Relay the human's request to pause. The run parks until they return. |
| `naiad branch <name>` | Declare the working branch the agent created. |

## Writing a workflow

Copy `workflows/matt-pocock.toml` and edit. `docs/workflow-authoring.md` covers the prompt conventions, the placeholders a prompt can carry (`{task}`, `{branch}`, `{predecessor}`, `{subject}`, `{next_state}`), and why each state in the shipped file is shaped the way it is. The workflow file is meant to be hand-edited by someone who has never seen this repository, so it carries no ADR pointers of its own.

## Development

```
uv sync
uv run pytest
uv run mypy naiad
```

The tests cover the decision core, the queue, the runtime, the hooks and the shipped workflow's invariants. The tmux and Claude adapters are checked by hand against a real repository, following `docs/smoke/matt-pocock.md`.

Layout:

```
naiad/domain     pure decisions: transitions, prompts, questions, supervision
naiad/runtime    runs, the queue, announcements, answers, the tick loop
naiad/adapters   tmux, the answerer, notifications, locks, executables
naiad/cli        the operator's and the agent's commands
naiad/hooks      installing the Stop, SessionStart and UserPromptSubmit hooks
naiad/skills     the naiad-adopt skill
workflows/       shipped workflow files
docs/adr/        one decision per file
```

## Status

Version 0.1.0. Built and used by one person, on macOS, against Claude Code as it was in mid-2026. Expect the hook and slash-command surface to move with Claude Code itself.
