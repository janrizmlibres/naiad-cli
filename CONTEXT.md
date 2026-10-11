# Naiad

Runs a multi-phase Claude Code workflow to completion without a human driving each step.

## Language

**Workflow**:
An ordered list of States describing one end-to-end piece of work. Defined in a file Naiad reads; swapping the file swaps the workflow, so Naiad itself knows nothing about any particular workflow's meaning.
_Avoid_: Pipeline, chain, flow

**Workflow library**:
The one machine-wide directory of Workflow files addressable by bare name, where a name is the file's stem. A name is entrance-side shorthand for the file it resolves to: the argument's shape alone — bare name or path — decides which it is, never what happens to exist on disk. A library file whose declared name disagrees with its stem is refused, so the file the library hands over always calls itself what it was asked for.

A store of regular files the operator owns, written by hand or through the authoring verbs; Naiad ships its starter inside the package and copies it in only on request, after which the copy is the operator's and is never replaced while it differs from the shipped one (ADR 0049). A symlink is a valid entry made by hand for a Workflow maintained in a repository, so a name resolves to the file as it stands rather than to a copy of it (ADR 0037).
_Avoid_: Registry, catalog, index, workflow dir, templates

**State**:
One phase of a Workflow. Carries a name, an optional Prompt, and whether entering it Clears the session. The agent declares which State it is in; Naiad only reacts.
_Avoid_: Phase, step, stage

**Prompt**:
The text Naiad delivers to the session when the agent enters a State. Typically a slash command invoking a user skill, with the agent's next State interpolated in.

Typed rather than pasted, in pieces small enough that the Session reads them as typing, and confirmed rather than assumed: a `UserPromptSubmit` hook checks what the Session took against what Naiad typed. A Prompt that arrived cut short is turned away before the agent starts on it and typed again, bounded like a Clear. The Announcement is handled only once the Prompt has landed whole (ADR 0053).
_Avoid_: Kickoff, template, instruction

**Pin**:
A sentence a Prompt adds to fix what its skill deliberately leaves loose — a criterion, an operand order, a permitted set — so the Workflow's behaviour survives edits to the skill (ADR 0033). Costly in Prompt length, so kept only where the loose reading has actually failed (ADR 0041); asserted nowhere by the tests, which hold invariants rather than content (ADR 0043).
_Avoid_: Constraint, guard, override, hardcoding

**Gate State**:
A State with no Prompt. Naiad delivers nothing and takes no action; the human types into the session directly to move things along. Requires no special handling — it falls out of the general rule that Naiad delivers a State's Prompt. A Terminal State with no Prompt is not a Gate State: it ends the Run rather than holding it for a human, so resolving with Gates skipped steps over Gate States but never over it.

What follows a Gate State is told to both sides without Naiad delivering anything: the agent learns it from the reply to its own Announcement, and the human from the notification. So the human's hand-off is a verdict, not a State's name.

Skipping applies to the declared order alone. A Gate State a Branching State names as a candidate is never skipped, because it is a destination the agent chose rather than a routine checkpoint on the path, and removing it would overrule the judgment that is the agent's to make. So a Run resolving with Gates skipped can still park — it declines routine review, not every stop.
_Avoid_: Gate, approval, human review, hold

**State file**:
The file the agent writes to declare its current State. The agent is its only writer; Naiad only reads it. This single-writer rule is what makes the agent, not Naiad, the owner of workflow progress.
_Avoid_: Status file, progress file, blackboard

**Session**:
The one tmux Claude Code session a Workflow runs in, start to finish. A Workflow is a Session.

Outlives its Run deliberately, because it holds the evidence of what the Run did. That Run's ending releases it, so that what it outlives it no longer answers to. A released Session belongs to no Run. The Protocol is injected into no fresh context there and the Protocol verbs refuse, which leaves an ordinary Claude Code session for the human to read and type in — and a free one for a later Adoption.

One exception: a Child that completed has its Session closed once its Parent has been told of it, since its work has been taken in and an idle Session per item would crowd out the Runs beside it; the transcript and logs stay on disk (ADR 0062).

