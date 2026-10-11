# 16 — README, `CONTRIBUTING.md`, `AGENTS.md`, and the docs drift test

Status: resolved
Mode: AFK
Blocked by: 01, 04, 07, 09, 13
Spec: [PRD](../PRD.md), "Documentation"; map tickets [09](../issues/09-the-documentation-set.md), [12](../issues/12-what-an-adopter-can-configure-and-where.md), [14](../issues/14-what-the-agent-and-the-human-each-know-at-a-gate.md)

**What to build:** The adopter's first hour, the contributor's rules, and the test that keeps both honest.

- **README**, in order:
  - the problem in two sentences and what Naiad does in one;
  - the boxed `bypassPermissions` warning, with containment being the machine's job;
  - prerequisites;
  - `uv tool install naiad-cli`, then `naiad install --starter`;
  - `queue add starter`, `queue watch`, `tmux attach`;
  - the folder-trust dialog;
  - at `review`: the notification names `implement`; read `PLAN.md`, then type and send a verdict;
  - where the result lands;
  - the adopter's own `CLAUDE.md` applies inside a Run;
  - a Question with no Answerer parks the Run;
  - Concepts (about ten terms);
  - How it works (four bullets);
  - manual uninstall under `CLAUDE_CONFIG_DIR` or `~/.claude`;
  - Status;
  - the license in one line;
  - links to the guides and `CONTRIBUTING.md`.

  The old `matt-pocock` example, the citations, `naiad.toml`, and the Development section leave it.
- **`CONTRIBUTING.md`:**
  - an issue before a non-trivial PR;
  - tests first and passing;
  - contributions under MIT and 0BSD with no CLA;
  - the development setup and layout table from the old README;
  - tmux and Claude adapter changes need a manual Run.
- **`AGENTS.md`:** the Workflow-files rule restated for the starter with no document pointer. The Agent-skills block stays until ticket 19 moves it.
- **The drift test:** it collects every line starting `naiad ` inside fenced code blocks of `README.md`, `CONTRIBUTING.md` and `docs/*.md`, splits each shell-style, and parses it with the parser function from ticket 01. Prose is not tested.

- [ ] The drift test passes, and fails when a documented verb is renamed.
- [ ] No tracked doc touched here cites an ADR, `CONTEXT.md`, a ticket or `.scratch`.
- [ ] The README walkthrough matches the starter's States and the Gate wording from ticket 07.
