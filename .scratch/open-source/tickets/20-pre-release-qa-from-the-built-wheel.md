# 20 — Pre-release QA from the built wheel

Status: resolved
Mode: HITL
Blocked by: 14, 16, 17, 18
Spec: [PRD](../PRD.md), "Testing Decisions" (the QA plan)

**What to build:** The spec's QA plan, run from the wheel before anything is published. It needs a real Claude Code, tmux and a human at a Gate.

1. On a machine or user with no Naiad: `uv tool install <wheel>`, then `naiad install --starter`. The closing report shows no failures.
2. `naiad doctor` with `tmux` off `PATH` fails with exit 1, and `naiad run` refuses in one line.
3. On a throwaway repository with a small test suite: `queue add starter`, `queue watch`, `tmux attach`, and answer the folder-trust dialog. At `review`:
   - the notification names `next: implement`;
   - `queue list` shows `parked  review`;
   - the agent's reply said a human takes it from here;
   - a sent "go ahead" moves the Run on with no State named.
4. The Run reaches `done` through three confirmed Clears. `PLAN.md` is removed in its own commit, and there is a pull request with `gh`, or the branch otherwise.
5. `naiad queue answers <entry>` prints `no questions were asked in <run>`.
6. Step 3 again with `CLAUDE_CONFIG_DIR` set.
7. Every README command block walked by hand.

Record the Run ids and findings in this ticket's Comments. A failure becomes a new ticket rather than being fixed inside this one.

- [x] Every step passes, or each failure is ticketed.

## Comments

### 2026-09-29 — isolated-directory pre-flight (agent, not the QA itself)

An agent ran only steps 1, 2 and the README blocks that start no Run. This is a pre-flight in isolated directories on the maintainer's machine, not the clean-machine run step 1 asks for. Steps 3–6 and the rest of step 7 are still for the human, and the checkbox stays unticked.

**Setup.** Wheel `naiad_cli-0.1.0-py3-none-any.whl` built with `uv build --wheel` from a `git archive` of `9201208`. The build ran offline from the uv cache because the sandbox had no network. Contents: the `naiad` package, `naiad/workflows/starter.toml`, and `LICENSE` plus `LICENSES/0BSD.txt` under `licenses/`. Metadata: `License-Expression: MIT AND 0BSD`, `Requires-Dist: tomlkit>=0.15.1`, Python >=3.11. Environment:
- a scratch `HOME`, with `UV_TOOL_DIR`/`UV_TOOL_BIN_DIR` inside it;
- `NAIAD_HOME` and `CLAUDE_CONFIG_DIR` unset, and every `CLAUDE*` variable unset;
- `PATH` holding only the isolated `naiad`, plus shims for `claude` (2.1.284) and `tmux`, plus system dirs, so the maintainer's own `naiad` was not on it.

**Run ids.** None. No Run was started. One Entry was queued and removed: `20260929-061625-462137-starter-7814`.

**Step 1 — pass.** `uv tool install <wheel>` installed `naiad-cli==0.1.0` and `tomlkit==0.15.1`. `naiad install --starter` wrote five hooks: `SessionStart` startup/clear/compact → `naiad protocol`, `Stop` → `naiad stopped`, `UserPromptSubmit` → `naiad submitted`. Each uses the tool's absolute path. It also installed `skills/naiad-adopt/SKILL.md` and copied `starter.toml` byte-identical into `~/.naiad/workflows`. The closing report was a single `info  notifications will fire through: terminal, desktop`, with no fail or warn, exit 0. `naiad doctor` alone gave the same result. Rerunning `install --starter` exited 0 and left the hook count at five, so no hooks were duplicated.

**Step 2 — pass.** With `tmux` off `PATH`:
- `naiad doctor` printed `fail  tmux is not on PATH — install tmux (macOS: brew install tmux)` and exited 1.
- `naiad run starter "qa probe"` refused in one line and exited 2: `naiad: tmux is not on PATH — naiad runs every Run in a tmux session; install tmux (macOS: brew install tmux), then run \`naiad doctor\``.
- `naiad queue watch` gave the same line and exit code.

**Step 7, the blocks that start no Run — pass.**
- The install block is step 1 above.
- `naiad queue add starter "Add a --dry-run flag to the export command" --repo .`, run on an empty throwaway git repo, queued the Entry. `queue list` then showed `waiting  -`.
- `queue answers <entry>` on the unstarted Entry printed `… has not started, so it has no answers yet`, exit 0.
- `queue rm` removed the Entry.
- `tmux ls` exited 0.
- With `NAIAD_NTFY_URL` set, doctor reported `terminal, desktop, push`.
- The Uninstall steps, followed by hand, removed exactly the hooks the README names (three `naiad protocol`, one `naiad stopped`, one `naiad submitted`), leaving `{"hooks": {}}`. Deleting `skills/naiad-adopt` and `~/.naiad` and running `uv tool uninstall naiad-cli` left no `naiad` on `PATH`.