Released by the agent's own last Announcement, by Naiad's record of the Finish it carried out, or by the Cancellation the operator's removal wrote — any one of the three. The Announcement comes first, because the agent owns workflow progress: a Session is released when the agent says the work is over, and not when Naiad notices. Naiad's record holds the release afterwards, because only the latest Announcement is kept and an agent that announces past its own ending would otherwise take the Session back. The Queue reads the record alone, so the two may disagree until a Run is next ticked (ADR 0035).
_Avoid_: Worker, pane, instance

**Clear**:
Discarding the Session's accumulated context (`/clear`) before delivering a Prompt. How a State gets a clean context without a new Session.

Confirmed before the Prompt follows it, never assumed. The `/clear` can be dropped, and a Prompt delivered into the context it should have discarded is the one failure Clearing exists to prevent — so that a Clear landed is reported by a `SessionStart` hook, the counterpart to the `Stop` hook that reports a Turn's end, and until it does the Clear is re-typed rather than delivered through. Bounded like a Nudge: after a small fixed number of tries the human is told, because delivering into an un-cleared context is never done on purpose.
_Avoid_: Reset, fresh session, restart

**Compaction**:
The Session summarising its own accumulated context in place, mid-phase, once it has filled to the point the Workflow declares — so that a long State runs on a working memory kept small rather than on everything it has ever read. The Session's act and not Naiad's: Naiad neither measures the context nor asks for the summary, and it never interrupts the agent to make room for one. It declares the point once, when the Session is launched, and learns that a Compaction happened the way it learns a Clear landed — through the `SessionStart` hook — whereupon it re-teaches the Protocol and reminds the agent which State and Subject it is standing in, since the summary may have lost them. Distinct from a Clear, which discards the context on purpose between States; a Compaction keeps the phase's progress and happens within one. Naiad-driven compaction — a reading of the context, a request that the agent yield its turn, a typed `/compact` — was considered and declined: the Session already does all three (ADR 0047).
_Avoid_: Auto-compact (the mechanism, not the term), summarise, context reset, yield, pause

**Model**:
The Claude model a State's work runs on. Declared in the Workflow file — on the State, or as an optional file-level default that a State's own key overrides — or by an Entry for a State it names, which beats both: whether a phase earns the expensive model is usually the phase's nature, but sometimes the task's, and the operator queueing the task is the one who knows. A State none of the three names has no Model, which is an opinion Naiad does not hold rather than a value it must find: nothing is typed, and the State runs on what the Session holds, which stickiness makes the last Model any State set (ADR 0040). Opaque to Naiad, which passes it on without knowing whether it names a real model: the Session is the authority on what is valid, and any list Naiad kept would rot.

Carried into the Session as a Switch, where the Belief says the Session does not hold it already, and best-effort where a Clear is confirmed: a Prompt into an un-cleared context poisons the work, while a Prompt on the wrong Model merely degrades its cost or quality. Preceding Prompt delivery means a Gate State gets none, which keeps "Naiad delivers nothing and takes no action" true there; the human at the keyboard can set their own, and it stands until a State declares otherwise. The Answerer's Model is declared separately in the same file and passed at invocation. Absence means no opinion there too, but resolves elsewhere: a headless session starts clean each time, so the platform's own default answers rather than the last State's Model.
_Avoid_: LLM, engine, tier

**Fallback**:
The models the Answerer may degrade to when its Model is unavailable, declared beside it as an ordered list the platform walks — Naiad forwards it opaquely and never learns which model answered. Exists only for the Answerer: it is the one headless invocation Naiad makes, and headless is where the platform hosts the feature; a State's Model has no Fallback, and its unavailability falls through the existing soft failures — the sticky previous model, or the silence rule. Absent unless declared, and absence means today's behavior.
_Avoid_: Retry, degradation chain, backup model

