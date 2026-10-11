# Manual smoke: the Matt Pocock Workflow end to end

The parts of Naiad held back from automated testing — the tmux and Claude
adapters, the reaching of a terminal, a desktop and a phone, the hook scripts,
and the tick loop's wiring — hold no logic worth testing, so the only honest
check is running them for real. This is that check:
`workflows/matt-pocock.toml` driven against a real repository to its Terminal
State.

What a push service is *sent* is tested rather than smoked, because a request
is data and a wrong header is a phone that stays silent with nobody watching to
notice. What is left for here is everything a test cannot stand in for: that
the topic is subscribed, that the phone is reachable, and that the banner
arrives at all.

It takes **three full Runs**, because the criteria cannot all hold in one. A
supervised Run is needed to exercise the Gate State; a Run with `--skip-gates`
is needed to show that an unattended one reaches its Terminal State without a
human at any boundary; and a third stands on a pinned base, which needs a
repository the other two have already left behind. They are the same Workflow
file, which is the point of the flags.

The Supervisor is checked separately, over **two further Runs that the Queue
starts** rather than a person. They are the same Workflow again and want the
smallest tasks of the lot, since what is being watched is the Queue rather than
the work — but the second should build on the first, because the same two Runs
are what shows a Queue producing a stack rather than a person arranging one.

Run 3 also asks for **two short Runs that are abandoned once they have started**
— one to show that a branch already there is checked out rather than failed on,
and one for the case where the Predecessor lands mid-Run if that could not be
arranged inside Run 3 itself. Neither is driven to a Terminal State: both are
killed as soon as the branch head has done its work, and both are described in
Run 3's section rather than given one of their own. To kill one: `Ctrl-C` the
`naiad run` that is driving it, `tmux kill-session -t naiad-<run-id>`, and then
`uv run naiad queue rm <entry-id>` — a killed Run's Entry is never finished, so
one left in the Queue is what the next `naiad run` picks up instead of the work
you meant to start.

Everything below is observed, not assumed. Where a step says *record*, write the
answer into the Results section at the bottom of this file and commit it.

## Before any of them

1. `uv run naiad install` — once per machine, and again whenever you want the
   library repaired. It writes the `SessionStart` and `Stop` hooks, which do
   nothing when no Run is attached, and the `naiad-adopt` skill, which is
   reached for only when you ask Naiad to adopt a session you are already in;
   both are safe to leave installed. It then links `matt-pocock` in the
   Workflow library to the file in this checkout, so the name opens the file
   under review rather than a copy of it (ADR 0037). A copy already sitting
   there is refused rather than replaced: move it aside and run this again.
2. Set up the phone leg, which is the one part of notifying that reaches you
   after you have walked away. Install the ntfy app, subscribe it to a topic
   name nobody could guess, and export `NAIAD_NTFY_URL=https://ntfy.sh/<that
   topic>` in the shell you will drive from — plus `NAIAD_NTFY_TOKEN` if the
   topic is access-controlled. Check it before trusting it:
   `curl -H "Title: naiad" -d "smoke" "$NAIAD_NTFY_URL"` must reach the phone.
   Leaving both unset is a valid run of this smoke, and then every phone
   observation below reads "not configured".
3. Pick a real repository with something genuinely worth building — a task
   small enough to finish overnight and real enough that the grilling interview
   has something to bite on. The Workflow writes ADRs, a spec, tickets, commits
   and a pull request, so use a repository where all of that is welcome.
4. That repository must be set up for the Matt Pocock skills (`docs/agents/`
   present), because the spec and ticket States publish into its tracker. Run
   `/setup-matt-pocock-skills` there first if it is not.
5. The `pull-request` State opens a pull request directly through the MCP
   server for the repository's host. The repository must therefore be on a
   host with such a server configured — GitHub or Gitea — or opt out of a pull
   request with a `naiad.toml` marker at its root (ADR 0016, ADR 0018).

One terminal throughout. `naiad run` adds one Entry and then, with nothing else
supervising, becomes the Supervisor itself: it starts the Run, drives it, and
gives your prompt back once the Queue is drained (ADR 0014). It prints the
Entry's id as it queues it and the Run's id and session as it starts it, so both
are on screen without a second command:

