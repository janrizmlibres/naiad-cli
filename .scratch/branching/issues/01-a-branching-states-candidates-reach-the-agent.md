# A Branching State's candidates reach the agent

Status: ready-for-agent
Blocked by: None — can start immediately
Spec: `.scratch/branching/PRD.md`

## What to build

A State may declare its candidate successors instead of inheriting the next one in the declared order, and everything that depends on knowing what comes next has to stop assuming there is exactly one answer.

**The resolver.** What the agent may announce next becomes a set that usually happens to have one member. A Branching State resolves to its declared candidates verbatim; a State without them resolves to the single successor the declared order supplies; a State with nothing after it resolves to empty. One resolver with a plural return rather than a singular and a plural accessor side by side — the module exists so that ordering has a single source of truth, and two accessors would drift, with a future caller reaching for the singular one and silently dropping a branch.

**The delivered Prompt.** The successor interpolated into a Prompt becomes the candidates rendered together, so a Branching State's Prompt reads as naming both exits. The Workflow supplies the names; the Prompt's own text supplies the criterion for choosing between them. Nothing in Naiad decides which branch is right.

**The Protocol.** Its expectation line goes plural. This is the one that matters most: naming a single candidate at a fork would bias the agent toward whichever the Workflow author happened to list first, in precisely the case where the agent's judgment is the whole point (ADR 0001). It is also all a Cleared agent standing at a fork has to go on.

**Deviation.** An Announcement naming any declared candidate is on the path and is not a Deviation — choosing correctly at a fork must not be recorded as a mistake. Anything outside the candidates is still delivered, because a human may have redirected the agent and refusing would deadlock exactly that intervention, but it is recorded as before.

**The Run log.** The recorded expectation stays a single string, rendered by joining the candidates. It is a human-readable diagnostic, the deviations query only tests whether it is present, and changing the persisted shape would strand existing Run logs for no gain. A deliberate inconsistency — plural in the domain, joined for the record — worth a comment where it happens.

Nothing about the shipped Workflow changes in this ticket. The work is verifiable against a Workflow fixture that declares candidates, and the shipped Workflow must go on behaving exactly as it does today.

## Acceptance criteria

- [x] Red → Green → Refactor throughout, with the Refactor step named and a verdict recorded even when the verdict is to keep as-is. The candidate already anticipated: whether the declared-order walk and the candidate lookup collapse into one resolver
- [x] A State declaring candidates resolves to all of them; a State without them resolves to its declared-order successor; a State with nothing after it resolves to empty
- [x] A Prompt delivered from a Branching State names every candidate
- [x] The Protocol injected into a fresh context names every candidate, phrased as a choice rather than an instruction
- [x] Announcing any declared candidate is not recorded as a Deviation
- [x] Announcing a State outside the candidates is still delivered, and is recorded as a Deviation
- [x] A Deviation's recorded expectation is a single joined string, and existing Run logs still parse
- [x] A Workflow declaring a candidate that names an undeclared State is still rejected before a Run exists
- [x] The shipped Workflow's behaviour is unchanged — its existing assertions pass untouched

## Refactor verdicts

**The anticipated candidate — do the declared-order walk and the candidate lookup collapse into one resolver?** Verdict: they are already one function with one plural return, and the two arms stay. A uniform shape would mean treating an implicit successor as a computed candidate list, but gate-skipping applies to the declared-order arm alone (ADR 0007), so the branch would move rather than disappear — and it would move somewhere less obvious than the `if state.next_candidates` it currently sits behind. Keep.

**The candidate rendering was about to be duplicated three ways.** The Prompt, the Protocol and the Run log all speak a set of candidate names, and each was going to join it by hand — the drift this ticket exists to prevent, one level down. Extracted to `render_candidates` in `naiad.domain.prompt`; the Protocol imports it so a fork cannot read one way in a Prompt and another after a Clear. Applied.

**`Entry.expected` staying a single joined string.** Verdict: keep, as the spec asks. Commented at both the field and the two places that join, since it is a deliberate inconsistency with a domain that is plural throughout.

**Naming: `next_state` → `next_states` rather than an added plural accessor.** Verdict: rename, no alias left behind. An alias is exactly the singular accessor a future caller would reach for and silently drop a branch through.

**The resolver returned `State` objects, and all four callers unwrapped them to names.** Found by review. Verdict: return names. A successor is only ever spoken — interpolated into a Prompt, named in the Protocol, compared against what the agent announced — so nothing asked a returned `State` anything, and the identical `tuple(s.name for s in …)` in `decide`, `kickoff`, `cli.protocol` and the shipped-Workflow test was four copies of one unwrapping. It also deleted the resolver's one unreachable branch: a candidate list is already names, so the defensive lookup that could in principle have dropped an unknown candidate is gone rather than commented. Applied.

**The Protocol's expectation stayed three sentences rather than going uniformly plural.** The PRD asks for "announce one of: …"; a single-successor State keeps the existing "announce: spec". Verdict: keep the split, now commented where it branches. Offering a choice where the Workflow gives one exit invites the agent to hunt for an alternative it was never given, and the ticket's criterion — phrased as a choice — is about the fork.

**`render_candidates` renders three or more candidates, which no Workflow has.** Verdict: keep. It is the natural form of the join rather than added machinery, and a two-case join that produced "a, b" for three would be a latent bug in the first Workflow that grew a third branch.