**Effort**:
How hard the Model thinks, declared beside it and treated identically: an Entry's setting for a State over the State's key over an optional file-level default, absence meaning no opinion, opaque, carried as a Switch, best-effort, and declared separately for the Answerer. The two are one kind of judgment — what the nature of a phase's work demands — carried as two terms only because the Session takes them as two commands. They are compared against the Belief one at a time all the same, so a State that moves one and keeps the other spends a Tick on the one it moved.
_Avoid_: Thinking budget, reasoning level, thoroughness

**Switch**:
Typing one of a State's settings — its Model or its Effort — into the Session ahead of that State's Prompt. How a phase comes to run on what its Workflow says it should.

One Switch to a Tick, and the Prompt only once every one of them has gone. The Session discards whatever arrives while it is handling a slash command it already has, so a Switch typed straight after another is lost, and so is a Prompt typed straight after a Switch — which parks the Run, since a Prompt that never arrived starts no Turn for the silence rule to read (ADR 0038). The Ticks between are the whole of the fix: unlike a Clear a Switch is never confirmed and never re-typed within one Announcement, because a wrong Model costs price or quality where an un-cleared context costs the work.

A State owes a Switch only for a setting the Session is not believed to hold already (ADR 0039). The settings are sticky, so a State asking for what is there pays two Ticks to change nothing, and the comparison is per setting rather than over the pair.
_Avoid_: Model switch, setting change, /model

**Belief**:
What Naiad takes the Session's settings to be: the last value it typed for each. Not a reading — the Session fires no hook on a Switch and asking it what it holds is forbidden — so what Naiad put there is the only evidence there is. It is read back out of the Run log, where every Switch is already written, rather than kept anywhere of its own, and a launch flag seeds it exactly as a typed Switch does.

Every Notify discards it. A Notify is Naiad saying it needs a human, and a human at the keyboard may set their own Model, so past one what Naiad typed is evidence of nothing. Discarding it is the only self-healing a Switch has left — it is what re-types one the Session dropped — and it hangs on a Notify rather than on a Gate State because a Gate is one hand-off to a human among several: a parked Run, a Clear that looks dropped and an escalated Question are the others. A Report hands nothing over and leaves it standing.

The two halves are read together and judged apart. What was last typed, and whether a human has had the keyboard since, are both facts the Run log already holds; that the second makes the first worthless is a rule, and rules live in one place.
_Avoid_: Cache, state, known settings

**Artifact**:
A file the agent writes that carries meaning between States, or that a human reads to review the agent's work. Because Artifacts hold the context, a State can be Cleared without losing anything.
_Avoid_: Deliverable, output, checkpoint

**Question**:
A decision the agent cannot make alone, announced through the State file rather than asked interactively. Carries its own text and every option the agent was weighing, so that whoever answers — and whoever later reviews the answer — sees the same choice the agent faced.

Asked one at a time (ADR 0044). Only the latest Announcement is kept, so a second Question would replace the first unanswered — a decision lost with nobody told — and the ask refuses instead: the agent holds its remaining questions and asks each as the previous answer arrives. A Question is unanswered until its Answer is sent or its Escalation resolves it; the agent announcing a State over one abandons it, which is its judgment to make and the Answer log's to record.
_Avoid_: Prompt (reserved), query, blocker

**Answerer**:
The separate Claude session that resolves Questions in the human's stead, so a Workflow runs unattended. Opt-in: a Workflow that declares no `[answerer]` table gives every Question to the human, and declaring the table gives every Question to the Answerer, each with a State able to say otherwise (ADR 0050). The table is the Answerer's settings and the file's default, never a precondition: a State asking for the Answerer in a table-less file gets it on the platform's defaults. It settles anything inferable from the repo and its docs; credentials, external spend, and business priorities are not in the repo, so answering those would be inventing, and it escalates instead. It carries its understanding of the repo across every Question in a run rather than rebuilding it each time.
_Avoid_: Auto-answerer, product owner, classifier

