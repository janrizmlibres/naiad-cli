# Contributing

Open an issue before a non-trivial pull request, so the change is agreed before the work is done. A typo or a one-line fix needs no issue.

Write the test first and see it fail for the reason you expect, then make it pass. A pull request lands with its tests, and with the suite and the type check passing.

Contributions are accepted under the MIT license, and under 0BSD for Workflow files. There is no contributor license agreement.

## Development setup

```
uv sync
uv run pytest
uv run mypy naiad
```

The tests cover the decision core, the queue, the runtime, the hooks and the shipped Workflows' invariants.

The tmux and Claude adapters are not covered by tests. A change to either needs a manual Run of the starter against a real repository, on a throwaway repository, before it is proposed.

## Layout

```
naiad/domain     pure decisions: transitions, prompts, questions, supervision
naiad/runtime    runs, the queue, announcements, answers, the tick loop
naiad/adapters   tmux, the answerer, notifications, locks, executables
naiad/cli        the operator's and the agent's commands
naiad/hooks      installing the Stop, SessionStart and UserPromptSubmit hooks
naiad/skills     the naiad-adopt skill
naiad/workflows  the starter Workflow, packaged with the wheel
workflows/       Workflow files run from a checkout
```

## Documentation

Every `naiad` command shown in a fenced code block of `README.md`, this file or `docs/*.md` is parsed against the real command tree by `tests/test_docs_drift.py`, so renaming a verb fails the suite until the documents follow. Prose is not tested.
