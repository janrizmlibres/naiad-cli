# naiad doctor and the refusals

Type: grilling
Mode: HITL
Status: resolved
Blocked by: 12

## Question

What does `naiad doctor` check, and which verbs refuse on their own when a prerequisite is missing? Today a machine without `tmux` or `claude` on PATH gets a Python traceback from `subprocess.run`, not a sentence. Decide: the doctor's checklist (tmux; `claude` and the version floor its flags imply, `--effort`, `--fallback-model`, `--autocompact`, `--permission-mode`; the hooks in the settings file; the adopt skill; the library and its entries resolving; which notification legs will fire, the desktop leg being macOS-only; `NAIAD_HOME` writable); whether each finding is a failure, a warning, or information; whether doctor fixes anything or only reports (install already self-heals its own three); and which verbs refuse before acting, `run`, `queue watch`, `adopt`, `ask` through the Answerer, each with one sentence naming the missing binary. Blocked by the configuration ticket because what is configurable is what doctor reads.

## Comments

2026-09-26, from "The documentation set": the map's first-run smoke fog patch is cleared. The README's first-Run walkthrough now covers the folder-trust dialog and the typed-but-unsent verdict. What an adopter sees on a machine with no tmux, no ntfy or no hooks installed is this ticket's to decide, and its documentation goes in `docs/running.md` under troubleshooting.

- 2026-09-27, from "What an adopter can configure, and where": `naiad install` now honours `CLAUDE_CONFIG_DIR`, so any check that the hooks or the skill are installed must look at `$CLAUDE_CONFIG_DIR` when it's set, and at `~/.claude` otherwise. The permission mode, the timings, `NAIAD_HOME`, the notification legs and `claude` on `PATH` are unchanged.

## Answer

Resolved in a grilling session, 2026-09-27.

- **One set of checks, two callers.** Each check has one severity. A verb that starts or drives a Run runs the failure-level checks before it acts and refuses on the first failure. `naiad doctor` runs every check and prints them all. A check can't pass in one place and fail in the other.
- **Doctor only reports.** It repairs nothing. Every finding ends with the command that fixes it (`naiad install`, `brew install tmux` / `apt install tmux`), and `install` stays the one verb that writes Claude Code's configuration. Doctor exits non-zero only when a check fails.
- **The checklist:**
  - **fail:** `tmux` on `PATH`; `claude` on `PATH`; `NAIAD_HOME` exists or can be created, and is writable; the hooks are present in the settings file Claude Code reads (`$CLAUDE_CONFIG_DIR/settings.json` when the variable is set, `~/.claude/settings.json` otherwise); the hooks name this `naiad`'s absolute path (a stale path from a moved install fails).
  - **warn:** `claude --version` is below the floor; the adopt skill is missing (looked for where install writes it, per "What an adopter can configure, and where"); a library entry does not load (broken symlink, bad TOML, or a `workflow check` failure), naming the file; a running tmux server's global `PATH` (`tmux show-environment -g PATH`) has no `claude`, fixed by restarting the server. This last check is doctor-only, and entrances check the caller's `PATH`.
  - **info:** the library is empty (points at `naiad install --starter`); which notification legs will fire: the terminal always, the desktop where `osascript` exists, push when `NAIAD_NTFY_URL` is set.
- **The version floor.** Doctor parses `claude --version` and compares it with one floor constant: the Claude Code release that has every flag Naiad can pass (`--permission-mode`, `--session-id`, `--model`, `--effort`, `--fallback-model`, `--autocompact`). The spec looks up the exact number. It is at or below 2.1.283. It is a warning because a Workflow that uses none of the newer flags still runs. A version string that does not parse gives "could not tell" as a warning, never a failure. `--help` is not parsed.
- **Which verbs refuse.** `naiad run`, `naiad watch` (the ticket's "queue watch"), `naiad adopt`, and the Supervisor wherever it starts, including an `adopt` or `run` that turns into one. `naiad queue add` does not check: an Entry can be queued on a machine that runs it later, and the Supervisor that picks it up refuses in its place. Protocol verbs and hook verbs never check, because they run inside a live Session.
- **`ask` through the Answerer.** No refusal. A consultation that can't run already escalates to the human, which is the right outcome. Only the Escalation reason becomes a sentence, e.g. "the Answerer could not be run: `claude` is not on PATH".
- **The refusal's shape.** One line on stderr, exit 2: the missing thing, why Naiad needs it, the fix, then `naiad doctor`. For example: `naiad: tmux is not on PATH; every Session runs in tmux. Install it (brew install tmux, apt install tmux), then run `naiad doctor`.` The entrance stops at the first failure. Doctor lists them all.
- **Install ends with doctor's report.** An adopter sees a missing prerequisite on the first command they type. Install's exit code stays its own.
- **No test notification.** Doctor stays read-only. A test send to each leg goes to the map's fog.
- **Documented** in `docs/running.md` under troubleshooting, one entry per failure and warning, as "The documentation set" routed it.
- No new glossary term and no ADR: doctor and its checks are CLI surface, not domain.
