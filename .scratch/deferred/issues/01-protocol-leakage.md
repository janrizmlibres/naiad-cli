# Protocol leakage: skills ask interactively despite the Protocol

Status: needs-info
Trigger: any unattended Run where the agent asked via `AskUserQuestion` instead of `naiad ask`

## The risk

The design requires the agent to announce Questions through `naiad ask` rather than asking the human directly (ADR 0002 — Naiad reads no Claude Code internals, so a Question it cannot see does not exist).

But this is a Protocol convention competing with a skill's own instructions. `grilling` in particular is built around asking one question at a time via `AskUserQuestion`, and other skills have the same instinct. The `SessionStart` injection re-asserts the Protocol on every fresh context, which is the strongest available lever — but it is still one instruction arguing with another.

When it leaks, the failure is quiet and expensive: the agent blocks on a dialog nobody will answer, no Announcement is made, Naiad Nudges twice, gives up, and notifies. An overnight Run dies having done nothing since the leak.

## Why it is deferred

The leak rate is unknown and unmeasurable without real Runs. Building a defence first risks solving a problem that does not occur, and the fallback below is additive — it can be dropped in later without disturbing anything decided so far.

## The known fallback

Intercept the tool rather than instruct against it: a `PreToolUse` hook on `AskUserQuestion` denies the call and returns the Answerer's response as the deny reason, which the model reads and acts on. This needs no cooperation from the agent and works with unmodified skills.

Two caveats to check before relying on it: using a deny reason as an answer channel is not a documented use and may not survive a release, and it catches only tool-call questions — a skill that asks in prose still slips through.

## What to capture in the meantime

Log every Run that ends in notify-after-Nudge along with what the agent was doing, so the leak rate is a number rather than an impression when this is picked up.
