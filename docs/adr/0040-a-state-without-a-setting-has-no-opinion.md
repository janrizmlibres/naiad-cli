# A State without a setting has no opinion

ADR 0026 refused a Workflow file where a State declares `model` and the file declares no file-level `model`. The reason it gave: a Model set in the Session is sticky, so absence would mean "whatever the previous State left behind". It called that an order-dependent surprise nobody chose, and made it unrepresentable.

The refusal charges the wrong person. An author who wants one expensive phase must also state a global for every other phase. The global is then the price of the annotation rather than a decision about the Workflow. A file wanting to say "this one State thinks harder, and leave the rest alone" cannot say it at all.

So absence stops being unrepresentable and becomes a meaning. A State that declares no `model` has no Model. Naiad types no Switch for it, and the State runs on what the Session holds — which stickiness makes the last value any State set. The file-level default stays, and stays optional. The order is the State's own key, then the file-level default, then absence. A file that declares a default has no State in the absence case, so every Workflow file valid today keeps its exact behaviour.

Nothing in the mechanism is new. `_switches` already drops a setting whose value is `None`, and `_parse_state` already falls back to `None` when neither the State nor the file declares the key. The whole change is the two refusal blocks deleted. The rule it generalises already existed too: a file naming neither key anywhere leaves the Session's settings alone. That stops being all-or-nothing over a file and becomes per State.

ADR 0026 was written before the Belief. That is what changed, and it is not that stickiness became safe — it did not. Naiad now knows what it last typed for each setting, and writes every Switch to the Run log (ADR 0039). So "whatever the previous State left behind" is a fact the log holds, rather than one a reader must replay the Run to recover.

## Considered options

**Inheriting down the file** — the parser carries the last declared value forward, so every State keeps an effective value — was the strongest alternative. It keeps ADR 0026's claim that a State's Model is readable from the file, and it keeps the Notify heal reaching every State. It was rejected for the order it invents. File order is not Run order at a Branching State: in `matt-pocock.toml`, `diagnose` sits above `grill`, so a Run through `grill` would take `diagnose`'s Model into the States below it. That is the order-dependent surprise ADR 0026 named, moved from the Run's path onto the file's and no easier to predict.

**Computing the value from the Run's actual path** produces the same Session settings as this ADR in every case, because typing nothing and typing what is already there are one thing to a sticky Session. It was rejected as machinery that buys no behaviour: Naiad would hold an opinion, record it, and type it, to reach where silence already reaches.

**Removing the file-level default entirely** is tidier, since stickiness carries a value down from the first State that declares one. It was rejected for what it does to files that exist. The parser ignores keys it does not know, so a removed default would go silent rather than be refused, and a Workflow would change price with nothing to read. Keeping the key costs one branch.

**Warning at parse** when one State declares a setting and another does not was rejected on sight. That shape is what this ADR exists to allow, so the warning would fire on every file it allows.

## Consequences

ADR 0026's claim that every State's effective Model is readable from the Workflow file now holds only for States that declare one. Nothing replaces it, because nothing needs to: a keyless State has no declared Model to read, and the log's last `switched` line before it says what was typed. Legibility moved rather than went, and ADR 0039 already moved it.

The Notify heal reaches declared settings only. `_switches` drops a `None` value before it tests the Belief, so a hand-off to a human re-types what a State declares and can re-type nothing for a State that declares nothing. A human who sets a Model at a Gate State therefore keeps it through every keyless State after it. That is the sticky behaviour this ADR chose, reaching one case further than the Workflow file does — and a State that wants its own Model still says so.

The Answerer is untouched. Its keys are its own, it never read the file-level default, and it carried no required-default rule, because a headless session starts clean each time. Absence has meant "pass no flag" there all along. The two now agree by design rather than by accident, though what no opinion resolves to still differs: the last State's Model in a Session, the platform's default in a headless invocation.

Effort changes identically, as it always has.

The new freedom has one trap, and it is worth naming because the shipped file walked into it. A setting declared on one State reaches only the Runs that walk through that State. An Entry may name the State it starts at, so a Workflow's first State in file order is not every Run's first State: `batches/marketing-hub-bugs.toml` enters `matt-pocock` at `diagnose`, and a pair declared on `classify` alone would leave those Runs on the platform's own setting with nothing in the file to say so. A file-level default has no such hole, because it reaches every State however a Run enters. That is why `matt-pocock.toml` keeps one — by choice now rather than by refusal, which is the whole of the change.