```
uv run naiad run workflows/matt-pocock.toml "<the task>" --repo /path/to/repo \
  --branch <your-repo's-branch-name>
```

Because it drains the whole Queue rather than only the Entry you just added,
**start each of these Runs with the Queue empty of anything unfinished**. A Run
that was killed rather than finished leaves its Entry unfinished, and the next
`naiad run` resumes that one before it reaches your new work: `uv run naiad
queue list` after any killed Run, and `uv run naiad queue rm <entry-id>` what it
shows still `running`.

The Working branch is given or derived, never invented by Naiad (ADR 0022):
name one with `--branch` and it is used verbatim, or omit the flag and the
agent at the head of the Run derives a name from the repository's own
conventions and declares it with `naiad branch`. When you do give a name,
give one that does **not** exist in the repository yet — creating it is the
branch head's job, and a branch prepared by hand beforehand tests nothing.

To watch it work: `tmux attach -t naiad-<run-id>`. Detach with `C-b d` — do not
close the session, and do not type into it except where a step says to.

## Run 1 — supervised

As above, with no flags. Everything except the `review` Gate State should happen
without you.

- [ ] **The Gate State holds and releases.** The Run parks at `review`, you are
      notified **once** — not once per tick — and nothing further happens until
      you type into the session. After you type, it resumes at `spec`. Record
      how long it sat there before notifying, and that only one notification
      arrived.
- [ ] **Every leg carries that one telling.** The terminal line, the desktop
      banner and — with a topic configured — the phone all say the same thing:
      the Run id as the title and `state 'review' is a Gate State and is
      waiting for you` as the body. The phone push arrives at high priority.
      Record which legs fired. A phone that stays silent while the terminal
      prints is the failure this leg exists to remove, so record the stderr
      line (`naiad: ntfy notification failed: ...`) if one appeared.
- [ ] **It finishes.** The Run reaches `done` and `watch` stops ticking. The
      session is still alive afterwards. The ending is pushed too, at ordinary
      priority: the phone says `finished at done`.
- [ ] **It releases the session.** In that still-live session, type `/clear`.
      Nothing is injected — no Protocol, no next State. Then ask the agent to
      run `naiad announce done`: it is refused with `no run is attached to this
      session`. The session is now an ordinary Claude Code session.

## Run 2 — unattended

```
uv run naiad run workflows/matt-pocock.toml "<the task>" --repo /path/to/repo \
  --branch <your-repo's-branch-name> --skip-gates
```

Start it and leave it. Nobody types into this session at any point; if you have
to, that is the finding, and record what forced it.

- [ ] **A full unattended Run reaches its Terminal State**, having resolved past
      the `review` Gate State without a human.

## The Working branch, in Runs 1 and 2

Neither of the first two Runs pins a base, so both take the ordinary path: a
Working branch that does not exist yet, and nothing to stand on.

- [ ] **The Run puts itself on its Working branch.** Once the branch head has
      written anything, `git branch --show-current` in the target repository
      reads the name you passed to `--branch`, and the branch's first commit
      sits on top of the repository's base branch. Record the branch and what it
      was based on. Commits landing on the base branch itself is the failure the
      branch paragraph exists to prevent.

## Run 3 — stacked on a Predecessor

Runs 1 and 2 exercise the branch paragraph with nothing to stand on: no
`--base`, so `{predecessor}` renders as nothing and the branch head is expected
to base the new branch on the repository's base branch. This Run is the other
side of it — a Predecessor whose work has **not** landed, which is what a Queue
produces when one Entry follows another (ADR 0015).

Set it up by hand, because the Queue that would produce it does not exist yet:

1. In the target repository, branch off the base branch, commit something
   visible, and push it. That branch is the Predecessor. Leave it unmerged —
   open a pull request for it or none at all; the test is ancestry, not merge
   status, so a Predecessor with no pull request is the case that matters most.
2. Record the Predecessor's tip: `git rev-parse <the-predecessor-branch>`. It is
   the baseline for checking afterwards that this Run committed nothing onto it.
3. Return to the base branch, and check out something other than the base branch
   if you can — a leftover branch from Run 1 or 2 is ideal. The working tree is
   shared, so what is checked out when a Run arrives is whatever the last one
   left, and a branch head that creates its branch from the current HEAD instead
   of from the base it chose only shows up when the two differ.
