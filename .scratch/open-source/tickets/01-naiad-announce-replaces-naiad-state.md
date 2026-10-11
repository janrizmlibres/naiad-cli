# 01 — `naiad announce` replaces `naiad state STATE`

Status: resolved
Mode: AFK
Blocked by: None — can start immediately
Spec: [PRD](../PRD.md), "The verb surface"

**What to build:** The agent announces a State with `naiad announce STATE [--subject S]`. Every place Naiad teaches or reminds the agent of the verb names the new one: the Protocol, the Nudges, the Wait-expiry reminders, the Compaction reminder, the rejection of an unknown State, and the adopt skill. They all share one constant. `naiad state` becomes free for the authoring noun, and no alias is kept for `naiad state <name>`.

Prefactor in the same ticket: the argparse tree is built by its own function rather than inside `main()`. `main()` builds the parser there, parses, and dispatches. The authoring nouns (tickets 10–12) and the docs drift test (ticket 16) both need a parser they can build without running a command.

- [x] `naiad announce <state>` announces exactly as `naiad state <state>` did, with the same replies, refusals and exit codes.
- [x] `naiad state <name>` is no longer a Protocol verb.
- [x] The Protocol text, nudges, wait reminders, Compaction reminder and adopt skill all name `naiad announce`, and their tests say so.
- [x] The parser is obtainable from a function without executing a handler, and `main()` uses it.
- [x] Built test-first (Red → Green → Refactor), with the Refactor candidates and verdict recorded in the ticket.

## Refactor

Candidates considered, with verdicts:

- Route the other verbs (`ask`, `wait`, `hold`, `branch`) through their own `*_SUBCOMMAND` constants in `main.py` and the refusals: keep. It is outside this ticket, and only `announce` was renamed.
- The refusals in `announce.py` and `wait.py` build `naiad announce <name>` with a bare `naiad`, where the Protocol uses the absolute path: keep. That is old behaviour and the wording is unchanged.
- One spelling for the placeholder, `{announce}` as a whole command in the Protocol and as the bare verb in the adopt skill: keep. The skill already formats `{naiad}` separately for every other verb it names.
- The parser test and the subprocess test both prove `state` is refused: keep both. One reads the tree without a Run, the other runs the real entrance and checks no Announcement is written.
- The `states` comment in `main.py` warned it sat one letter from the old Protocol verb: removed, now false.
- The unknown-State refusal and the Compaction reminder never named the verb, and still do not. The Protocol they arrive with does, and their wording is unchanged.
