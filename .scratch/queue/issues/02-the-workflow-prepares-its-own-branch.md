# The Workflow prepares its own branch

Status: ready-for-agent
Blocked by: 01-a-run-carries-a-working-branch-and-a-predecessor
Spec: `.scratch/queue/PRD.md`

## What to build

A Run puts itself on its own branch before it writes anything, and opens its pull request against the right base. No Naiad code changes — this is Prompt prose in the shipped Workflow, and it is where the git knowledge lives (ADR 0015).

**Where it goes: the two branch heads, not a State of its own.** A dedicated first State would be skipped by exactly the Entries that pre-classify, which are most of them — a design Run starts at `grill` and a bug Run at `diagnose`, and both would step straight over it. The classifying State writes nothing and needs no branch. Both heads Clear, and a checked-out branch is git state that survives a Clear, so putting the paragraph at each head covers all three entrances. The cost is one paragraph written twice, which this file already accepts twice over for the same kind of reason.

**What the paragraph says.** Check out `{branch}`, creating it if it does not exist. Base it on `{predecessor}` when that branch is set and is *not* already an ancestor of the repository's base branch; base it on the base branch otherwise, and when no Predecessor was given at all.

**The test is ancestry, not merge status.** `git merge-base --is-ancestor` asks one question with a terminal answer, needs no API call and works offline. Merge status is a taxonomy — open, closed, merged, closed-unmerged — that has to be enumerated correctly to be safe, and it answers wrongly for the case that matters most here: a Run parked at `handover` has commits and no pull request at all, so "not merged" would send the next Run to the base branch and drop that work from underneath it.

**It must be safe to repeat.** A resumed or re-entered Run finds the branch already there and must check it out rather than fail on it.

**The pull request re-applies the test.** The Predecessor may have landed during the Run — a stack of Entries is exactly the case where that happens — so the State that opens the pull request asks the ancestry question again rather than trusting what was true at the start, and passes the result as the base. The pull request skill already accepts an explicit base for stacked work and defaults to the repository's base branch otherwise, so it needs telling and nothing more; its own logic stays its own.

**Known hole, accepted rather than solved.** A Predecessor whose pull request was closed without merging is not an ancestor, so the next Run stands on abandoned commits. The pinned base is the answer when it happens, and it is rare enough that a human is there.

This is Prompt prose, so it is unverified until it runs — ADR 0006 already records that the behaviour of a real agent under a Prompt is a prediction until a smoke run says otherwise. Extend the smoke document accordingly.

## Acceptance criteria

- [ ] Red → Green → Refactor throughout, with the Refactor step named and a verdict recorded even when the verdict is to keep as-is
- [ ] Both branch heads instruct the agent to check out the Working branch, creating it if absent
- [ ] The base is the Predecessor when it is not an ancestor of the base branch, and the base branch when it is or when no Predecessor was given
- [ ] The instruction is idempotent — a Run re-entering a State whose branch exists checks it out rather than failing
- [ ] The State that opens the pull request re-applies the ancestry test and passes the result as the base
- [ ] The classifying State is unchanged and still writes nothing
- [ ] The Workflow still parses and every existing assertion about it still holds
- [ ] The smoke document covers a Run started with a pinned base, on a branch that does not exist yet
