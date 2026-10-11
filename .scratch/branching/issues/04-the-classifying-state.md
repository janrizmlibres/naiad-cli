# The classifying State

Status: ready-for-agent
Blocked by: 03-the-bug-branch
Spec: `.scratch/branching/PRD.md`

## What to build

Kickoff with nothing said about where to start. The operator describes the task in their own words, and the agent decides which kind of work it is.

**Classification is a State.** It becomes the first State of the Workflow rather than something Naiad owns (ADR 0005). Its Prompt reads the task, looks at the codebase as far as it needs to, and announces the head of the appropriate Branch — exactly as any other State announces its successor. Because it is an ordinary State it runs in the Run's own interactive session with full access to the repository, rather than as a headless call made before any session exists.

Its Prompt is plain prose and runs no skill. No existing skill fits, and one whose entire body is three sentences would be indirection rather than encapsulation; the classification criterion exists nowhere else, so putting it in the Prompt creates no second copy of anything. This makes it the first Prompt that does not open with a slash command, so the Workflow file's comment asserting that convention needs amending — the convention's real reason is mechanical, that a slash command is only read at the start of a message, not a requirement that every State run a skill.

It writes no Artifact. Its Announcement is the record, the Run log already holds it, and both branch heads Clear anyway.

**The branch heads Clear.** Both the grilling State and the diagnosing State Clear and interpolate the task themselves, so the classifier's reading of the task never reaches them. This matters most for diagnosis, whose job is to form a hypothesis from evidence rather than inherit a guess — an agent that begins by agreeing with the classifier is the failure this branch is most likely to have. It is safe by construction rather than by luck: the only thing that must cross the boundary is the task, and Naiad holds that itself and interpolates it into every delivered Prompt rather than only the first.

**The escape hatch.** An operator who already knows what kind of work they have starts the Run at a branch head and skips classification entirely, which needs no code — the start-state option already accepts any declared State name. It needs saying out loud, in the Workflow file beside the classifying State, because it is the answer to "the classifier can be wrong" and nobody will find it otherwise.

## Acceptance criteria

- [x] Red → Green → Refactor throughout, with the Refactor step named and a verdict recorded even when the verdict is to keep as-is
- [x] The shipped Workflow's first State is the classifying State, and its candidates are the two branch heads
- [x] Its Prompt carries the task, runs no skill, and states the criterion for choosing a Branch
- [x] It declares no Clear and writes no Artifact
- [x] Both branch heads Clear, and both carry the task in their own Prompts
- [x] Kickoff with no start State named delivers the classifying State's Prompt with the task in it
- [x] Kickoff at either branch head still works and skips classification
- [x] Announcing either branch head from the classifying State is not recorded as a Deviation
- [x] The Workflow file's comment about Prompts opening with a slash command is amended, and the start-state escape hatch is recorded beside the classifying State
- [x] The whole Workflow still parses and every State's successor is asserted, branch and tail alike

## Refactor verdicts

**No production code changed again.** `naiad/` is untouched for the second ticket running; the classifier is expressed entirely in the Workflow file, which is what ADR 0005 predicted when it said a Workflow that can already send the agent to any of its States can express a branch without Naiad learning anything.

**The task assertion iterated the wrong table.** `test_only_the_branch_heads_are_told_the_task` ranged over `SKILLS`, and the classifying State runs no skill — so it would have kept passing while asserting nothing whatever about the new State's Prompt. Verdict: introduce `DELIVERING` (every State with a Prompt, skill or not), range over that, and rename to `test_only_the_classifier_and_the_branch_heads_are_told_the_task`. `test_each_prompt_names_the_state_to_announce_next` had the same defect and got the same fix.

**`DELIVERING` derived rather than written out.** `["classify", *sorted(SKILLS)]` instead of a fifth literal table. Verdict: derive, but pair it with `test_every_state_that_delivers_a_prompt_is_accounted_for` — the danger of splitting delivering States across two tables is a State added to the file that lands in neither, and nothing else would have noticed.

