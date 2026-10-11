# Naiad never reads Claude Code internals

Naiad v1 learned what the agent was doing by scraping the terminal UI, and the resulting code was both large and fragile — the UI it depended on can change in any release. Session transcripts look like a tidier replacement, but they are documented as internal, format-unstable, and explicitly not to be parsed.

So Naiad reads neither. Everything Naiad needs to know, the agent tells it through the Protocol — including its Questions, which is why a Question carries its own text and options rather than being lifted out of the conversation. Naiad's entire coupling to Claude Code is therefore three supported surfaces: sending keys to a terminal session, a hook that reports a turn has ended, and a hook that injects the Protocol into a fresh context.

## Consequences

The agent must be told not to ask its questions the natural way, which fights the instincts of skills that ask interactively. This is a real cost and the place the design is most likely to leak in practice. We accept it: a leak is visible and recoverable, whereas a dependency on an unstable internal fails silently and at the worst possible moment.
