# The personal Workflow's project file is its own, not Naiad's

ADR 0018 gave a repository a `naiad.toml` to opt out of the pull request, and ADR 0048 spelled a second key in it, `companions`, on the ground that "`naiad.toml` is Naiad's own file" and naming a key in it is Naiad describing its own interface. Naiad never read the file. Only the `pull-request` Prompt of `workflows/matt-pocock.toml` did, and that file is the maintainer's personal Workflow: it opens its States with slash commands from a third-party plugin and is not what Naiad offers anyone. The first open-source release ships a starter instead (ADR 0049) and drops `naiad.toml` and `naiad init` from Naiad.

We decided the project file belongs to the personal Workflow, not to Naiad. It is renamed `.matt-pocock.toml`, so that its name says whose convention it is and no file called `naiad.toml` suggests Naiad reads it; its two keys, `companions` and the pull-request opt-out, are unchanged, and the `pull-request` Prompt is edited to read the new name. An adopter's Workflow keeps its per-project facts wherever its own Prompts say — a TOML file, a text file, a line in `AGENTS.md` — and Naiad has no opinion on it.

The personal Workflow stays in this repository at `workflows/matt-pocock.toml`, a regular tracked file anyone can read. `naiad install` never offers it, it is not package data, and no adopter-facing document names it. The maintainer's library keeps its hand-made link to it, unchanged (ADR 0037, ADR 0049).

## Considered alternatives

**Keeping the name `naiad.toml`** needed no change in the maintainer's projects. Rejected because a file of that name at a repository root reads as Naiad's configuration, which is the claim this ADR retracts.

**Moving the two facts into each project's `AGENTS.md` as prose** was rejected for ADR 0048's reason: the Prompt runs after a Clear, and a list of paths an agent has to recognise by shape is one it can fail to recognise.

**An `examples/` directory**, or a second file shipped in the package, would offer the Workflow to adopters, and it depends on a plugin Naiad does not own. **A repository of its own** would hide nothing the maintainer wanted hidden and separate the file from its history.

## Consequences

The maintainer's projects that keep a `naiad.toml` rename it to `.matt-pocock.toml`.

**Companion repository** leaves `CONTEXT.md`: it is a concept of one Workflow's Prompt, not a term an adopter meets anywhere in Naiad. ADR 0048 and ADR 0051 keep their wording as the record of how that Prompt came to be.

The shipped-workflow tests (ADR 0043) run their invariants over the starter and over the personal Workflow alike, since the file stays tracked and the invariants read no content.
