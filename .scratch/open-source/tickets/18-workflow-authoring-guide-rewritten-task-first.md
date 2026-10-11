# 18 — `docs/workflow-authoring.md` rewritten task-first

Status: resolved
Mode: AFK
Blocked by: 11, 12, 16
Spec: [PRD](../PRD.md), "Documentation"; map ticket [09](../issues/09-the-documentation-set.md)

**What to build:** The authoring guide for adopters, in six parts:
1. start from the starter and change it with the verbs;
2. build a Workflow from scratch (`workflow new`, `state add`, `workflow check`, then queue it);
3. State kinds and marks, including `report`, explained on `ship`, and a Gate's hand-off being a verdict;
4. the slots (`{task}`, `{branch}`, `{predecessor}`, `{subject}`, `{next_state}`): what each renders and when it is empty;
5. the Prompt conventions, restated inline:
   - kept: a skill's slash command opens the Prompt, and what follows is an argument, never a procedure; never restate the Protocol; declare a setting only where it changes; `autocompact` is the file's key; a branching State writes its successors out;
   - dropped: the two conventions specific to the personal Workflow;
   - new: no "you just…" after a Clear; name the hand-off Artifact by path;
6. the file by hand: one annotated TOML with each key once, with `workflow check` as the net.

Plus "Why the starter is shaped this way".

The current file's tuning notes and per-State ADR index move to `docs/maintainer/matt-pocock-notes.md`, which ticket 19 untracks. The old smoke doc becomes `docs/maintainer/matt-pocock-smoke.md` there too.

- [ ] The drift test passes over the rewritten file.
- [ ] It cites no ADR, `CONTEXT.md`, ticket or `.scratch`, and never names the personal Workflow.
- [ ] The maintainer notes exist under `docs/maintainer/` with the old content intact.