**Left for the human:** step 1 on a genuinely clean machine or user, steps 3–6, and the README blocks that start or watch a Run (`naiad queue watch`, `tmux attach -t naiad-<run-id>`, and the five numbered first-Run steps).

**Failures ticketed:** none. Observations, not failures:
- The copied `starter.toml` lands with mode `0600`.
- A repeat `naiad install` says "installed …" even when nothing changed.
- `naiad run` and `queue watch` refuse with exit 2 where `doctor` exits 1. The ticket only fixes doctor's code.

### 2026-09-29 — the QA run in a clean Linux container (human at the Gates, agent observing)

**Machine.** A container built from `.scratch/open-source/qa/Dockerfile` (untracked): `debian:trixie-slim` with tmux 3.5a, git 2.47.3, gh 2.46.0, uv 0.12.20, Claude Code 2.1.284 and a non-root user `qa`, and no Naiad. The wheel is the one from the pre-flight (`9201208`). The human logged Claude in, answered both folder-trust dialogs and sent both "go ahead"s. The agent ran every other command through `docker exec` and read the Runs from outside.

**Run ids.**
- Run 1: `20260929-064533-starter-238`, Entry `20260929-064533-615314-starter-229`, repo `~/qa1`, task "Add a subtract function with a test", default `~/.claude`.
- Run 2: `20260929-094628-starter-1752`, Entry `20260929-094627-945035-starter-1743`, repo `~/qa2`, task "Add a multiply function with a test", `CLAUDE_CONFIG_DIR=/home/qa/claude-alt`.

**Step 1 — pass.** `uv tool install ~/naiad_cli-0.1.0-py3-none-any.whl` fetched `tomlkit==0.15.1` from PyPI. `naiad install --starter` installed the hooks, the skill and the starter. The closing report was only `info  notifications will fire through: terminal` (Linux, so no desktop leg), exit 0.

**Step 2 — pass** (pre-flight above).

**Step 3 — pass (Run 1).** The trust dialog appeared and the Run waited on it. At `review`:
- the watcher printed `state 'review' is a Gate State and is waiting for you; next: implement`;
- `queue list` showed `parked   review`;
- the announce reply was `review is a Gate: a human takes it from here. End your turn and wait for them.`, and the agent ended its turn saying it was waiting for a person;
- the human's "go ahead" moved the Run to `implement` with no State named.

**Step 4 — pass (both Runs).** Each log reads `cleared` → `delivered` → `confirmed` for `implement`, `verify` and `ship`, then `finished done`. `PLAN.md` was removed in its own commit: `ae924a5` on `feat/subtract` and `66e8253` on `feat/multiply`, each touching only `PLAN.md`. The container has no remote, so each Run stopped at the branch and its closing words name it. Tests: `2 passed` on both branches.

**Step 5 — pass.** `naiad queue answers` printed `no questions were asked in 20260929-064533-starter-238` for Run 1 and the same for Run 2.

**Step 6 — pass (Run 2).** `naiad install --starter` with `CLAUDE_CONFIG_DIR` set wrote the hooks to `/home/qa/claude-alt/settings.json` and the skill to `/home/qa/claude-alt/skills/naiad-adopt`, and `doctor` was clean. The Session's `claude` process had `CLAUDE_CONFIG_DIR=/home/qa/claude-alt` in its environment, taken from the tmux global environment. Its transcript landed under `claude-alt/projects`, and nothing for `qa2` appeared under `~/.claude`. All the step 3 and step 4 checks passed again.

**Step 7 — pass, walked in the container.** The install block, `queue add`/`queue watch`, `tmux ls`/`tmux attach -t naiad-<run-id>`, and the five numbered first-Run steps (trust, `plan`, `review`, `implement`/`verify`/`ship`, `done`) all matched what the README says. The Uninstall steps were walked in the pre-flight.

**Not exercised.** The desktop notification leg (the container is Linux) and a pull request through `gh` (no remote). The ticket accepts "the branch otherwise", so the pull request path waits for post-publish QA, when a real remote exists.

**Failures ticketed:** none. Observations, not failures:
- Run 2's trust dialog sat unanswered for over 30 minutes, and the watcher printed `the session produced no signal for 1800s`. That is the silence alarm working. The README's trust step says only "The Run waits for you", so an adopter who steps away will also get this notification.
- Run 2's closing lines ended `Branch: feat/multiply` then `Done.`, so the branch is next-to-last rather than the last words the README promises. Run 1 ended with the branch. This is agent wording, not Naiad.
- Read in the instant between a Gate's `announced` and `notified` lines, `queue list` shows `running  review`, and `parked` a moment later. Nothing is wrong once the Tick completes.