4. Do **not** create the Working branch.

```
uv run naiad run workflows/matt-pocock.toml "<a task that builds on that work>" \
  --repo /path/to/repo --branch <a-branch-that-does-not-exist> \
  --base <the-predecessor-branch> --at grill --skip-gates
```

`--at grill` is deliberate: an Entry that pre-classifies skips the classifying
State, which is the whole reason the branch paragraph lives at the two heads
rather than in a State of its own. If the branch is only prepared when the
classifier runs, this Run is where that shows.

- [ ] **The branch is created, and stands on the Predecessor.** After the
      grilling State has written anything at all, `git branch --show-current` in
      the repository reads the Working branch, and
      `git merge-base --is-ancestor <predecessor> <working branch>` succeeds.
      Record both. A Working branch that does not contain the Predecessor's
      commit means the Run based itself on the base branch and the next piece of
      work will not see this one's code.
- [ ] **Nothing was committed on the wrong branch.** `git rev-parse
      <the-predecessor-branch>` still reads the tip you recorded before the Run,
      and the base branch's own tip is likewise unmoved. Both are branches this
      Run must build on and never write to.
- [ ] **The pull request opens against the Predecessor.** The pull request this
      Run creates has the Predecessor as its base, not the repository's base
      branch — the ancestry test is asked again at `pull-request` and the answer
      is passed to whatever opens the pull request as an explicit base. Record
      the base the pull request actually carries.
- [ ] **The re-asked question changes its answer.** While the Run is still
      working — any time before it reaches `pull-request` — merge the
      Predecessor into the base branch. The pull request must then open against
      the **base branch** rather than the Predecessor, because the Predecessor is
      now an ancestor of it. This is the case the re-test exists for, and the one
      a value computed at kickoff would get wrong. If merging mid-Run is not
      practical, take it as one of the two short Runs instead: start a Run with
      the same `--base` after the Predecessor has been merged, watch which base
      its branch head chooses, kill it there, and say in the results that it was
      checked this way rather than mid-Run.
- [ ] **Re-entry finds the branch rather than failing on it.** The other short
      Run: start one naming the **same** `--branch` as this one, now that it
      exists and has commits on it. The branch head must check it out and carry
      on with the commits intact; a Run that dies at `git checkout -b`, or one
      that starts the branch over, is the idempotence failure, and it is what a
      resumed Run would hit. Kill this Run once the branch head has got that far
      — it has nothing else to show, and letting it finish would put a second
      pull request on the same branch.

## Run 4 — walking a Wayfinder map (`--at wayfind`)

The loop ADR 0045 adds: AFK decision tickets resolved in order, a stop at the
first HITL one, and a spec written from the cleared map. It needs a charted
map, so chart one by hand with `/wayfinder` in the target repository first —
or reuse one — and make sure its frontier reads, in number order: at least one
`Mode: AFK` ticket, then a `Mode: HITL` one, then the rest.

1. `naiad run matt-pocock <repo> --at wayfind --subject <first AFK ticket file>`
   with no task: the ticket path stands in as the Task, and the Run log should
   show it in both places.
2. Watch the AFK passes. Each one Clears, delivers `/wayfinder <ticket>`, and
   announces `wayfind` again with the next ticket as the Subject — one ticket
   per Announcement, research tickets included, however many the skill would
   have run in parallel.
3. The loop must park at `chart` the moment the head of the frontier is HITL,
   even with AFK tickets unblocked behind it, and say in the session which
   ticket and which Mode stopped it. No Model is typed at `chart`: set your
   own, resolve the ticket by hand, then announce `wayfind` — or `map-spec`
   with the map file as the Subject if that was the last ticket.
4. The next `wayfind` pass re-types opus and high, because the Notify at
   `chart` discarded the Belief.
   Also provoke a Question from an AFK pass: a ticket that cannot be resolved
   without you — one that needs a credential, say. `wayfind` reserves its
   Questions for you (ADR 0046), so the Answerer must never be consulted: the
   notification arrives at once with the Question's text and names `wayfind`,
   the Answer log records it as escalated with that reason, and no Answerer
   session is started. Reply in the Session and watch it finish the ticket and
   scan on.
