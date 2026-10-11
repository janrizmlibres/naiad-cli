# What an adopter can configure, and where

Type: grilling
Mode: HITL
Status: resolved
Blocked by:

## Question

Which of Naiad's fixed assumptions become settings, and at what level does each live: the Workflow file, an environment variable, or a constant that stays? The candidates the charting survey found: the `bypassPermissions` mode every spawned Session and the Answerer run with (a session-spec field no file can set); the tuning constants (two Nudges, silence at 120 s, hang at 1800 s, default Wait 600 s, Wait budget 1800 s, Clear confirmation 8 s with 3 retries, consultation timeout 300 s); the home directory (`NAIAD_HOME`, default `~/.naiad`); the notification legs (terminal always, desktop only where `osascript` exists, push only with `NAIAD_NTFY_URL`); and where install writes (`~/.claude/settings.json`, `~/.claude/skills`). Decide per item: setting or constant, and its home. The rule to hold to: a Workflow key is for what varies per workflow, an environment variable for what varies per machine, a constant for what should not vary at all. Do not open the tmux dependency here; it is a prerequisite, and a second session adapter is fog.

## Answer

Resolved in a grilling session, 2026-09-27. Held to the ticket's rule: a Workflow key for what varies per workflow, an environment variable for what varies per machine, a constant for what should not vary. No item turned out to vary per workflow, so no Workflow key is added.

- **Permission mode: constant.** `bypassPermissions` stays fixed for every Session and the Answerer. A permission prompt would stall a Run as unexplained silence, and a settable mode needs the engine to recognise such a prompt, which is a signal and not a setting. Containment is the machine's job (container, VM, devcontainer), and the README says so. ADR 0057.
- **Tuning constants: all constant.** Two Nudges, silence 120 s, hang 1800 s, default Wait 600 s, Wait budget 1800 s, Clear confirm 8 s × 3, delivery × 3, consultation 300 s. Silence, Nudge, Clear and delivery describe Claude Code and tmux, not a workflow. A State key for the hang bound or Wait budget goes into the map's fog, and returns only if an adopter's long-running State hits it.
- **Home directory: environment variable, unchanged.** `NAIAD_HOME`, default `~/.naiad`, no XDG default. Moving the default later would strand existing Runs.
- **Notification legs: unchanged, no new switches.** The terminal always fires, the desktop fires where `osascript` exists, push fires with `NAIAD_NTFY_URL` (+ `NAIAD_NTFY_TOKEN`). No mute switch. ntfy priority stays fixed because it carries the Notification/Report distinction (ADR 0055). Linux desktop stays fog.
- **The `claude` binary: unchanged.** Found on `PATH` by its bare name. `PATH` is already the machine's setting, and a wrapper named `claude` covers the non-standard case. No `NAIAD_CLAUDE`.
- **Where install writes: honours `CLAUDE_CONFIG_DIR`.** When it's set, `naiad install` writes the hooks into `$CLAUDE_CONFIG_DIR/settings.json` and the skill into `$CLAUDE_CONFIG_DIR/skills`, and falls back to `~/.claude` otherwise. It is a variable Claude Code already defines, so Naiad reads it and invents none, and adds no flags. Without this, hooks written to a directory Claude Code doesn't read make every Session look silent. Claude Code's settings docs confirm user `settings.json` moves with the variable. The docs don't say so outright for personal skills, so the spec verifies that first, and if skills don't move, the skill path stays `~/.claude/skills`.
- **Written down for the adopter:** `docs/running.md` gets a short "What you can configure" section listing `NAIAD_HOME`, `NAIAD_NTFY_URL`, `NAIAD_NTFY_TOKEN`, and `CLAUDE_CONFIG_DIR` as the one variable Naiad reads but doesn't own, plus a line saying the timings and the permission mode are fixed on purpose. There is no separate configuration page.
