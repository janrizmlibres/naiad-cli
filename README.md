# Naiad

A task that takes several phases of Claude Code, such as planning, building, checking and shipping, means starting each phase's session by hand, and one long session bloats its context until the agent loses the thread. Naiad drives one Claude Code session through a Workflow you declare, clears its context between phases, and calls you only when it needs you.

Its Prompts can run any slash command or skill you have. The starter Workflow that ships with it runs none: it takes a small feature or fix on any repository from a plan to a pull request.

## Before you start

> [!WARNING]
> **Every Session Naiad opens runs in `bypassPermissions` mode.** Claude Code asks for no permission before it edits files, runs commands or pushes, and it acts on the repository you name with your credentials. An unattended Session cannot answer a permission prompt, so the mode is not a setting. Containment is your machine's job: a container, a VM or a devcontainer. Try your first Run on a throwaway repository.

You need:

- [uv](https://docs.astral.sh/uv/)
- tmux
- [Claude Code](https://claude.com/claude-code) 2.1.221 or newer on your `PATH`, logged in
- optionally, `gh`, installed and authenticated, so the last phase can open a pull request

## Your first Run

```
uv tool install naiad-cli
naiad install --starter
```

`naiad install` writes three hooks into your Claude Code user settings, keeping everything else there, installs the `naiad-adopt` skill, and copies the starter Workflow into `~/.naiad/workflows`. It ends with `naiad doctor`'s report, which names anything your machine still lacks. Run `naiad doctor` on its own any time.

Then, from the repository you want the work done in:

```
naiad queue add starter "Add a --dry-run flag to the export command" --repo .
naiad queue watch
```

`queue watch` takes the queue in order and keeps following it, so leave it running. In another terminal, find the Run's tmux session and watch the agent work:

```
tmux ls
tmux attach -t naiad-<run-id>
```

Detach with `C-b d`; the Run carries on.

1. **Trust the folder.** On a repository Claude Code has never opened, it asks whether you trust the folder. Answer in the pane. The Run waits for you.
2. **`plan`.** The agent creates a branch and writes `PLAN.md` at the repository root, committed on it.
3. **`review`.** This is a Gate. Naiad tells you, by terminal, desktop and, if you set it up, phone notification, that `review` is waiting for you and that `implement` is next. Read `PLAN.md`, then type a verdict into the Session **and send it**: "go ahead", or what to change. The agent announces the next State itself. Name a State only to send it somewhere else.
4. **`implement`, `verify`, `ship`.** Each starts from a cleared context and reads `PLAN.md` cold. `ship` removes the plan, and opens a pull request when the repository has a remote and `gh` can push. Otherwise it stops at the committed branch.
5. **`done`.** You are notified, and the last words in the Session name the branch and the pull request.

Things worth knowing on a first Run:

- Your own `CLAUDE.md` and global instructions apply inside a Run. The starter adds no rules of its own, so your testing and commit conventions carry over.
- The starter declares no Answerer, so a Question the agent cannot decide alone parks the Run and notifies you. Answer it in the Session.
- Naiad writes nothing into your repository. What lands there is what the Prompts make the agent do.
- Optional phone notifications go through [ntfy](https://ntfy.sh): export `NAIAD_NTFY_URL=https://ntfy.sh/<your-topic>`, and `NAIAD_NTFY_TOKEN` if the topic is protected.

## Concepts

- **Workflow**: an ordered list of States in a TOML file. Swapping the file swaps the work.
- **State**: one phase of a Workflow, with a name, usually a Prompt, and whether entering it clears the Session.
- **Prompt**: the text Naiad types into the Session when the agent enters a State.
- **Announcement**: how the agent says which State it is in, with `naiad announce <name>`. Naiad reacts to it and never guesses.
- **Session**: the one tmux Claude Code session a Run uses from start to finish.
- **Clear**: discarding the Session's context between States, so each phase starts clean.
- **Gate**: a State with no Prompt. Naiad parks the Run and you type into the Session.
- **Run**: one Workflow carried out against one task in one working tree.
- **Queue**: the backlog of Runs waiting their turn. Runs in the same working tree go one after another, and Runs in different ones go side by side.
- **Answerer**: an optional headless Claude that answers the agent's Questions so you are not asked. A Workflow opts in with an `[answerer]` table.

## How it works

- The agent owns workflow state. It announces each State it enters, and Naiad only reacts.
- One Session per Run, cleared between States. Files in your repository, like `PLAN.md`, carry the hand-off across each clear.
- Naiad hears about turns ending and contexts clearing through hooks in your Claude Code settings. They do nothing in a session that is not part of a Run.
- Naiad keeps its own records under `~/.naiad` (`NAIAD_HOME` moves it) and nothing in your repository.

## Uninstall

Naiad has no uninstall command. To remove it by hand, under `$CLAUDE_CONFIG_DIR` if you set it, or `~/.claude` otherwise:

- In `settings.json`, delete the hook entries whose command runs `naiad protocol` (three, under `SessionStart`), `naiad stopped` (under `Stop`) and `naiad submitted` (under `UserPromptSubmit`).
- Delete the `skills/naiad-adopt` directory.

Then delete `~/.naiad`, and run `uv tool uninstall naiad-cli`.

## Status

Version 0.1.0. Built on macOS and used by one person. It works on Linux without desktop notifications. It tracks Claude Code's hook surface as of 2026, so expect it to move with Claude Code.

## License

Naiad is MIT licensed. The starter Workflow is 0BSD, so copy it freely.

## Going further

- [Running Naiad](https://github.com/janrizmlibres/naiad-cli/blob/main/docs/running.md): the queue, Gates, Questions, notifications and troubleshooting.
- [Writing a Workflow](https://github.com/janrizmlibres/naiad-cli/blob/main/docs/workflow-authoring.md): start from the starter, or build one from scratch.
- [How it works](https://github.com/janrizmlibres/naiad-cli/blob/main/docs/how-it-works.md): the protocol the agent follows and what the hooks do.
- [Contributing](https://github.com/janrizmlibres/naiad-cli/blob/main/CONTRIBUTING.md)
