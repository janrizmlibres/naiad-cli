# A Switch carries what the Session does not hold

> Amended by ADR 0040.

ADR 0026 had every delivery type the State's Model and Effort, "not only on change", and named that retyping as the mitigation for a Switch the terminal dropped. ADR 0038 then gave each Switch a Tick of its own, so the mitigation stopped being two keystroke lines and became four seconds and two slash commands ahead of every Prompt in the Run — most of them saying what the Session already held. A shipped Workflow whose States share one file-level pair pays that on every delivery and changes nothing by it.

So a Switch carries what the Session does not already hold. Naiad keeps a belief about the Session's settings — the last value it typed for each — and a State types a setting only where its own effective value differs. Compared per setting rather than over the pair, so a State that moves the Model and keeps the Effort spends one Tick and not two. Everything ADR 0026 declared stands: the State key over a required file-level default, the opacity, the Gate State typing nothing, and the Switch being best-effort rather than confirmed.

It is a belief and not a reading. Claude Code fires no hook on a Switch, and reading the session's state back is what ADR 0002 forbids, so the only evidence of what the Session holds is what Naiad put there. That evidence goes stale in exactly one way Naiad can see: a hand-off to a human. So **every Notify empties the belief**, and the next delivery types the State's settings again whether or not they changed. A Gate State is the hand-off Naiad plans for; a park, a Clear that looks dropped and an escalated Question are the others, and each ends with a human at the keyboard who may type a `/model` of their own.

The belief is read back out of the Run log rather than kept as a record of its own, the discipline `ended`, `opened` and `previous_state` already follow: every Switch and every Notify is written there, and one fact deserves one home. Kickoff now writes a `switched` line for each launch flag it passed, so a spawned Run and an adopted Run leave the same trace and a spawned Run's second State does not retype what the launch already set. An Announcement's own Switches are excluded from its belief, which is what holds the belief still while they are typed one to a Tick — counting them would shrink the sequence from under itself and deliver the Prompt with the second setting never typed.

## Considered options

**Keying it on `clear`** — a `clear = true` State types its settings and every other State reuses them — was the first shape proposed, and was rejected as unsound. A `/clear` discards the context and does not touch the Session's settings, so a Clear is no evidence at all about what the Session holds; and a non-clear State declaring a Model different from the State before it would then never get it, with nothing in the Workflow file to warn the reader.

**Setting the Session once, on the Run's first delivery, and never again** is cheaper than anything here. It was rejected because it deletes the premise of ADR 0026 rather than the cost of it: a grill and a review-fix would run at one price, and every per-State `model` key in every Workflow file would become dead weight.

**Re-arming on a Gate State alone** was rejected as the same rule stated too narrowly. A Gate is one hand-off among several, and the park case — where a human is most likely to go poking about in a session — is the one it would miss.

**Nothing re-arming it at all** — the belief being only ever what Naiad typed — is the simplest rule of the three and the one a reader can predict from the Workflow file with no replay of the Run's path. It was rejected because it leaves no heal whatever: a human who sets a Model at a Gate silently prices every State after it, and a dropped Switch is never retyped for the rest of the Run.

**Keeping the belief in `switches.json`**, beside the per-Announcement count already there, would be one file read instead of a log scan. It was rejected because the log already carries the fact, and a second home for it is a second thing to keep in step.

**Leaving kickoff alone**, so that a spawned Run's first delivery finds nothing typed and types both, costs about four seconds once per Run and touches neither `kickoff.py` nor `session.py`. It was rejected for what it says rather than what it costs: a log silent about flags Naiad did pass is a log that misreports the Session, and the belief is read from that log.

**Typing both settings whenever either changes** keeps the pair whole, as the glossary describes it, and always shows a State's full price on one line rather than a half a reader must complete from an earlier one. It was rejected because the filter it would replace already exists — `_switches` drops a setting the State does not declare — so comparing per setting is the same line, and it saves a Tick where a State raises the Effort and keeps the Model.

## Consequences

The self-heal ADR 0026 bought with the every-delivery retype is gone. A Switch the terminal swallows now mis-runs every later State that matches the stale belief, rather than one State — the failure ADR 0026 accepted knowingly, made to last longer. Two things hold it down. ADR 0038's Tick spacing is what makes a drop rare in the first place, and a Notify is the heal that remains: the Runs most exposed to a wrong Model are the long unattended ones, and those are the Runs that pass through Gates.

A Workflow file edited mid-Run behaves better than it did, and not worse: the library entry is an address rather than a copy (ADR 0037), so a changed default is read on the next tick, and it differs from the belief, so it is typed.

The log gains two lines at kickoff and loses most of the ones it had — which is the point, since a `switched` line now marks a State that actually changed something. Reading a State's effective Model out of the log alone means finding the last `switched` line before it; reading it out of the Workflow file, which is where ADR 0026 put it, still takes no replay at all.
