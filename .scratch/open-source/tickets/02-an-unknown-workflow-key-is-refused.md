# 02 — An unknown Workflow key is refused

Status: resolved
Mode: AFK
Blocked by: None — can start immediately
Spec: [PRD](../PRD.md), "The Workflow loader"; map ticket [16](../issues/16-an-unknown-workflow-key-is-refused.md)

**What to build:** A Workflow file carrying a key Naiad does not know fails to load instead of loading as if the key were absent. `questons = "human"` is refused, not silently ignored. The refusal names the key, where it sits (the file, the named State, or `[answerer]`), and the keys allowed there. Every caller goes through the one load path, so `queue add`, `run`, the Supervisor and later `workflow check` refuse alike. There is no version key.

Allowed keys:
- top level: `name`, `model`, `effort`, `autocompact`, `answerer`, `states`;
- a State: `name`, `prompt`, `clear`, `terminal`, `next`, `model`, `effort`, `questions` (plus `report` once ticket 06 lands);
- `[answerer]`: `model`, `effort`, `fallback`.

- [ ] An unknown key at each of the three levels is refused with the key, its place, and the allowed list.
- [ ] `naiad queue add` with such a file refuses with that sentence, not a traceback.
- [ ] Both `workflows/matt-pocock.toml` and the starter draft load unchanged.
- [ ] Built test-first, Refactor verdict recorded.