5. A cleared map reached from an AFK pass announces `review` with the map as
   the Subject; from there announce `map-spec`, and observe a Clear followed by
   `/to-spec <map file>`, then the ordinary `tickets` → `orchestrate` chain.

## The Supervisor, over a real Queue

The Supervisor's rules are tested as data in and Action out, and its loop with
sleeping and reporting injected. What neither can show is the Supervisor
against a real Queue — starting a real session, driving it to a real ending,
and moving on — so that is checked here.

It needs **two Entries small enough to finish**, against the repository the
Runs above used. Queue them, then supervise; nothing else is typed until the
second one ends. Neither pins a base, so the second stands on the first — give
it a task that genuinely builds on the first's, since the stacking checks below
read whether the second agent could see the first's code.

```
uv run naiad queue add workflows/matt-pocock.toml "<the first task>" \
  --repo /path/to/repo --branch <a-branch-that-does-not-exist> --skip-gates
uv run naiad queue add workflows/matt-pocock.toml "<the second task>" \
  --repo /path/to/repo --branch <another-branch-that-does-not-exist> --skip-gates
uv run naiad queue list
uv run naiad queue watch
```

`--skip-gates` on both, because a Gate State parks the Queue by design and the
point here is that nothing else does. One terminal is enough: the Supervisor
starts each Run and drives it itself.

The same two Entries can be written as one document and queued in one command,
which is how a night's backlog is reviewed before it is committed to. Keys at
the top are defaults for every Entry and each Entry may override them; the
Entries queue in the order the file writes them, which is the order the
Predecessor rule reads. Nothing records that they arrived together.

```toml
workflow = "workflows/matt-pocock.toml"
repo = "/path/to/repo"
skip-gates = true

[[entries]]
task = "<the first task>"
branch = "<a-branch-that-does-not-exist>"

[[entries]]
task = "<the second task>"
branch = "<another-branch-that-does-not-exist>"
```

```
uv run naiad queue add --file nightly.toml
```

One-at-a-time is now structural rather than a rule to remember: the Supervisor
holds an advisory file lock for its whole life, and the three checks below are
the only test that lock ever gets. Racing two real Supervisors is not something
the automated tests do — it would be flaky, slow, and would assert the operating
system's behaviour rather than Naiad's — so what the tests pin is what each
command does with the lock's answer, and whether the lock answers at all is
this document's to say.

- [ ] **A second Supervisor is refused.** With the Supervisor above running,
      `uv run naiad queue watch` in another terminal exits non-zero with a
      message saying one is already running, and starts nothing. Two of them
      would each take the first waiting Entry and put two agents in one working
      tree, which is the single thing one-at-a-time exists to prevent.
- [ ] **`naiad watch` is refused beside it.** `uv run naiad watch <the live run
      id>` in another terminal is refused for its own reason: the Queue is
      sequential, so the Supervisor is already driving that Run, and a second
      ticker on it delivers everything twice. Confirm nothing was delivered
      twice into the session as a result of asking.
- [ ] **`naiad run` while supervising enqueues and returns.** Type a third piece
      of work with `uv run naiad run …` while the Supervisor is mid-Run. It must
      print the Entry's id and return your prompt **immediately** — no session,
      no watching — and the Entry must appear at the **back** of `naiad queue
      list` rather than jumping ahead of what is waiting. Record how long it
      took to return. This is the same command an agent inside a session would
      run, and a session cannot host a process that blocks for hours.
- [ ] **The lock dies with the process.** After `Ctrl-C`-ing the Supervisor,
      `uv run naiad queue watch` starts normally with nothing to clean up
      first — and after `kill -9` on one, likewise. A stale lock needing an
      operator to remove it is the failure the kernel-held lock exists to
      prevent.
- [ ] **Two Entries run one after the other, with nobody between them.** The
      second Run's session does not exist until the first Run has reached
      `done`. Record both Run ids and the wall-clock moment each session
      appeared; overlapping sessions mean two agents were in one working tree,
      which is the single thing the sequential Queue exists to prevent.
- [ ] **The Queue says what became of each.** `naiad queue list` during the
      first Run reads `running` for it and `waiting` for the second, and after
      both, `done` twice — read off the Runs rather than off a status anything
      wrote down (ADR 0013). Record what it read at each point.
