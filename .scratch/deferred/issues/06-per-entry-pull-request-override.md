# A per-Entry override for the pull-request default

Status: needs-info
Trigger: an operator wants a single Run to open a pull request, or to skip one, against what the project itself would otherwise do

## What was found

The tail decides how a Run ends by reading the project in front of it: a repository with a host that can open pull requests (GitHub or Gitea) opens one; a repository that has opted out, or has no remote at all, announces `done`. The opt-out is a marker the operator records in the repository — a `naiad.toml` at its root — so that a preference the repository does not otherwise know about itself becomes a fact the agent can read. Default is to open a pull request; the marker suppresses it.

That covers the *project's standing preference*. It does not cover a *single Run* wanting to differ from it — "this repository normally opens pull requests, but not for this one," or the reverse. During the grill we designed the seam for that without building it. The intended shape is a precedence chain, resolved in the tail Prompt where every other tail decision already lives:

```
per-Run override   (if set — highest)
   ↓ else
repo marker        (naiad.toml in the project)
   ↓ else
safe default       (open a pull request wherever one can be opened)
```

For the override to be a true override rather than a one-way opt it is tri-state: unset defers to the repository, `true` opens a pull request even where the marker suppresses one, `false` skips even where the default would open one. The repo-marker work is not throwaway when this lands — it becomes the middle rung.

## Why it is deferred

Delivering a per-Run value to the agent means a sixth placeholder in `render_prompt`, whose docstring closes the set at five ("the task, the next State, the Subject, the branch and what it stands on") and names guarding against a sixth as a reason of its own, plus a new field on `Entry`. That is real surface, and ADR 0016 already weighed a per-Entry flag for the neighbouring skill-naming problem and rejected it — it "buys explicitness at queue time for a fact the repository already knows about itself." No Run needs the override yet, and paying the placeholder cost speculatively is the thing 0016 warned against.

What is worth recording is *why this is not simply the same rejection*. ADR 0016's objection was that the flag duplicated a fact the repository holds. An override is the opposite case — it is the operator telling Naiad something the repository does *not* hold, that this one Run should differ from the project's standing default. So when a concrete use arrives the flag is defensible in a way it was not for the default, and it should get its own ADR, which will have an honest argument to make rather than reopening a settled one.

## Constraints this places on the work shipping now

None. The repo-marker design leaves the seam open deliberately: the override slots *above* the marker in the same tail-Prompt decision, changing nothing already written. Do not add the placeholder or the `Entry` field until a real Run needs it — until then the precedence chain above is the whole of the design, and the safe default plus the marker is the whole of the implementation.