**Consultation**:
One putting of a Question to the Answerer, and what came back. Distinct from the Question itself because asking and acting on the reply are separated by a rule: Naiad asks, the outcome arrives as a signal, and the next decision either sends the Answer into the session or notifies the Escalation. Collapsing the two would put that rule where the Answerer is called rather than in the decision function.
_Avoid_: Call, lookup, query, round trip

**Answer**:
What the Answerer settles a Question with, sent into the Run's Session and recorded in the Answer log. Sent only once a Turn has ended, for the same reason a Prompt is: it is typed into the Session the agent is working in, and an agent still working would be typed over. Consulting and escalating carry no such wait, because neither sends anything.
_Avoid_: Reply, response, resolution, verdict

**Escalation**:
The Answerer declining a Question as not the repo's to settle. Indistinguishable in mechanism from a Gate State — Naiad stops acting and the human types into the session directly.
_Avoid_: Handoff, needs-input, block

**Reserved Question**:
A Question the Workflow gives the human: every Question unless the State or an `[answerer]` table says otherwise (ADR 0050), and any Question from a State declaring `questions = "human"` (ADR 0046). The Answerer is never consulted: Naiad parks the Run at once, as it does on an Escalation, with the notification carrying the Question's text, and the human answers in the Session. The Answer log records it as escalated with a reason saying who put it with the human — no Answerer declared, or the State reserving it. The agent's side is unchanged — it asks exactly as the Protocol says — because whose a Question is belongs to the Workflow, like a State's Model, rather than to a Prompt telling the agent not to ask.
_Avoid_: Human question, HITL question, no-answerer

**Task**:
What an Entry's work is, in the operator's own words — the description a human reads in the Queue and the Answerer reads for context, and the text a Workflow's entrance States interpolate. Given when the Entry is made, once, and never absent: an Entry made with only a Subject takes that Subject as its Task, because an operator who gave only a Subject has said the Subject describes the work. The stand-in applies only when no Task arrives from anywhere — a Task given alongside a Subject, or supplied as a Batch file default, is the Task. At an Adoption the agent distils it from the conversation, because there the operator's words are a conversation rather than a line.
_Avoid_: Ticket (the work a Workflow implements), description, title, summary

**Run**:
One execution of a Workflow against one task, from kickoff to a Terminal State — or to the Cancellation that ends it early. Everything Naiad tracks belongs to a Run and is addressed through it; nothing is global, so a second concurrent Run is an addition rather than a redesign.
_Avoid_: Job, worker, instance, execution

**Queue**:
The ordered backlog of Entries. One per machine, spanning every working tree, taken strictly in order of Entry id within each Lane — and sequential per Lane, so at most one Run is ever live per working tree, while different working trees run concurrently. One-at-a-time was always about the working tree, and the target path names the working tree (ADR 0020). The one thing Naiad holds that does not belong to a Run, which is not a contradiction of the Run's rule but its complement: the Queue holds Entries, and an Entry is precisely a Run that does not exist yet.
_Avoid_: Backlog, schedule, pipeline, worklist

**Lane**:
The Queue narrowed to one working tree, named by an Entry's target path. Sequential within itself — at most one Run live, later Entries waiting behind it — while other Lanes run beside it (ADR 0020). Two worktrees of one repository are two Lanes, because the exclusion unit is the working tree rather than the repository.
_Avoid_: Track, channel, per-repo queue, slot

**Entry**:
A Run waiting to start, carrying everything kickoff would otherwise be told: the Workflow, the task, the target repository, the State to start at, the Subject, the Working branch when one is given, an optional pinned base, whether Gates are skipped, its Child limit, which Run spawned it when it is a Child, and any settings — a Model or an Effort — it names for States of its Workflow. A setting always names its State: one naming a State the Workflow lacks, a Gate State or a Terminal State is refused, since none of them is ever typed a Switch, while one naming a State the Run may never reach is kept, since where a Run goes is known only as it goes. Checked where the start State is, when the Entry is queued and again when it starts, so a Workflow edited in between refuses a stale setting as it refuses a stale start State. Addressed by its own id and never by its position, so that removing one, or later stepping over one, renumbers nothing. Shown by the shortest tail of that id no other Entry's id ends in, which the commands that take an Entry accept as readily as the whole id (ADR 0067).

