# review-fix runs only when a review completed; pull-request branches on the review, not its findings

> Superseded by commit d856840 (the shipped tail ends when the pull request is open).

The shipped tail always passed through `review-fix`. `pull-request` opened the pull request, waited for the Claude Code Review check, read its findings and announced its one successor; `review-fix` then Cleared, re-fetched the same findings, and — if there were none — announced `done` itself. On a host that runs no such review at all the pass was pure ceremony: a Clear and a turn to discover there was nothing to discover. And the "are there findings?" question was answered twice, once in a context that had just read them and again in a Cleared one that had to fetch them back.

We made `pull-request` a Branching State — `next = ["review-fix", "done"]` — that routes on whether an automated review *completed*, and read none of its content to decide. A review ran and its check finished within budget: announce `review-fix`. The host runs no such review, or it did not finish in the budget: announce `done`, because there is nothing to fix. `review-fix` is otherwise untouched: it still Clears, still fetches the raw review output, and still forms the whole verdict on what to address.

The criterion is content-blind on purpose. Which findings are real and which to exclude is `/fix-review`'s own work — it is the reviewer of the reviewer, reading each referenced file and throwing out what the review got wrong. For `pull-request` to route on whether findings are *actionable* it would have to do that validation first, which duplicates the skill and holds the same knowledge in two States (ADR 0010). "Did a review run" is not a judgment about the work — it is an observation `pull-request` makes first-hand, having just watched the check finish — so it can sit there. The judgment about the findings stays in the one place that reads the code to make it.

This also puts the decision where the knowledge already is. `pull-request` watched the review complete; that it completed is a fact it holds, where the old tail Cleared it away and had `review-fix` re-derive the weaker version of it. It is the same reason the implement loop chooses its next ticket in the context that has seen the tracker rather than the Cleared one that has not (ADR 0009). `review-fix` re-fetches the *content* because it Clears and because fetching from the pull request is `/fix-review`'s contract — that re-fetch is the skill's, not a second copy of the branch decision.

## Consequences

`review-fix` keeps its guard — "if the pull request carries no review findings, say so and announce `done`." The branch at `pull-request` is content-blind, so a review that ran but validated down to nothing, or came back all praise, still enters `review-fix`; the guard is where that resolves to `done`. One no-op Clear and turn in the clean case is the price, and it is the price the guard was kept to pay. Dropping the guard would leave `/fix-review` groping for findings that are not there, which is the failure it is most prone to.

`pull-request` names its two successors in the prompt rather than interpolating `{next_state}`, as the diagnosing and implement States already do and for the same reason: the placeholder renders every candidate as one joined phrase, useless where each exit carries a different condition — findings to the fix, their absence to the end. The shipped-workflow test asserts each declared candidate is announced by name, so a candidate renamed here without the prompt following it fails.

`done` is now reachable directly from `pull-request`, not only through `review-fix`. It stays terminal and promptless; the Run ends there whether the review was skipped, empty, or fixed.
