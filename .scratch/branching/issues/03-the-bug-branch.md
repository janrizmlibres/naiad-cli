# The bug branch

Status: ready-for-agent
Blocked by: 01-a-branching-states-candidates-reach-the-agent, 02-a-branch-candidate-gate-state-survives-gate-skipping
Spec: `.scratch/branching/PRD.md`

## What to build

The first Branch in the shipped Workflow. An operator with a bug starts a Run at the diagnosing State, and the bug is diagnosed and fixed end to end, rejoining the existing tail at the pull request. Both kinds of work then finish the same way.

**One State, not two.** The diagnosing State runs the existing diagnosis skill in full — build a tight pass/fail signal, reproduce, minimise, hypothesise, instrument, fix with a regression test, clean up and post-mortem — and announces the shared tail. There is no separate fixing State and no diagnosis Artifact. The alternative was argued for at length before the skill was read and rejected on evidence: the fix phase already writes its regression test before the fix and then re-runs the original feedback loop, and the post-mortem is explicitly better-informed after the fix than before it, so splitting severs a discipline mid-stride and then reconstructs by hand, in an Artifact, what not Clearing supplies for free. The review that would have justified the split is not wanted either — on the path where the hypothesis is confirmed there is no decision for a human to make. ADR 0008 holds the full argument, including what the Artifact would have had to carry if the split is ever revisited.

**The fork that is wanted.** The diagnosis skill instructs the agent to stop and report when it cannot build a feedback loop at all, and not to hypothesise without one. That becomes the branch's second candidate: a Gate State with no Prompt and no Artifact. The findings are already in the session verbatim, which is where whoever reads them is looking, so writing them to a file would be transcription rather than communication. The operator supplies the missing environment, steps, or captured artifact by typing into the session directly, and the agent carries on through the remaining phases in the same context before announcing the shared tail.

Because this Gate State is a branch candidate, the previous ticket's rule keeps it reachable in an unattended Run: a Run that cannot reproduce a bug stops and notifies rather than being told to open a pull request.

**Where it goes in the file.** The bug branch's States are declared before the feature chain, in the order a Run moves through them, so the file reads top to bottom. Three declarations of candidates appear across this ticket and the next; here, the diagnosing State names the Gate State and the pull request, and the Gate State names the pull request. Every other successor in the Workflow stays implicit, so the entire existing feature chain is untouched — that it remains untouched is itself worth asserting.

The diagnosing State Clears and restates the task, which costs nothing now and is what makes the next ticket's classifier safe to put in front of it.

## Acceptance criteria

- [x] Red → Green → Refactor throughout, with the Refactor step named and a verdict recorded even when the verdict is to keep as-is
- [x] The shipped Workflow declares a diagnosing State, a no-reproduction Gate State, and no separate fixing State
- [x] The diagnosing State's candidates are the no-reproduction Gate State and the pull request; the Gate State's successor is the pull request
- [x] The diagnosing State's Prompt invokes the diagnosis skill and states the criterion for choosing between its two candidates
- [x] The diagnosing State Clears and its Prompt carries the task
- [x] The no-reproduction State has no Prompt, so Naiad delivers nothing and the operator types into the session
- [x] Starting a Run at the diagnosing State produces the right initial Prompt, with the task in it
- [x] Under a Run resolving with Gates skipped, the no-reproduction State is still offered as a candidate while the feature branch's review Gate is still skipped
- [x] Every State in the existing feature chain keeps the successor it has today, asserted rather than assumed
- [x] Prompts read as delivered rather than as templates, as the shipped Workflow's existing assertions require

## Refactor verdicts

**No production code changed, so the refactor question is entirely about the test.** The branch is expressed in the Workflow file; `naiad/` is untouched, which is the evidence that tickets 01 and 02 built the mechanism this one only uses.