**The comment amendment, made testable.** The header comment asserted a universal convention that the classifier now breaks, and the temptation was to weaken it to prose and assert nothing. Verdict: invert it into `test_only_the_states_that_run_a_skill_open_with_a_slash_command`. The convention's real content — mechanical, and about skills rather than about States — is now an assertion over the whole file rather than a claim in a comment, and a future skill-less Prompt that opens with a stray slash fails.

**`TOLD_THE_TASK` kept separate from `BRANCH_HEADS`** even though one is the other plus `classify`. Verdict: keep. They answer different questions — where a Run may be started, and which Prompts carry the task — and collapsing them would tie the escape hatch's parametrization to a Clearing decision it has nothing to do with.

**The Deviation test was vacuous as first written.** `deviation(announced=head, previous_state="classify") == ()` passes just as well against a Workflow that has never heard of `classify`, because an empty expectation is also reported as no Deviation — it was green before the State existed. Verdict: assert the off-path case beside it, so the test fails unless the fork is real.

**Stale docstrings, from this ticket and the last.** The module docstring still called the file "the Matt Pocock feature chain"; `test_each_state_that_declares_candidates_declares_the_right_ones` still said "only one of these branches", now two of three; and the smoke document's list of Clearing States never gained `diagnose` when ticket 03 added it. All corrected.

**The grilling State did not Clear, and the box saying it did was ticked. Found by review, on the Spec axis.** This is the ticket's central safety property and it was half-built: `diagnose` Clears, `grill` did not, so a classifier's "this is a feature because…" would have survived straight into the interview that exists to ask that question from scratch. It went unnoticed because `test_the_implement_loop_clears_and_the_design_phases_do_not` actively pinned the old set, so the suite asserted the bug. Fixed, and the assertion is now two: the Clearing set as a whole, and `test_each_branch_head_clears_and_so_restates_the_task` parametrized over both heads, which ties the Clear to the restatement that pays for it rather than leaving them asserted in different places. Every claim in this section that rested on "both branch heads Clear" was true of one State when written.

**The classifier's branch choice is not unit-tested, and the smoke item for it was reverted. Found by review, on the Spec axis.** The PRD's Testing Decisions send the question to manual smoke, and I read that as an instruction to write the item now. Out of Scope says the opposite and is the more specific of the two: *"It records observed behaviour of a real agent, so it is written after the code lands and a Run has actually been driven through both branches — not as a prediction alongside the implementation."* Verdict: revert. What survives in `docs/smoke/matt-pocock.md` is one word — `diagnose` added to its list of Clearing States, which ticket 03 left stale and which is a correction rather than a prediction.

**Two assertions that were green for the wrong reason. Found by review, on the Standards axis.** `assert "bug" in prompt` and `assert "feature" in prompt` pass on a Prompt with the two branches swapped, which is the one way this Prompt can be wrong while looking right; it is now parametrized per branch and asserts the kind and the Announcement in the same sentence. And `deviation(...) == ("grill", "diagnose")` restated a literal the `CANDIDATES` table already owns, so renaming a candidate would have failed in the table's test and passed here.

**Not done: a glossary entry for the classifying State.** Raised by review as a possible gap. Verdict: no entry. CONTEXT.md already carries **Branching State**, and this is one; the PRD is explicit that *"the names `classify`, `diagnose` and `no-repro` are one Workflow's language and appear nowhere in the glossary or the engine."* An entry would put one Workflow's vocabulary into Naiad's.

**Not done: the ticket's `Status:` line left at `ready-for-agent`.** Also raised by review. The five labels in `docs/agents/triage-labels.md` have no completed state, and ticket 03 shipped complete with the same line. Verdict: leave it, and take it up as a tracker question rather than inventing a sixth label mid-ticket.
