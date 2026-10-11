# naiad-v2

## Workflow files

`naiad/workflows/starter.toml` and `workflows/*.toml` are configuration a human
hand-edits, and they ship to projects that know nothing of this repository.
Keep them that way: a comment in one holds no pointer to any document and no
explanation of why. Reasoning that needs writing down goes in
`docs/workflow-authoring.md`, beside the Prompt conventions.

## Agent skills

### Issue tracker

Issues live as markdown files under `.scratch/<feature>/` in this repo — no external tracker, no PR triage surface. See `docs/agents/issue-tracker.md`.

### Triage labels

The five canonical triage roles, each using its default string (`needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`), recorded as a `Status:` line in each issue file. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: one `CONTEXT.md` and `docs/adr/` at the repo root. See `docs/agents/domain.md`.