**The successor assertion weakened to accommodate the fork.** Generalising `(successor,) = next_states(...)` to a loop, the obvious move was to drop from `assert f"announce {successor}" in prompt` to a bare substring check for each candidate name — which would have passed on a Prompt that mentioned `no-repro` in prose and told the agent to announce only `pull-request`. Verdict: restore the strong form inside the loop. The diagnosing Prompt names both exits as announcements, so nothing had to be given up, and the weaker assertion would have silently permitted the one failure the fork exists to prevent — a Prompt deciding the branch in the least visible place.

**A global assertion parametrized per-State.** `test_only_the_forking_states_declare_candidates` checked one State's candidates *and* the whole file's set of forking States, so the second half ran twice and would have reported against whichever parametrization failed first. Verdict: split into `test_each_forking_state_declares_the_candidates_it_should` and `test_nothing_outside_the_bug_branch_declares_candidates`. Two questions, two failures.

**Four module-level tables in the test (`SKILLS`, `CANDIDATES`, `FEATURE_CHAIN`, `BRANCH_HEADS`).** Verdict: keep. Each drives a different parametrized question, and `FEATURE_CHAIN` in particular earns its place by making "unchanged" an assertion over every edge rather than a claim in a docstring. Collapsing them into one table of States would mean a row of mostly-empty columns and a test that reads by indexing rather than by name.

**The weak assertion survived in a second place — found by review, both axes independently.** The verdict above was applied in `test_each_prompt_names_the_state_to_announce_next` but not in the kickoff test, which still checked `successor in prompt`. So the verdict as first written overstated what the diff did. Applied properly this time, and the two kickoff tests now share a `kickoff` helper rather than repeating the eight-argument `start_run` call.

**The shipped file's default start State was asserted nowhere.** Found by review. Replacing the old kickoff test with one parametrized over both heads meant every case passed `start_state`, so nothing pinned what an operator who names nothing gets — and `test_transitions.py` asserts `grill` against a fixture, which would have read as false comfort. Added `test_a_run_started_with_no_state_named_begins_at_the_first_declared_one`, asserting the diagnosing State against the shipped file. The next ticket's classifier will change that line, which is the point of having it.

**Terminology drift, found by review.** "Execution order" for what the repo and ADR 0007 call the **declared order** — and untrue besides, since no Run walks `diagnose → no-repro → grill`. And "fork" as a type noun where CONTEXT.md's **Branching State** entry lists `_Avoid_: Fork`; the test is now `test_each_state_that_declares_candidates_declares_the_right_ones`, which is also honest about `no-repro`, a State that declares a candidate and branches nowhere. Fixed. "The second Gate State" in the TOML was simply wrong — ADR 0008's qualifier, *the first Gate State that is a branch candidate*, is the load-bearing part and I had dropped it.

**One sentence in three places.** Found by review: ADR 0008's "the findings are already there verbatim, which is where whoever reads them is looking" had been copied into the TOML comment and a test docstring. Verdict: cite the ADR from the TOML, drop it from the docstring. The argument lives in one place and the code points at it.

**The diagnosing Prompt names its candidates by hand rather than interpolating `{next_state}`.** Verdict: keep, now commented. `{next_state}` renders every candidate as one joined phrase — right for "announce what comes next", useless where each exit carries a different condition, which is the whole content of this fork. Prior art is the implement loop, which writes its own name for a comparable reason. The names stay the Workflow's in the way that matters: the successor test asserts each declared candidate is announced by name, so renaming a candidate without following it here fails.

**The two Gate States asserted in one test.** `test_an_unattended_run_tells_the_two_kinds_of_gate_state_apart` covers `review` and `no-repro` together rather than in two tests. Verdict: keep as one, as the previous ticket's criterion asks — the distinction is the behaviour, and separated they could drift into agreeing with each other.

## Note for the next ticket

The first declared State is now `diagnose`, so a Run started with no `--start-state` begins at the diagnosing State rather than at the grilling one. That is the declared order this ticket asks for, and the next ticket's classifier goes in front of it and restores a sensible default. Until then, an operator starting a feature Run names `grill` explicitly — which the shipped-Workflow test now exercises for both branch heads.