Records which Run it became and nothing else. Whether it is waiting, running, parked or done is read from that Run, which already holds all four (ADR 0013).

Removing one is a Cancellation: the Run it became ends with it, which releases that Run's Session. An Entry is a Run that does not exist yet, so an Entry taken back is work called off — not a line deleted from a list while the work carries on (ADR 0036).

Pre-classifying an Entry means naming the State it starts at, which is the Workflow's own vocabulary rather than a category Naiad knows: a design Entry starts at `grill` because that is what the State is called, not because Naiad has learnt what a design is.
_Avoid_: Item, job, ticket (reserved for the work a Workflow implements), request

**Prune**:
Removing every done Entry from the Queue, together with the Run each became, as one act — and, after them, every Orphaned Run that reads done or parked. Only done Entries qualify, and a done Child only once its Parent has been told of it or has ended — waiting is future work, running backs a live Run, and parked is a Run asking for a human, so none of the three is Prune's to take. Removing one of those by name is a Cancellation instead, which deletes nothing; Prune faces no Run that may still be live, so the Entry and the Run leave together, and history lives exactly as long as its line in the listing — while what has no line lives only until the next Prune (ADR 0030). The one deleter of Runs: nothing else removes one, a Cancellation least of all.
_Avoid_: Clear (reserved for context discard), purge, gc, cleanup, sweep

**Cancellation**:
Ending a Run because the operator removed its Entry by name. The third witness of an ending beside the Terminal Announcement and the Finish, and the only one that is nobody's judgment but the operator's — which is why it needs no guard: naming one Entry is already the judgment Prune cannot make about a Run that may still be live.

Reaches a Run's Children with it: cancelling a Parent cancels each of them, since a Child exists only to serve it, and a cancelled Child is told to its Parent as cancelled.

Deletes nothing. It is written onto the Run as its own kind of line, never as the Finish it was not, so that a Run called off does not read back as one that completed. The Run then reads done, so its Session releases and the next Prune takes the orphan; the record survives exactly that long.

Written before the Entry is removed, which inverts a Prune's order (ADR 0029) because the two guard against opposite failures: a Prune must not let a Run outlive its Entry, and a Cancellation must not let an Entry outlive its release. So one that cannot be written refuses the whole removal. Nothing is typed into the Session — the agent learns at its next Protocol verb, from the refusal — and the operator is told which Session is now theirs (ADR 0036).
_Avoid_: Kill, abort, delete, abandon, stop

**Orphaned Run**:
A Run directory no Entry names, left behind by a Cancellation or when a Prune's Run removal fails. Temporary rather than a state to manage: the next Prune takes one that reads done or parked — an Entry-less Run can never be ticked, answered or advanced, so even its parking is permanent and protects nobody — and skips one that reads running, naming it by path, because running cannot distinguish a live Session from a dead one that never announced, and Naiad never looks at tmux to find out. Liveness is a fact only the operator has, so a running orphan is theirs to remove by hand.
_Avoid_: Stray run, dangling run, garbage, leak

**Adoption**:
An Entry that attaches its Run to a Session that already exists, instead of spawning one. Made from inside that Session by the agent, on the human's stated intent, after the human has done the early States by hand — so the conversation those States built stays in context. Queues in its Lane like any Entry and waits its turn; the Supervisor remains the one entrance to starting it.
_Avoid_: Takeover, attach, import, handover (reserved)

**Batch file**:
A document declaring several Entries at once, so that a night's work can be read before it is committed to. TOML, like a Workflow file, because a person or an agent writes it; keys at the top are defaults and an Entry's own keys override them. It is a way of describing Entries and not a thing the Queue holds: it produces N Entries, they queue in the order the file writes them, and nothing afterwards records that they arrived together — so there is no batch to cancel and none to report on.
_Avoid_: Batch (as something the Queue holds), bulk import, job file