- [ ] **A restarted Supervisor picks up where it left off.** `Ctrl-C` the
      Supervisor while the first Run is mid-flight, leave the session alone, and
      start `naiad queue watch` again. It must resume the **same** Run rather
      than starting a second one for that Entry, and the Run must carry on from
      where it was. Record the Run id before and after; two ids for one Entry is
      the failure.
- [ ] **A parked Run holds the Queue.** Park the first Run deliberately — set a
      ticket's `Status:` to `ready-for-human` so the loop announces `handover`,
      as in the checks below. The second Entry must not start while it is
      parked, and must start once you type into the parked session and it
      reaches `done`. Record how long it was held, and that the notification
      arrived once.
- [ ] **An Entry removed before it runs never runs.** Queue a third Entry,
      `naiad queue rm` it before the Supervisor reaches it, and confirm no
      session is ever opened for it and the Supervisor drains past it without
      comment.

### The second Entry stands on the first

Neither Entry pins a base and both target one repository, so the second's
Predecessor is the first's Working branch, resolved when the second Entry starts
rather than when it was queued. This is the check that a Queue *produces* a
stack — Run 3 could only arrange one by hand — and it is the reason to prefer a
second task that genuinely builds on the first.

Nothing extra is queued for it; it is read off the two Runs already above.

- [ ] **The second Entry was handed the first's Working branch.** The second
      Run's `run.json` reads the first Entry's Working branch as its
      `predecessor`, not the repository's base branch and not nothing. Record
      what it says. Naiad passes an opaque string and knows no git (ADR 0015),
      so this is the whole of what Naiad decided; what the agent did with it is
      the next check.
