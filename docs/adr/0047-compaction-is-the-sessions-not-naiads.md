# Compaction is the Session's, not Naiad's

A single `implement` iteration on a 1M-window Model grows past 200K tokens with nothing stopping it, because Claude Code compacts a 1M session at about 967K by default. Past 200K the agent's quality drops and every turn re-sends the whole context, and Naiad had no way to do anything about it: it confirms Clears between States and types Switches ahead of Prompts, but a State's context mid-phase was nobody's.

The design first proposed was Naiad's: read the context usage, tell the agent to yield its turn when it crossed the line, type `/compact` into the quiet session, confirm it landed, and send the agent back to work. We decided instead that Naiad passes the point at launch — `autocompact = "200k"` in the Workflow file, `--autocompact` on the kickoff line — and does nothing else. Claude Code measures, compacts mid-turn without asking the agent to stop, and reports the Compaction through the `SessionStart` hook Naiad already installs, which re-teaches the Protocol and now adds a line saying which State and Subject the agent stands in.

## Why not Naiad's

Nothing Naiad is coupled to can see the context. No hook carries token counts — Stop, SessionStart and PreCompact hand over session and transcript identifiers and no more — and the one surface that does, the statusline, would be a fourth coupling under ADR 0002, installed over whatever statusline the operator already runs. Reading the transcript is what ADR 0002 forbids.

Nothing Naiad types can compact a working session. Whether a `/compact` typed mid-turn is processed is undocumented, so the handshake needed a first verb running the other way — Naiad asking the agent to end its turn, with a resume message after — and every Protocol verb so far runs agent to Naiad. Auto-compaction needs no such thing: it fires between the agent's own steps, and the agent never has to be told.

And the Session already does the whole job. `autoCompactWindow` is documented as the point at which compaction happens, separate from the window itself: the Model keeps its 1M and compacts at 200K. Rebuilding that in Naiad would be new machinery — a reading, a verb, a typed slash command with the retry shape of ADR 0019 — standing in for one launch flag.

## What Naiad keeps

The point is a file-level key and nothing per State, because it is a property of the Session — set once at launch — where Model and Effort are properties of a phase. Opaque, as the Model is (ADR 0026): the value is handed to the flag verbatim and the Session judges it. Absent means no opinion and no flag, so a Workflow that never asked runs exactly as before (ADR 0040). A flag rather than the environment variable, which is documented to outrank a setting the operator chose on purpose.

The Run log gains a `launched` line naming the point, and a `compacted` line each time the hook reports one — the diagnostic that lets "it produced something strange overnight" be read against "its context was summarised three times during implement". Not a `switched` line: that feeds the Switch belief, and a value no State ever compares against would be a line lying about what it is for. The belief itself is untouched by a Compaction, for the reason ADR 0039 refused to key it on `clear`: a summary discards conversation and leaves the Session's settings where they were.

The injection on `source: "compact"` adds one sentence the other sources do not get — the State and Subject from the latest Announcement, or from the Opening where an Adoption has announced nothing yet, and the text of a Question still unanswered, so that an agent whose summary lost its own Question does not ask it again into a refusal. A Clear-shaped injection alone, "when this phase is done announce X", invites a fresh start on a half-done ticket, which is the Clear failure in different clothes.

## Considered options

**Clear and re-deliver** at the line, reusing ADR 0019's confirmed handshake. Rejected because ADR 0003's premise — Artifacts carry the meaning, so a State can be Cleared — holds between States and not within one: a half-done ticket's progress lives in the conversation, and a re-delivered `/implement` starts it over.

**A statusline hook** as the reading, with the Yield-and-`/compact` handshake on top. Credible, and the only way to get a number Naiad could hold a rule over. Rejected as above: a fourth surface bought for a rule the Session already enforces, resting on an undocumented mid-turn behaviour.

**A `PreCompact` hook** to record whether a Compaction was automatic or a human's `/compact` at a Gate. Rejected because the distinction changes no decision — for the diagnostic both are the context summarised at this point in the Run — and a third hook is not worth a fact nothing reads.

**An Adoption typing `/autocompact`** into the Session it joins. Rejected: the Session is the human's, the value is a Switch with no belief to compare against, and the adopt skill can tell them what the Workflow wants.

## Consequences

The Answerer session is untouched; it is not the one growing past 200K, and one number per Workflow file is enough until it is.

No automated test can see a Compaction happen, for the reason ADR 0038 gave: the fake terminal takes every send. The tests hold the invariants — the key parsed, absence passing no flag, the `compacted` line written when the hook says `compact`, the reminder naming State and Subject — and never the number (ADR 0043). The smoke criteria gain a line: a `compacted` entry in the Run log of a long `implement`, with the agent carrying on the same ticket after it.

A Compaction is a summary, and a summary can lose what the agent was holding. The reminder covers the three things Naiad knows — State, Subject, open Question — and nothing else; what the phase had in its head beyond those is the skill's to have written down, which is the constraint ADR 0003 already places on a Clear, now applying within a State as well.