**Supervisor**:
The one process that starts Runs. For each Lane with work waiting, it takes that Lane's first unfinished Entry, starts or ticks its Run, and moves on — one Run live per working tree, Lanes in parallel, and a Run started only within Capacity. Holds a lock for the whole of its life, which is what makes one-per-working-tree structural rather than a rule someone has to remember (ADR 0014). Holds no Run of its own: which Runs are live is derivable from the Entries, so concurrency is more Entries in that condition rather than a rewrite.
_Avoid_: Daemon, scheduler, runner, orchestrator

**Spawn**:
A Run enqueueing an Entry as its own Child, from inside its Session — the fifth Protocol verb. In every other respect the Child is an ordinary Entry: its working tree, Working branch, start State and Subject are the agent's to name and opaque to Naiad, which records only whose it is.
_Avoid_: Fork (a Branching State's territory), dispatch, delegate

**Child**:
An Entry a Run spawned, and the Run it becomes; that Run is its **Parent**. Exists to serve its Parent — its work counts once the Parent takes it in at a Join State, and cancelling the Parent cancels it. Runs in a working tree of its own, so in a Lane of its own, beside its Parent and its siblings.
_Avoid_: Sub-run, worker, subtask

**Child limit**:
How many of a Run's Children may work at once, given on its Entry; absent, there is no limit of the Run's own. A Child over it waits in the Queue like any Entry, so a limit of one takes the Children one at a time in the order they were spawned. A number rather than a mode, because what working in parallel means is the Workflow's, and Naiad knows only how many — so Naiad hands the number to the Prompt and leaves what it means there.
_Avoid_: Parallel mode, serial mode, width, fan-out

**Capacity**:
How many Runs may be working at once on the machine, Children included and a Parent held at a Join State not counted. A ceiling derived from the machine's memory unless the operator sets one, and below it a Run starts only while the operating system reports its memory and disk unstrained — so what else is open decides the real number from moment to moment. It bounds starting alone: a Run already working is never held back by it. An Adoption is held back only by disk, because the Session it joins is already live, but once started it is counted.
_Avoid_: Cap, max runs, concurrency limit, slots

**Join State**:
A State whose Prompt Naiad holds back while its Run's Children are still working. Delivered once a Child has finished that the Parent has not yet been told of, naming every such Child — by Subject, Working branch, working tree, and whether it completed or was cancelled — and each exactly once; delivered at once when the Run has no unfinished Child, saying that none is named; held otherwise. Holding is waiting rather than silence, so nothing is Nudged. A Parent cannot end over unfinished Children: its Announcement of a Terminal State is refused while any Child has not started, is running or is parked, and the refusal sends it to its Join State.
_Avoid_: Barrier, fan-in, Wait (reserved for the verb)

**Working branch**:
The git branch an Entry's work is done on. Given when the Entry is made, or Derived by the agent when it is not — but never invented by Naiad, because a correct name follows the target repository's conventions and Naiad knows no repository's conventions (ADR 0022).

Distinct from Branch, which is a path through a Workflow. The two words name unrelated things and the collision is the glossary's to prevent.
_Avoid_: Branch (reserved), git branch, feature branch

**Derived branch**:
A Working branch the agent names itself, when the Entry was made without one. Named inside the repository with its conventions in sight — recent branches, the team's own prefixes — which is what Naiad, blind to every repository, could never do. Declared to Naiad in the same turn it is created, and settled once declared: a Run's Working branch is written once however it arrives, because the next Entry stands on it.

Until the agent declares, the Entry claims no branch. Two branchless Entries may wait in the Queue together; each declaration is checked against the claims that exist when it is made, which is where the two-Entries-one-branch refusal fires for Entries that named no branch to refuse at their making.
_Avoid_: Auto branch, generated branch, invented branch, default branch

**Predecessor**:
The Working branch an Entry's work stands on, as far as the Queue knows: the Entry's pinned base if it has one, otherwise the Working branch of the most recent preceding Entry for the same repository. A preceding Entry whose own record carries no branch yields the branch its Run declared (ADR 0022); one with no branch anywhere — its Run never reached a head — contributes none and is walked past to the Entry before it. Entries for other repositories are walked over, because a branch name from another repository is not a fact about this one; Entries for the same repository are never skipped on the grounds that their work has landed.

An opaque string, passed into the Prompt without being interpreted, exactly as a Subject is. Whether to actually stand on it is decided in the Prompt by the agent, which can see whether it has already landed; Naiad neither asks nor knows (ADR 0015).
_Avoid_: Base, parent, upstream, base branch

**Announcement**:
The agent's act of declaring a State or a Question. Announcements are distinct and ordered even when they name the same State twice, which is what lets a State repeat — the agent implementing its fifth ticket announces the same State a fifth time, and Naiad acts a fifth time. Naiad acts once per Announcement and never twice — a bound above, not below: an Announcement replaced before Naiad looks is acted on not at all, which for a State is stale intent shed on purpose, and for an unanswered Question is the loss the ask refusal exists to prevent (ADR 0044).
_Avoid_: Update, signal, event, transition (a repeat is not a transition)

**Standing State**:
The State a Run is standing in: its latest Announcement's State — carried by a Question too, since the agent asks from where it stands — or, before it has announced anything, the State it began at, recorded on the Run when it starts. Read from the Run alone, never re-derived from the Workflow, so a Workflow edited under a live Run changes no Run's answer. One answer for every reader: the Protocol measures what the agent owes from it, a Compaction reminds the agent of it, and the Queue listing shows it beside the status. A Run that has ended keeps the one it ended in, which for a Cancellation is wherever the work stopped.
_Avoid_: Current State, phase

**Subject**:
What an Announcement is about: a string the agent names when it announces, which Naiad substitutes for `{subject}` in the Prompt it then delivers. Opaque — Naiad records it and passes it on without interpreting it, so a Workflow may make it a ticket file, a URL or a branch name without Naiad learning that Workflow's vocabulary.

It is what lets a State repeat over a series of items rather than merely repeat. The agent announcing implement a fifth time says which ticket the fifth one is, so the choice is made in the context that has just seen the whole series, rather than re-derived from scratch in the Cleared one that has seen none of it.

Belongs to the Announcement rather than to the Prompt, which is why the two directions are not symmetrical. A Prompt with `{subject}` and no Subject is rejected when the agent announces, since the Prompt cannot be rendered and the mistake is the agent's to correct. A Subject a Prompt has no slot for is kept and logged, because the Prompt is one reader and the Run log is another: the Subject of a Gate State is substituted nowhere and is read by the human, and it is the one that says which item they have been handed.
_Avoid_: Argument (reserved for the text after a slash command), payload, parameter, item

**Turn**:
One exchange in the session, from the agent being given something to do until it stops. Its ending is the safety half of delivery: an Announcement says the agent intends to advance, a turn ending says it is no longer working. Neither substitutes for the other — turns end constantly without the agent being ready, and an agent that has announced usually keeps working for a while. Reported by a `Stop` hook, which is the only way Naiad learns of it. Recorded against the Run it belongs to — or, before an Adoption's Run exists, against the Entry that will become it, so an ending in the gap is not lost (ADR 0042).
_Avoid_: Idle, done, finished, ready

**Tick**:
One pass of Naiad's loop: gather the signals, call the decision function, carry out the Action. Holds no rules of its own, so a condition that needs adding belongs in the decision function rather than here.
_Avoid_: Poll, cycle, iteration, heartbeat

**Protocol**:
The contract the agent must follow to be driven: announce rather than assume, never ask a human directly. Naiad's own responsibility, injected into every fresh context, so that a Workflow's author never carries it.
_Avoid_: Convention, instructions, preamble

**Deviation**:
An Announcement naming a State the expected next ones do not include — one State usually, several at a Branching State, where any candidate is on the path. Permitted — the human may have redirected the agent, and the agent's judgment is the point — but recorded, because it is more often a symptom of a confused agent than a decision.
_Avoid_: Violation, error, jump

**Nudge**:
The reminder Naiad sends when the agent falls silent without announcing anything — and without declaring a Wait, because a declared Wait is not silence. Bounded: after a small fixed number, Naiad stops and the human is notified. Unbounded nudging is Naiad fighting the agent rather than driving it.
_Avoid_: Retry, poke, watchdog

**Wait**:
The agent declaring, before ending its turn, that its silence is deliberate — it is waiting on something that will come back, named so the operator can read what. The third protocol verb beside announcing and asking: an Announcement means a phase is done, a Wait means the opposite. While one is in force Naiad does not Nudge; when it expires the ordinary silence rule resumes, which makes expiry the re-check for things that wake nothing on their own. Waits may chain — each new one replaces the last and resets the Nudge count — but draw on one bounded budget per Announcement, because an agent waiting indefinitely is a Run stalled with no human told.
_Avoid_: Sleep, suspend, pause, snooze

**Hold**:
The agent declaring, on the human's instruction, that the Run is in the human's hands: Naiad parks it deliberately — no Nudges, no expiry — until the human types into the Session and the agent signals again. The fourth Protocol verb. Distinct from a Wait, which waits on something that comes back on its own; a Hold waits on a person, joining Gate State and Escalation in that family, differing only in who initiated the handover — the Workflow, the Answerer, or the human.
_Avoid_: Pause (the human's word at the keyboard, not the model's), suspend, freeze, indefinite wait

**Report**:
Naiad telling the operator that a Run entered a State the Workflow marked for it, and handing nothing over. Distinct from a notification that a human is needed: nobody is asked to act, so the Run does not park and the Belief stands, because no human took the keyboard. One for each Announcement of the State, including repeats, told the moment the Announcement is seen rather than after the Prompt lands. A Question's Announcement is not an entry and the State a Run starts at has no Announcement, so neither reports. Never declared on a Gate State or a Terminal State, each of which already tells the operator on entry (ADR 0055).
_Avoid_: Notify (the park), heads-up, milestone alert

**Branch**:
One of several paths a Workflow may take through its States, chosen by the agent at a Branching State and rejoining a shared tail. Which Branch a task belongs to is a judgment about the work, so it is announced like any other State rather than decided for the agent.
_Avoid_: Route, path, classification (the act, not the result)

**Branching State**:
A State that names its candidate successors instead of leaving the declared order to supply one. The candidates are what the agent is told it may announce and what a Deviation is measured against, so a Branch is expressed by the one or two States that fork rather than by a transition graph over all of them — which would put Workflow meaning back inside Naiad.
_Avoid_: Fork, decision point, router (Naiad owns no router — see ADR 0005)

**Terminal State**:
The State that ends a Run. Declared by the Workflow rather than by a name Naiad knows, so that Naiad stays ignorant of any particular Workflow's meaning.
_Avoid_: Done, complete, final

**Answer log**:
The Artifact recording every Question of a run with its options and what became of it — the Answer chosen, the Escalation that ended it, or the abandonment the agent's next Announcement wrote over it (ADR 0044) — and the Standing State it was asked from. Escalations and abandonments belong there beside the answers: a log holding only the Questions that were settled would show an unattended run as tidier than it was. Written by Naiad rather than the agent, since Naiad holds both halves. What a human reads at a Gate State to judge whether the unattended run went astray. For a Question the human took, it holds who put it with them, never their reply, which is typed into the Session where Naiad does not see it.
_Avoid_: Q&A file, transcript, audit log

**Run log**:
The record of every Announcement Naiad received and every Action it took, in order — which State, which Action, and why. The diagnostic that turns "it produced something strange overnight" into a readable sequence, and the reason a finished Run's session is left alive rather than killed. Written by Naiad rather than the agent, like the Answer log, since a trail kept by the party being audited is worth little. Distinct from the Answer log, which is the narrower record of Questions and what became of them.
_Avoid_: History, trace, journal, events