- [ ] **The second Entry's branch is cut from the first's.** Once the second
      Run's branch head has written anything, `git merge-base --is-ancestor
      <first Working branch> <second Working branch>` succeeds in the target
      repository. Record both branch names and the answer. A second branch that
      does not contain the first's commits means the second agent never saw the
      first's code, and the conflict surfaces at merge rather than here.
- [ ] **The second pull request opens against the first's branch.** The first
      Entry's branch is still unmerged when the second Run reaches
      `pull-request`, so the ancestry test there answers the same way and the
      pull request stacks. Record the base it carried. If you merged the first
      Entry's pull request while the second Run was still working, the base must
      be the repository's base branch instead — say which happened.

Repository scoping — an Entry for another repository being walked over when the
Predecessor is resolved — is not checked here. It is a rule over Entries with no
git in it, covered as data in `tests/test_supervise.py`, and checking it for
real would need a second repository set up for the Matt Pocock skills to earn
nothing the table of cases does not already say.

## Run 5 — the implement loop builds tickets as Children

Short Runs on a scratch repository, each started at `orchestrate` with the
same tracked ticket set: two independent tickets, `01` and `02`, and a third,
`03`, blocked by both. Keep each ticket a few lines of code with a test, so
what is watched is the loop rather than the work. Create `feat/smoke` from the
base branch before queuing: a Run started at `orchestrate` is past the State
that would create its Working branch, and `orchestrate` hands over rather than
cut a branch that exists nowhere.

```
naiad queue add matt-pocock "<the ticket set's directory>" --repo <scratch repo> --branch feat/smoke --at orchestrate
naiad queue watch
```

1. **In parallel.** With no `children` key: record that `01` and `02` are
   claimed and committed in one pass, that two sibling worktrees
   `<repo>-wt-feat-smoke--01` and `--02` appear, and that both Children are
   building at once (`naiad queue list` shows them under the Parent, which
   reads `joining`). Record that `03` is spawned only after both are merged
   into `feat/smoke`. At the end, record that no `<repo>-wt-*` directory and
   no `feat/smoke--NN` branch remains, and that `pull-request` was entered
   exactly once.
2. **One at a time.** Commit `children = 1` in `.matt-pocock.toml` and run
   the set again from fresh tickets: record that no Child is spawned, no
   worktree or `feat/smoke--NN` branch appears, and each ticket is built by an
   `implement` delivery on `feat/smoke`, in ticket order, with `orchestrate`
   between them. Run it once more with no key and `--child-limit 1` on the
   Entry instead, and record the same.
3. **Cancelled.** Run it again and `naiad queue rm` one Child while it builds:
   record that the next `orchestrate` pass removes its worktree, keeps its
   branch, and that the Run ends at `handover` naming that ticket once the
   other tickets are in.
4. **On GitHub issues.** Publish the same three tickets as issues of a scratch
   repository with a remote, `03` blocked by both through GitHub's issue
   dependencies, and queue the Run with the parent issue as its task. Record
   how each ticket was claimed, and that every issue was closed by the Parent
   after its Child's branch was merged into `feat/smoke`, never by the Child:
   each issue's closing time is later than its merge commit on `feat/smoke`.
   Record that `03` was spawned only after both blockers were merged and
   closed (ADR 0066).

## What to observe across Runs 1 and 2

Each of these is an acceptance criterion of
`.scratch/core-engine/issues/07-the-matt-pocock-workflow-end-to-end.md`.

- [ ] **A Question is answered by the Answerer.** At least one Question is
      raised, resolved without you, and appears in the Answer log
      (`answers.json` under the Run's directory) with its options and the answer
      chosen. Record the Question. If a whole Run raises none, the grilling
      interview probably leaked — see Protocol leakage below.
- [ ] **The implement loop iterates.** The `implement` State is announced once
      per ticket, and each iteration starts from a cleared context — in the
      attached session, each ticket begins with the context wiped and the
      Protocol re-injected. Record the number of tickets and the number of
      `delivered implement` entries in the log; they must match.
- [ ] **Each iteration is given its own ticket.** Every `announced implement`
      entry in the log carries an `about:` naming a ticket file, no two the
      same, and the Prompt delivered into the session names that same file.
      A delivery reading `the ticket at ` with nothing after it means the
      Subject was lost between the Announcement and the Prompt.
- [ ] **The tickets are labelled before the loop reads them.** After `tickets`,
      check the `Status:` line of every published ticket. They should read
      `ready-for-agent` except where the ticket says why a human is needed. If
      they are all `ready-for-human`, the loop will hand over its first ticket
      and implement nothing — that is the failure ADR 0010 exists for, and it
      means the pinning in the `tickets` Prompt did not take.
- [ ] **A ticket the agent should not do parks the Run.** Set one ticket's
      `Status:` to `ready-for-human` before the loop reaches it. The agent must
      announce `handover` rather than implementing it or asking you in prose,
      the notification must arrive, and the Run log's `announced handover`
      entry must carry an `about:` naming that ticket. Type into the session to
      release it and confirm the loop resumes at the next ticket. Worth
      repeating once with an unrecognised status such as `ready`, which must
      also park and must say which status it found.
- [ ] **A needs-triage ticket is specified rather than handed over.** Set one
      ticket's `Status:` to `needs-triage` before the loop reaches it. The agent
      must announce `triage` with an `about:` naming that ticket, not
      `handover`, and the pass must start from a cleared context. It must not
      ask you in prose — `/triage` recommends and waits for direction by design,
      so this is the State most likely to leak (ADR 0033). Confirm the pass ends
      on `ready-for-agent`, `ready-for-human`, `needs-info` or `wontfix`, never
      on `needs-triage`, which is the loop the pin exists to prevent. Where it
      ends `ready-for-agent`, the Run must reach `implement` for that same
      ticket with nobody typing into the session. Record the outcome written and
      whether a Question was raised.
- [ ] **A wontfix outcome advances the Run rather than parking it.** Repeat the
      check above with a ticket whose work the repository already does, so the
      pass writes `wontfix`. The scan must walk past it and announce against
      the **next** ticket rather than the one just closed (ADR 0027, ADR 0034).
      Record which ticket it named. Any of the four exits is correct — what
      fails is an Announcement still carrying the `wontfix` ticket, or a park
      with open tickets left unread, either of which means the pass did not
      scan again.
- [ ] **Every State runs at the Model and Effort its Workflow gives it.** Read
      the status line at each State rather than counting slash commands. This
      file declares `opus` at `high` effort at the top and on no State, so
      every State's effective pair is that one. The first State of a spawned
      Run takes it as launch flags rather than as typed commands — kickoff
      spends no Tick on them (ADR 0026) — and every State after it holds what
      the Session already has, so it types nothing (ADR 0039). So the status
      line must read `opus` and `high` at every State, with **no** `/model` or
      `/effort` line anywhere in the Run. Record the pair the status line
      showed at every State, not only the first.
- [ ] **A hand-off to a human re-types the settings, and is the only place
      that types them at all.** At the `review` Gate, type `/model sonnet` into
      the session yourself before releasing it. The State after the Gate must
      then type `/model` and `/effort`, each with its own result line before
      the Prompt, and the status line must come back to `opus` at `high`. Two
      things ride on this one check. It is the self-healing a Switch has left
      (ADR 0039): without it your `sonnet` would have quietly priced every
      State after the Gate. And with one pair for the whole file, it is the
      only moment in the Run where a Switch is typed at all — so it is also
      the only witness of the two-commands-one-to-a-Tick sequence, and a
      missing `/effort` here is the fault ADR 0038 is about. No automated test
      can see that: the suite drives a fake session that accepts every send.
- [ ] **A Clear and a compaction each leave the agent able to announce.** The
      `implement` loop provides the Clears. A compaction is likelier during
      grilling or a long ticket; if none occurs naturally, force one with
      `/compact` in the session while the agent is mid-phase, and confirm the
      Protocol re-appears and the agent still announces afterwards.
- [ ] **The Session compacts itself at the file's point, and carries on.** The
      file declares `autocompact`, which rides the launch as a flag and is
      never typed (ADR 0047), so the Run log opens with a `launched` line
      naming the point and no `/autocompact` appears in the session. During a
      long `implement` ticket, watch the status line's context reading: it
      must fall back on its own once it passes the point, with nobody typing,
      and a `compacted` line naming `implement` must appear in the log for
      each time it does. After each one the agent must carry on with the
      **same** ticket — the Subject of the current `announced implement` line
      — rather than starting it over or announcing early, and the injected
      reminder in the session must name that State and Subject. Record how
      many `compacted` lines the Run produced and at which States, and any
      time the agent restarted a ticket after one.
- [ ] **The pull request State opens the pull request and ends the Run.**
      `pull-request` waits on nothing: once the pull request is open it
      announces `done`, and the Run ends. Confirm it neither declares a wait —
      no `waits.json` appears under the Run's directory — nor lingers for a
      review to arrive, and that the open pull request is the last thing the
      Run does. Record whether the agent announced promptly after the open or
      spent turns on anything after it.
- [ ] **The Run log stands alone.** Read `log.json` under the Run's directory
      and reconstruct what happened without opening the session. Record anything
      you had to open the session to understand — that is a gap in the log, and
      a bug against issue 06.

## Protocol leakage

The known risk: skills such as `grilling` ask interactively by design, and the
Protocol is one instruction arguing with another. When it leaks, the agent
blocks on a dialog nobody will answer, Naiad Nudges twice, gives up and
notifies, and the Run has done nothing since.

The Run log makes this countable without any extra instrumentation: a leak looks
like `nudged (attempt 1)`, `nudged (attempt 2)`, `notified` under one seq, with
no Announcement after it. For every such sequence, attach to the session, see
what the agent was actually doing at the time, and add it to
`.scratch/deferred/issues/01-protocol-leakage.md` — which State, which skill,
and whether it asked through a tool call or in prose. The deferred decision is
whether to intercept `AskUserQuestion`, and it wants a number rather than an
impression.

## Artifact discipline

The Clearing States (`diagnose`, `implement`, `triage`, `pull-request`) are
only safe because the States before them wrote Artifacts.
Nothing enforces this, and the symptom is a State that appears to have forgotten
what it just did.

`pull-request` is the one to watch hardest: a PR flow prefers the session's
context for the description, and this Workflow Clears before it on purpose, so a
pull request described from the branch diff is correct here and a thin or empty
description is the bug.

The same Clear is why a Companion repository is read from the project rather
than remembered: the State that did the work in the second checkout is gone by
the time the pull requests open, so a companion `naiad.toml` never names is one
the tail cannot find (ADR 0048). The cross-repository ending is not checked by
any of the Runs below — it would need a second repository set up for the Matt
Pocock skills and a task that genuinely spans both — so a project that uses it
is the place to watch for a companion left unopened, or a pull request opened
over a branch that was never this Run's.

`triage` carries the same risk from one direction only. Entered from `implement`
it needs nothing the ticket does not already hold. Entered from `handover` it
Clears away the answers a human has just typed into the session, so those answers
belong on the ticket before the Announcement (ADR 0034). The symptom is a pass
re-asking a question the human answered at the gate a moment earlier.

Any instance of a State groping for something it no longer holds goes on
`.scratch/deferred/issues/02-clear-and-artifact-discipline.md` — it will read as
a model failure rather than a Workflow bug, which is exactly why it is worth
writing down.

## Results

_Fill in after the Runs and commit._

**Run 1 — supervised**

- Run id / repository / task:
- Working branch created, and what it was based on:
- Gate State held, notified once, released:
- Legs that carried it (terminal / desktop / phone), and any failure line:
- Reached Terminal State, and whether the ending reached the phone:

**Run 2 — unattended (`--skip-gates`)**

- Run id / repository / task:
- Working branch created, and what it was based on:
- Reached Terminal State with nobody typing:
- Anything that forced an intervention:

**Run 3 — stacked on a Predecessor (`--base`, `--at grill`)**

- Run id / repository / task:
- Predecessor branch, its tip before the Run, and whether it had a pull request:
- Branch checked out when the Run started:
- Working branch created, and what it was based on:
- `git merge-base --is-ancestor <predecessor> <working branch>`:
- Predecessor and base branch tips unmoved afterwards:
- Base the pull request actually opened against:
- Reached Terminal State:
- Base chosen once the Predecessor had landed, and whether that was mid-Run or
  in a short Run of its own:
- Re-entry onto the existing branch, and whether its commits survived:

**Run 4 — walking a Wayfinder map (`--at wayfind`)**

- Run id / repository / map:
- AFK tickets resolved, in order, one per Announcement:
- Ticket and Mode that parked the Run at `chart`, with AFK tickets behind it:
- Model typed by hand at `chart`, and the pair re-typed on the next pass:
- Question asked from `wayfind`: notification text, Answer log entry, and
  whether an Answerer session appeared:
- Cleared map: which State announced it, and what `map-spec` delivered:
- Reached `tickets` with a spec on the tracker:

**The Supervisor over a real Queue**

- Entry ids / Run ids / tasks:
- Second `naiad queue watch` refused, and what it said:
- `naiad watch` on the live Run refused, and whether anything was delivered
  twice as a result of asking:
- `naiad run` while supervising: how long it took to return, and where its Entry
  landed in the list:
- Supervisor started again after `Ctrl-C` and after `kill -9`, with nothing to
  clean up first:
- When each session appeared, and whether any two overlapped:
- What `naiad queue list` read during the first Run and after both:
- Run id for the first Entry before and after the Supervisor was restarted:
- Parked Run: how long it held the Queue, and notifications received:
- Entry removed before it ran, and whether anything started for it:
- `predecessor` recorded in the second Run's `run.json`:
- `git merge-base --is-ancestor <first branch> <second branch>`:
- Base the second Entry's pull request opened against, and whether the first
  Entry's pull request had been merged by then:

**Run 5 — the implement loop builds tickets as Children**

- Run ids / scratch repository / ticket set:
- In parallel: `01` and `02` building at once, `03` spawned after both merged:
- Worktrees and ticket branches left at the end, and `pull-request` entries:
- `children = 1` and `--child-limit 1`: Children spawned (expect none), and the order the Parent built the tickets in: 2026-10-03, scratch repositories `naiad-smoke-serial-key` (`children = 1`, Run 20261003-111305-matt-pocock-30663) and `naiad-smoke-serial-flag` (`--child-limit 1`, Run 20261003-111307-matt-pocock-30663). Both: no Child, no worktree, no `feat/smoke--NN` branch; `implement → build-here` three times, 01, 02, 03 in order, one commit each on `feat/smoke`, then `pull-request` (skipped, no remote) and `done`. The first `implement` rendered `Child limit:` empty and `1` respectively, and `{children}` as `- none`.
- Cancelled Child: worktree removed, branch kept, ticket named at handover:

**Runs 1 and 2**

- Questions raised, answered, escalated:
- Tickets implemented / implement deliveries:
- Ticket statuses as published by `tickets`:
- Handovers, and the status that caused each:
- Clears and compactions survived:
- `compacted` lines and their States, and whether any ticket was restarted after one:
- Run log sufficient on its own:
- Protocol leaks observed:
