# naiad-v2

## Workflow files

`workflows/*.toml` is configuration a human hand-edits. Keep it that way: a
comment is a one-line ADR pointer, never an explanation. Reasoning that needs
writing down goes to `docs/adr/`. Prompt conventions are in
`docs/workflow-authoring.md`.

## Agent skills

### Issue tracker

Issues live as markdown files under `.scratch/<feature>/` in this repo — no external tracker, no PR triage surface. See `docs/agents/issue-tracker.md`.

### Triage labels

The five canonical triage roles, each using its default string (`needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`), recorded as a `Status:` line in each issue file. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: one `CONTEXT.md` and `docs/adr/` at the repo root. See `docs/agents/domain.md`.
