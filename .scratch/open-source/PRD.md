# Open-source Naiad: the first public release

Status: ready-for-agent
Map: [map.md](map.md) (sixteen resolved tickets under `issues/`)

## Problem Statement

Naiad works, but only for the person who built it. The one Workflow it ships opens every State with a slash command from a third-party plugin and reads a `naiad.toml` convention Naiad never owned. It is installed from a source checkout, and it links that checkout into the library. Its documentation is written for one reader and cites about five hundred architecture records that an outsider cannot use.

Someone who finds the repository today cannot install it from PyPI, cannot run anything on a plain Claude Code install, and cannot write a Workflow of their own without learning the TOML schema from the source.

Several small behaviours also only make sense to someone who already knows the engine:

- The Queue listing says `parked` without saying where.
- A Gate leaves both the agent and the human unsure what comes next.
- A missing `tmux` surfaces as a Python traceback.
- A misspelt Workflow key is silently ignored.
- A first `naiad ask` would start a headless Claude session with permission prompts off in a repository the adopter never agreed to hand over.

## Solution

Ship Naiad as `naiad-cli` on PyPI, under MIT, with its two Workflow files under 0BSD. An adopter types `uv tool install naiad-cli`, then `naiad install --starter`, then `naiad queue add starter "<task>" --repo .`, and the result is a finished Run on a plain Claude Code install:

- one Session driven through plan, review, implement, verify and ship;
- cleared between phases;
- one Gate where the adopter reads `PLAN.md` and sends a verdict;
- a pull request or a branch at the end.

Workflows become things an adopter authors without reading the schema. Two nouns, `naiad workflow` and `naiad state`, carry verbs that write the TOML file. The file stays the truth and stays hand-editable. The library becomes a store of files the adopter owns, and the starter is copied into it only on request.

The engine changes only where a declaration or a legibility gap needs it:

- The Queue listing shows each Run's Standing State.
- A State can ask for a Report on entry without parking the Run.
- The Answerer is opt-in, and its Answers are readable through a verb.
- A Gate tells both sides what follows it.
- Unknown keys are refused.
- `naiad doctor` and the entrance refusals turn missing prerequisites into sentences.

The documentation is rewritten for adopters: a README, `docs/running.md`, `docs/workflow-authoring.md`, `docs/how-it-works.md` and `CONTRIBUTING.md`. A drift test keeps every command line in them valid.

The maintainer's record (ADRs, glossary, tracker, smoke notes) comes off the public repository and out of its history. The personal Workflow stays in the repository, unoffered and unmentioned.

## User Stories

### Installing and the first Run

1. As an adopter, I want to install Naiad with `uv tool install naiad-cli`, so that I need no source checkout and still type `naiad`.
2. As an adopter, I want `naiad install` to write the hooks and the adopt skill into the Claude Code configuration I actually use, so that Sessions report their turns instead of looking silent.
3. As an adopter who sets `CLAUDE_CONFIG_DIR`, I want install to write the hooks into `$CLAUDE_CONFIG_DIR/settings.json` and the skill into `$CLAUDE_CONFIG_DIR/skills`, so that Naiad follows the directory Claude Code reads.
4. As an adopter, I want `naiad install --starter` to put a starter Workflow in my library as a regular file, so that I can run it by name at once and edit it as my own.
5. As an adopter, I want a bare `naiad install` to leave my library alone, so that re-running install never touches my Workflows.
6. As an adopter who edited the starter, I want `naiad install --starter` to refuse to overwrite my copy and name `--force`, so that a thoughtless re-run never destroys my work.
7. As an adopter whose starter is unchanged, I want `naiad install --starter` to refresh it silently, so that an older copy picks up the shipped fixes.
8. As an adopter, I want install to end by printing doctor's report, so that I see a missing prerequisite on the first command I type.
9. As an adopter, I want the starter to run on a plain Claude Code install with no custom skills, so that my first Run needs nothing I don't already have.
10. As an adopter, I want the starter to plan into `PLAN.md`, stop at one Gate, then implement, verify and ship with a Clear between each, so that I see both of Naiad's claims (no manual Sessions, contained context) in one Run.
11. As an adopter, I want the starter to open a pull request when the repository has a remote and `gh` is authenticated, and to stop at the branch otherwise, so that the Run ends usefully on any repository.
12. As an adopter, I want the starter to declare no Model, Effort or Answerer, so that a Run uses what my Claude Code holds and never decides anything without me.
13. As an adopter, I want the README to warn me before install that every Session runs with permission prompts off and to suggest a throwaway repository for the first Run, so that I know what I am handing over.
14. As an adopter, I want the README to tell me about Claude Code's folder-trust dialog on a repository it has never opened, so that I answer it in the pane instead of thinking the Run is stuck.
15. As an adopter, I want the README to tell me that my own `CLAUDE.md` and global rules apply inside a Run, so that I am not surprised when the plan follows them.

### Knowing the machine is ready

16. As an adopter, I want `naiad doctor` to list every finding as fail, warn or info, each ending with the command that fixes it, so that I can fix everything in one pass.
17. As an adopter, I want doctor to fail when `tmux` or `claude` is missing from `PATH`, so that I learn about a missing prerequisite before a Run needs it.
18. As an adopter, I want doctor to fail when the hooks are missing from the settings file Claude Code reads, or name a `naiad` other than this one, so that a moved install is caught.
19. As an adopter, I want doctor to fail when `NAIAD_HOME` cannot be created or written, so that Naiad's storage problems surface before a Run.
20. As an adopter, I want doctor to warn when `claude --version` is below the floor Naiad's flags need, or cannot be read, so that I know to upgrade without being blocked when my Workflows use none of the newer flags.
21. As an adopter, I want doctor to warn when the adopt skill is missing, when a library entry does not load, or when a running tmux server's `PATH` has no `claude`, so that the quiet failures are named.
22. As an adopter, I want doctor to tell me which notification legs will fire and whether my library is empty, so that I know how I'll hear about Runs and what to do first.
23. As an adopter, I want doctor to repair nothing, so that `naiad install` stays the one verb that writes Claude Code's configuration.
24. As an operator, I want `naiad run`, `naiad watch`, `naiad adopt` and the Supervisor to refuse with one sentence (the missing thing, why Naiad needs it, the fix, then `naiad doctor`), so that I never read a traceback for a missing binary.
25. As an operator, I want `naiad queue add` to queue without checking the machine, so that I can queue work on one machine that another will run.
26. As an agent inside a Session, I want the Protocol and hook verbs never to run the machine checks, so that a live Session is never refused over something it cannot fix.
27. As an operator whose Answerer cannot run, I want the Question escalated with a readable reason such as "the Answerer could not be run: `claude` is not on PATH", so that I answer it myself and know why.

### Running and watching

28. As an operator, I want `naiad queue list` to show each Run's Standing State right after its status word, so that `parked  review` reads as a phrase and I know where each Run stands without opening a notification.
29. As an operator, I want a waiting Entry to show `-` in that column, so that nothing claims a State for work that hasn't started.
30. As an operator, I want a running Run that hasn't announced yet to show the State it started at, so that the column is never blank for live work.
31. As an operator, I want a done Run to show the State it ended in, so that a Cancellation shows where the work stopped.
32. As an operator, I want the column to report what the Run recorded even when the Workflow no longer declares that State, so that editing a Workflow under a live Run never rewrites a Run's history.
33. As an operator, I want the Gate notification to name the State that follows (or the candidates, where the Gate branches), so that I know what my verdict unlocks.
34. As an operator at a Gate, I want to type a verdict ("go ahead", or what to change) and send it, with no State name needed, so that clearing a Gate needs no knowledge of the Workflow's vocabulary.
35. As an agent announcing a Gate that Naiad will park on, I want the announce verb's reply to tell me a human takes it from here, to end my turn, and what to announce afterwards, so that I can act on the human's verdict without being told the State's name.
36. As an agent announcing any other State, I want the plain `announced X (n)` reply, so that I am not tempted to start the next phase before Naiad delivers it.
37. As an operator, I want a Question from a Workflow with no Answerer to park the Run and notify me with its text, so that nothing is decided without me unless I opted in.
38. As an operator, I want a Workflow that declares `[answerer]` to send every Question to the Answerer unless a State says `questions = "human"`, so that turning the Answerer on is one table, not a key on every State.
39. As an operator, I want a State in a Workflow with no `[answerer]` table to be able to opt in with `questions = "answerer"`, so that I can trust the Answerer with one phase alone.
40. As an operator, I want `naiad queue answers <entry-or-run>` to print one numbered block per Question (State, Question, options, and whose outcome it was), so that I can audit an unattended Run without opening JSON.
41. As an operator, I want that verb to require the Entry or Run and never default to the latest, so that I never read the wrong lane's Answers.
42. As an operator, I want the Finish and Gate notifications to say "N answered by the Answerer — naiad queue answers <entry>" when the Answerer answered at least once, so that I know there is something to review and how.
43. As an operator, I want `naiad queue watch` to echo each consultation and answer as one line cut to the terminal width, so that the stream stays readable while the full detail lives in the log.
44. As an operator, I want a State marked `report = true` to tell me each time a Run enters it, on every leg, without parking the Run or discarding the Belief, so that I can follow milestones without stopping the work.
45. As an operator, I want each Report to say `entered <state>` plus the Subject when there is one, and to reach ntfy at a lower priority than a Gate, so that a milestone never sounds like a request for me.

### Authoring Workflows

46. As a Workflow author, I want `naiad workflow list` to show every Workflow in my library, naming a broken link as broken, so that I see what I can run.
47. As a Workflow author, I want `naiad workflow show WF` to print the file-level keys and every State with its kind and marks, so that I can read a Workflow without reading TOML.
48. As a Workflow author, I want `naiad workflow new NAME` to create a Workflow with a terminal `done` and nothing else, so that I start from something that loads.
49. As a Workflow author, I want `naiad workflow new NAME --from WF` to copy a Workflow and rewrite its `name` to the new stem, so that the copy is never misfiled.
50. As a Workflow author, I want `naiad workflow rm` and `naiad workflow rename` to refuse while a queued Entry or live Run addresses the file, naming them, so that I never pull a Workflow out from under work in flight.
51. As a Workflow author, I want `naiad workflow check WF` to load the file the way a Run would and report what is wrong, so that my hand edits have a safety net.
52. As a Workflow author, I want `naiad workflow set|unset WF KEY [VALUE]` over a key table that `--help` prints, so that every file-level key is reachable without a verb of its own.
53. As a Workflow author, I want `naiad state list|show` to show a State's kind (`prompt`, `gate` or `terminal`) and its marks (successors, `clears`, `report`, whose Questions, `model/effort`), and `show` to print the Prompt in full, so that I can read a State at a glance.
54. As a Workflow author, I want `naiad state add` to land a new State before the terminal State unless I say `--after` or `--before`, so that the common case needs no placement flag.
55. As a Workflow author, I want `naiad state add` to take the Prompt from `$VISUAL` or `$EDITOR`, from `--from FILE`, from stdin with `--from -`, inline with `--prompt`, or not at all with `--gate`, so that I can write Prompts interactively or from scripts.
56. As a Workflow author with no editor set, I want a one-sentence refusal naming both remedies, so that I am never dropped into `vi`.
57. As a Workflow author, I want an editor that exits on an empty file to change nothing and say so, so that an aborted edit is harmless.
58. As a Workflow author, I want `--clear`, `--model`, `--effort`, `--next`, `--terminal` and `--auto` on `state add`, so that I can declare a whole State in one line.
59. As a Workflow author, I want `naiad state set|unset WF STATE KEY [VALUE]` for `model`, `effort`, `clear`, `terminal`, `questions` and `report`, validated before any write, so that a bad value never reaches the file.
60. As a Workflow author, I want `set` to refuse `name`, `prompt` and `next` and name the verb that owns each, so that I learn the right verb from the refusal.
61. As a Workflow author, I want `naiad state rename` to rewrite every `next` that names the State, so that renaming never breaks an edge.
62. As a Workflow author, I want `naiad state rm` to refuse while another State names it in `next`, naming those States, so that removal never leaves a dangling successor.
63. As a Workflow author, I want `naiad state move WF STATE --after|--before OTHER` to reorder States, so that I can edit the path most States take.
64. As a Workflow author, I want `naiad state next WF STATE A B` to replace the successors, `--none` to clear them, and no arguments to open a numbered picker, so that branching is easy whether I know the names or not.
65. As a Workflow author, I want `naiad state set-prompt WF STATE` to edit a Prompt through the same sources as `add`, so that Prompts are never hand-escaped TOML strings.
66. As a Workflow author, I want every writing verb to reload the file after writing and restore it on failure, so that no verb leaves an unloadable file behind.
67. As a Workflow author, I want the verbs to keep my comments and layout, so that the file stays mine to read and hand-edit.
68. As a Workflow author with a hand-made symlink in my library, I want the verbs to write through it to the file it points at, so that a Workflow maintained in a repository can be edited either way.
69. As a Workflow author, I want a write that would leave no terminal State refused, so that no Workflow becomes one a Run can never end.
70. As a Workflow author, I want an unknown key at the top level, in a State, or in `[answerer]` refused with the key, where it sits, and the keys allowed there, so that `questons = "human"` fails loudly instead of changing nothing.
71. As a Workflow author, I want `report = true` refused on a Gate State or a Terminal State, naming the State, so that I don't declare a second telling where one already happens.
72. As a Workflow author, I want `docs/workflow-authoring.md` to walk me from changing the starter, to building a Workflow from scratch, to kinds, slots, Prompt conventions and the file by hand, so that I learn by task rather than by schema.

### Reading the documentation

73. As an adopter, I want the README to open with the problem Naiad solves in two sentences and what it does in one, so that I know within a paragraph whether it's for me.
74. As an adopter, I want a short Concepts list and a four-bullet "How it works" in the README, with no citations I cannot open, so that I learn the words I will meet.
75. As an adopter, I want the README to list the manual uninstall steps, so that I can remove Naiad completely.
76. As an adopter, I want the README's Status section to say it is built on macOS, used by one person, works on Linux without desktop notifications, and tracks Claude Code's hook surface as of 2026, so that I know what I am adopting.
77. As an operator, I want `docs/running.md` to cover the queue, watching, Gates, Questions and the Answerer, reading Answers, notifications, `NAIAD_HOME`, Adoption, tmux, "What you can configure" and troubleshooting per doctor finding, so that day-to-day operation has one page.
78. As a curious adopter, I want `docs/how-it-works.md` to paraphrase the Protocol, the three hooks, Clears, Switches and the Belief, and why `bypassPermissions` is fixed, so that I understand the agent's side without reading the source.
79. As an adopter, I want `naiad <noun> --help` to be the command reference, so that the reference never drifts from the code.
80. As a maintainer, I want a test that parses every `naiad …` line in the shipped docs' fenced blocks against the real parser, so that a renamed verb breaks the build rather than the docs.

### Contributing and maintaining

81. As a contributor, I want `CONTRIBUTING.md` to ask for an issue before a non-trivial pull request, tests first and passing, and to say contributions come in under MIT and 0BSD with no CLA, so that I know the rules before I start.
82. As a contributor, I want the development setup (`uv sync`, `pytest`, `mypy`, the layout) and a note that tmux or Claude adapter changes need a manual Run, so that I can work on the code.
83. As a contributor's agent, I want `AGENTS.md` to state the Workflow-files rule for the starter with no pointer to a document I cannot open, so that the agent follows it.
84. As a contributor reading the code, I want every comment and docstring to state its rule inline instead of citing an ADR, a ticket, the glossary or a PRD, so that the code explains itself in the public checkout.
85. As the maintainer, I want the ADRs, glossary, tracker, agent docs and maintainer notes hidden through `.git/info/exclude` and removed from every past commit before release, so that adopters see a CLI and its documentation, not my working notes.
86. As the maintainer, I want the personal Workflow kept at `workflows/matt-pocock.toml`, tracked, 0BSD, unoffered, and reading `.matt-pocock.toml` instead of `naiad.toml`, so that my own Runs keep working and nothing suggests Naiad reads a project file.
87. As the maintainer, I want the shipped-workflow invariants to run over both the starter and the personal Workflow, so that neither file can drift into one a Run cannot start.
88. As the maintainer, I want publishing to go through a GitHub Actions workflow with PyPI trusted publishing behind an environment that needs my approval, so that no token lives anywhere and nothing publishes without me.
89. As an adopter reading the license, I want `LICENSE` to say the code is MIT and name the two 0BSD Workflow files, so that I know my copied starter owes nothing.

## Implementation Decisions

The decisions below come from the map's sixteen resolved tickets. Where a ticket gives the detail, the gist is here and the ticket is the reference. ADRs 0049, 0050, 0052, 0054, 0055, 0056 and 0057 are already written and stand as written. The glossary edits (Standing State, Report, Reserved Question widened, Gate State, Answer log, Companion repository removed) are already in `CONTEXT.md`.

### Packaging, naming and license

- The distribution is `naiad-cli` and the command stays `naiad`, with a static version of `0.1.0`. `pyproject.toml` gains `readme`, `license = "MIT AND 0BSD"`, `license-files` (both texts), `authors`, `classifiers` and `[project.urls]`, and the build requirement moves to `setuptools>=77`. The starter ships as package data inside the wheel. (Tickets 06, 07, 08.)
- The code is MIT, `Copyright (c) 2026 Janriz Libres`. The starter and `workflows/matt-pocock.toml` are 0BSD. `LICENSE` holds the MIT text and names the two 0BSD files, `LICENSES/0BSD.txt` holds the 0BSD text, and no SPDX header goes in either TOML file (ADR 0056).
- Publishing uses a GitHub Actions workflow triggered by a version tag. A build job runs the test suite and mypy, then `uv build`. A separate publish job has `id-token: write`, runs in the `pypi` environment with a required reviewer, and uses `pypa/gh-action-pypi-publish`. A pending publisher is registered on PyPI for `naiad-cli` before the first tag (research findings on branch `research/pypi-publishing`).
- **Decided here: one runtime dependency, a comment-preserving TOML writer (`tomlkit`).** The standard library reads TOML but cannot write it. The verbs must keep an author's comments, key order and multi-line Prompts, or the file stops being theirs to hand-edit. The starter's commented header would vanish on the first `set`. Reading for a Run still goes through the standard loader.

### The Workflow library and install

- The library is a store of regular files the adopter owns (ADR 0049). The checkout-relative shipped-workflows directory goes, along with symlinking shipped files, the copy refusal and its wording, and install's "no workflows directory" branch. The shipped file is read as a package resource.
- `naiad install --starter [--force]` copies the packaged starter into the library:
  - no file there: the starter is written;
  - a byte-identical file: it is rewritten;
  - a file that differs, or a symlink of that name: refused with "starter.toml differs from the shipped starter; pass --force or move it aside";
  - `--force`: overwrites.

  A bare `naiad install` never touches the library, and there is no interactive prompt.
- Hand-made symlinks remain valid entries. Verbs write through them. A dangling link is named as broken by the listing and by the resolver, never reported as a missing name.
- Install's hooks and skill targets default to `$CLAUDE_CONFIG_DIR/settings.json` and `$CLAUDE_CONFIG_DIR/skills` when the variable is set, and to `~/.claude/...` otherwise. The existing `--settings` and `--skills` flags keep working, and no new flags or Naiad variables are added. Claude Code's documentation confirms that both settings and personal skills move with `CLAUDE_CONFIG_DIR`: the "`.claude` directory" page says every `~/.claude` path lives under that directory instead. One function computes that default, and install and doctor both read it.
- After writing, install prints doctor's full report. Install's exit code is its own.

### The verb surface

- `naiad announce STATE [--subject S]` replaces the Protocol's `naiad state STATE`. The Protocol text, nudges, wait reminders, the Compaction reminder and the adopt skill all name the new verb through the one constant they already share. No alias is kept for `naiad state <name>`.
- `naiad workflow list | show WF | new NAME [--from WF] | rm WF | rename WF NEW | check WF | set WF KEY VALUE | unset WF KEY`.
- `naiad state list WF | show WF STATE | add WF STATE | rm WF STATE | rename WF STATE NEW | set WF STATE KEY VALUE | unset WF STATE KEY | move WF STATE (--after|--before) OTHER | next WF STATE [STATE ...] [--none] | set-prompt WF STATE`.
- `WF` is a library name or a path, decided by its shape exactly as the existing resolver decides it.
- **Key tables** drive `set` and `unset`, and `--help` prints each key's value shape:
  - file level: `model`, `effort`, `autocompact`, `answerer.model`, `answerer.effort`, `answerer.fallback`;
  - State level: `model`, `effort`, `clear`, `terminal`, `questions` (`answerer|human`), `report`.

  Values are validated from the table before any write. `unset` deletes the key, because absence means no opinion. `name`, `prompt` and `next` are verb-owned, and `set` refuses them, naming `rename`, `set-prompt` and `next`.
- **`state add`**:
  - It lands before the first terminal State unless `--after` or `--before` says otherwise. `--terminal` lands it at the end with no Prompt.
  - The Prompt source is one of: `$VISUAL`, then `$EDITOR`, by default; `--from FILE`; `--from -`; `--prompt TEXT`; or `--gate`.
  - With no editor set, it refuses in one sentence naming both remedies. An empty editor buffer changes nothing and says so.
  - `--clear`, `--model`, `--effort`, `--next` (repeatable), `--terminal` and `--auto` write their keys. `--auto` writes `questions = "answerer"`, and there is no human flag. Keys not given stay absent.
- **Order** is the declared order: a State without `next` hands over to the one declared after it. `add --after/--before` and `move` edit that path, and `next` edits the exceptions.
- **`state next`**: positionals replace the successors, and `--none` clears them. With no arguments it opens a numbered prompt from the standard library, listing the States with the current successors marked. Outside a terminal it refuses and names the list form.
- **`terminal` is settable**, and any write that leaves no terminal State is refused.
- **`workflow new`** scaffolds `name` and a terminal `done` in the library and refuses a name that already exists. `--from` copies a name or path and rewrites `name` to the new stem.
- **`workflow rm` and `workflow rename`** refuse while an Entry that is not done, or a live Run, addresses the file, naming each one. Paths are compared after resolving, so a link and its target count as one file. There is no `--force`; the remedy is `naiad queue rm`.
- **`state rename`** rewrites every `next` edge naming the State. **`state rm`** refuses while another State names it, naming those States. Neither refuses over a live Run, which keeps its recorded Standing State.
- **Every writing verb** validates, writes, reloads the file through the one load path, and restores the previous bytes if the reload fails, then reports the loader's error. Writes are atomic and go through symlinks to their targets.
- **Kind and marks** come from one renderer shared by `workflow show`, `state list`, `state show` and the existing `naiad states`, which stays as the adopt skill's reader:
  - the kind column says what Naiad does on entry: `prompt`, `gate` or `terminal`;
  - the marks follow it: `→ a, b` for successors, `clears`, `report`, `questions: human|answerer` (whose they are, resolved against the file's default), and the Model and Effort;
  - `workflow show` adds the file-level keys above the States, and `state show` adds the Prompt in full.
- The verb stub on branch `prototype/verb-surface` is a fixture for help wording only. It predates `--auto`, `report` and the `questions` polarity, and is not merged.

### The Workflow loader

- Unknown keys are refused at the top level (`name`, `model`, `effort`, `autocompact`, `answerer`, `states`), in a State (`name`, `prompt`, `clear`, `terminal`, `next`, `model`, `effort`, `questions`, `report`) and in `[answerer]` (`model`, `effort`, `fallback`). The refusal names the key, where it sits and the allowed keys. Every caller goes through the one load path. There is no version key. (Ticket 16.)
- A State's `questions` defaults to `"answerer"` when the file declares an `[answerer]` table and to `"human"` otherwise; the State's own key overrides either. The enum keeps its two members (ADR 0050).
- `report` is an optional boolean on a State, and is refused on a Gate State or a Terminal State, naming the State (ADR 0055).

### The engine

- **The Standing State is recorded at the start.** Kickoff and Adoption record the resolved start State's name on the Run, the first declared State when the Entry named none. The Standing State resolver reads that record, never the Workflow, so the Protocol, the Compaction reminder and the Queue listing give one answer. A Run with no recorded start and no Announcement has no Standing State. (Ticket 04.)
- **The Queue listing's line** is `id  status  state  repo  branch  task  (run)`:
  - The State column is padded to the longest State name in the listing, with no header row.
  - A waiting Entry shows `-`. A Run that has not announced shows its recorded start State. Otherwise the latest Announcement's State shows as recorded, with no mark for a Wait or a Question and no Subject.
  - Old Runs with no record show `-`.
- **Report**:
  - `Notification` gains `REPORT`, and the decision function gains a separate `Report` Action with its own Reports record, keyed like Notices, and a `reported` log kind. Neither the parked status nor the Belief's hand-off reads that kind.
  - It fires on the first Tick that sees an unhandled Announcement of a `report = true` State, before any Clear or Switch, without waiting for a turn end, once per Announcement.
  - Question Announcements and start States never report.
  - The message is `entered <state>` plus `: <subject>` when there is a Subject, and the title is `naiad: <run id>`. It goes down every leg, and ntfy maps `REPORT` to priority 2.
  - (ADR 0055.)
- **The Gate notification** appends `; next: <state>`, or the candidates joined as the Protocol joins them, taken from the successors resolved for the Gate. It adds no clause when nothing follows. (Ticket 14.)
- **The announce reply at a Gate.** The rule is decided by the same predicate that makes the decision function notify for a Gate, so a Gate a `--skip-gates` Run resolves past gets the plain reply. When Naiad will park on the announced Gate, the reply is: "`<gate>` is a Gate: a human takes it from here. End your turn and wait for them." It is followed, word for word, by the Protocol's expectation sentence: the single successor, "whichever applies" at a fork, or the nothing-expected sentence. Every other Announcement, Terminal included, keeps `announced X (n)`. Nothing is typed into the Session.
- **Reserved Question wording.** A Question the human takes because no table and no State key put it with the Answerer gets the reason "no Answerer is declared". 0046's "state X reserves its Questions for you" remains where a State asked for it. Both go into the notification ahead of the Question's text and into the Answer log's escalated entry.
- **An Answerer that cannot run** (no `claude`, or its launch fails) escalates with a sentence reason, "the Answerer could not be run: `claude` is not on PATH", instead of an exception text.
- **The Answer log** records, on each entry, the Standing State the Question was asked from. Entries written before this change read with no State.
- **The Answerer count.** When the Answerer answered at least once (escalations, human Questions and abandonments don't count), the Finish and Gate notifications add a line: `N answered by the Answerer — naiad queue answers <entry>`. The Run id stands in for a Run that has no Entry.

### The Run-facing verbs

- **`naiad queue answers <entry|run>`** takes a required argument, accepting an Entry id or a Run id.
  - An Entry that hasn't started says so. A Run with no Questions prints `no questions were asked in <run>`.
  - Otherwise it prints one numbered block per Question, with a blank line between blocks:
    - a first line with the number and the State;
    - the Question wrapped to the terminal width (80 when piped);
    - `options:`, one per line;
    - one outcome line, `→ answerer: <answer>`, `→ yours: <reason>` or `→ abandoned: <what the agent moved on to>`.
  - There is no colour and no `--json`. (Ticket 15.)
- **`naiad queue watch`** echoes `consulted` and `answered` as one line cut to the terminal width, dropping the options and keeping the answer's first clause. The Run log keeps the full detail.

### Doctor and the refusals

- **One set of checks, each with one severity, and two callers.** `naiad doctor` runs them all, prints one line per finding with its severity and remedy, repairs nothing, and exits 1 only when a check fails. The entrances (`run`, `watch`, `adopt`, and the Supervisor wherever it starts, including a `run` or `adopt` that becomes one) run the fail-level checks and stop at the first failure. The refusal is one line on stderr with exit 2: the missing thing, why Naiad needs it, the fix, then `naiad doctor`. `queue add`, Protocol verbs and hook verbs never check. (Ticket 13.)
- **fail:**
  - `tmux` on `PATH`;
  - `claude` on `PATH`;
  - `NAIAD_HOME` exists or can be created, and is writable;
  - the hooks are present in the `CLAUDE_CONFIG_DIR`-aware settings file;
  - the hooks name this `naiad`'s absolute path.
- **warn:**
  - `claude --version` is below the floor, or cannot be parsed ("could not tell");
  - the adopt skill is missing from the `CLAUDE_CONFIG_DIR`-aware skills directory;
  - a library entry does not load (broken link, bad TOML, or a check failure), naming the file;
  - a running tmux server's global `PATH` lacks `claude`. Only doctor runs this check.
- **info:**
  - the library is empty, pointing at `naiad install --starter`;
  - which notification legs will fire: the terminal always, the desktop where `osascript` exists, push when `NAIAD_NTFY_URL` is set.
- **Decided here: the version floor is Claude Code 2.1.221**, the release that added `--autocompact`, the newest of the flags Naiad can pass. `--permission-mode`, `--session-id`, `--model`, `--effort` and `--fallback-model` all predate it. The source is the Claude Code CLI reference, which says `--autocompact` "Requires Claude Code v2.1.221 or later". It is one constant.

### Configuration

- Nothing new is configurable (ADR 0057; ticket 12):
  - `bypassPermissions` stays fixed for Sessions and the Answerer;
  - every tuning constant stays a constant;
  - `NAIAD_HOME`, `NAIAD_NTFY_URL`, `NAIAD_NTFY_TOKEN` and `claude` on `PATH` are unchanged;
  - `CLAUDE_CONFIG_DIR` is read and never owned.

### The starter and the personal Workflow

- **The starter** is the draft on branch `prototype/starter-workflow`, moved to the package as `starter.toml`. It declares six States in a straight line: `plan` → `review` (Gate) → `implement` (Clear) → `verify` (Clear) → `ship` (Clear) → `done` (terminal). It uses `{task}` and `{branch}` in `plan` and `{next_state}` wherever a Prompt exists. It declares no settings, no `[answerer]` table and no `report`. Its commented header shows where `autocompact`, `model` and `effort` go. (Ticket 01.)
- **The personal Workflow** stays at `workflows/matt-pocock.toml`: tracked, 0BSD, never package data, never offered by install, and named in no adopter-facing document. Its `pull-request` Prompt reads `.matt-pocock.toml` instead of `naiad.toml` in both places it names the file. `naiad.toml` and any mention of a `naiad init` leave Naiad's documentation. (ADR 0052.)

### Documentation

- The set is `README.md`, `docs/running.md`, `docs/workflow-authoring.md` (rewritten task-first, with "Why the starter is shaped this way" and `report` explained on `ship`), `docs/how-it-works.md`, `CONTRIBUTING.md` and a trimmed `AGENTS.md`. The contents of each are as ticket 09 lists them, with the Gate wording from ticket 14 and "What you can configure" from ticket 12.
- There is no command reference and no `CHANGELOG.md`.
- The README's current `matt-pocock` example, its ADR citations and its Development section leave it. Development moves to `CONTRIBUTING.md`.

### The maintainer's record and the history

- `docs/adr/`, `CONTEXT.md`, `docs/agents/`, `docs/maintainer/` (renamed from `docs/smoke/`, holding `matt-pocock-smoke.md` and `matt-pocock-notes.md`), `.scratch/` and `CLAUDE.local.md` are hidden through `.git/info/exclude`, never `.gitignore`, and live only in the maintainer's checkout. `AGENTS.md`'s Agent-skills block moves to the untracked `CLAUDE.local.md`. (ADR 0054.)
- **Every tracked citation is restated inline.** That covers ADRs, `CONTEXT.md`, tickets, the PRD, `.scratch/` and `docs/smoke/`, in code, tests, `README.md`, `AGENTS.md` and `docs/workflow-authoring.md`: about 550 lines mention an ADR today. The shipped-workflow test's docstring loses its pointers.
- **At release, before the first publish:**
  - `git filter-repo` removes those paths from every commit;
  - a message callback rewords every commit message so it no longer cites an ADR, a ticket, the glossary or `.scratch`. An agent drafts the rewordings and the maintainer reviews them;
  - the local `research/*`, `prototype/*` and `worktree-agent-*` branches are dropped;
  - the GitHub repository `naiad-cli` is deleted, recreated and pushed.

  Until then it stays public as it is.

## Testing Decisions

- **The method is TDD** (Red → Green → Refactor) for every behaviour change here. A failing test is seen failing for the expected reason before code changes, and each unit ends with a named Refactor verdict.
- **A good test asserts external behaviour only**: exit status, what a command prints, what lands on disk, the Action the decision function returns, the error a load raises. It never asserts private helpers, call order, or the content of a shipped Workflow's Prompts. The shipped-workflow tests hold invariants, never content.
- **Seams, highest first, confirmed with the maintainer:**
  1. **The `naiad` command in-process**: `main(argv)` with `NAIAD_HOME` and `CLAUDE_CONFIG_DIR` pointed at temporary directories, asserting exit code, stdout, stderr and files. It covers:
     - every authoring verb, including rollback on a write the loader rejects, comments surviving a `set`, writing through a symlink, the in-use refusals, the editor and stdin sources, and the `next` picker's refusal outside a terminal;
     - `install --starter` and its refusal and `--force`;
     - the install targets under `CLAUDE_CONFIG_DIR`;
     - `queue list`'s State column;
     - `queue answers`;
     - `doctor` and the entrance refusals, with fake `tmux` and `claude` scripts on a temporary `PATH`. A fake `claude` prints a version below, at and above the floor, and one that doesn't parse;
     - the announce reply at a parking Gate, at a skipped Gate and at an ordinary State.

     Prior art: `test_states_command`, `test_queue_command`, `test_cli`, `test_library_install`, `test_announce_command`.
  2. **The decision function**, which is pure: the Report Action and its ordering before a Clear, no Report for a Question or a start State, the Gate notification's `next:` clause, both Reserved Question reasons, and the Answerer-count line on Finish and Gate. Prior art: `test_decide`.
  3. **The loop, a tick at a time with fake adapters**: the Reports record, the `reported` log line, a Report never parking the Run and never discarding the Belief, ntfy priority 2 for `REPORT`, the Standing State recorded at kickoff and Adoption, and the Answer log carrying the State. Prior art: `test_loop`, `test_ntfy`, `test_kickoff`, `test_answer_log`.
  4. **The loader** (`parse_workflow`): unknown keys at each level with the allowed list, `report` refused on Gate and Terminal States, and the `questions` default following the table. Prior art: `test_workflow`.
  5. **The shipped-workflow invariants**, parametrised over the packaged starter and `workflows/matt-pocock.toml`: loads under its own name, every slot fillable, every successor named, no "you just" after a Clear, every non-terminal State leads somewhere, and a Run can start from it. Prior art: `test_shipped_workflow`.
  6. **The docs drift test** (the one new seam). The parser is built by its own function instead of inside `main()`. The test collects every line starting `naiad ` in fenced blocks of `README.md`, `CONTRIBUTING.md` and `docs/*.md`, splits it shell-style, and parses it against that parser. Prose is not tested.
- **Existing tests move with the code.** The link-the-shipped-workflows tests are replaced by `--starter` tests, tests of `naiad state STATE` become tests of `naiad announce`, and test docstrings lose their citations.
- **Test runs follow the house rule**: capped workers, no coverage unless asked, one run at a time.
- **The QA plan** (manual, HITL, before the tag and again after the publish):
  1. On a machine or user with no Naiad, run `uv tool install` of the built wheel (after publishing, `uv tool install naiad-cli`), then `naiad install --starter`. Install's closing report shows no failures.
  2. Run `naiad doctor` with `tmux` removed from `PATH`: it gives the fail line and exit 1, and `naiad run` refuses with the one-line sentence.
  3. On a throwaway repository with a small test suite, run `naiad queue add starter "<task>" --repo .`, `naiad queue watch` and `tmux attach`. Answer the folder-trust dialog. At `review`:
     - the notification names `next: implement`;
     - `queue list` shows `parked  review`;
     - the agent's announce reply said a human takes it from here;
     - a sent "go ahead" moves the Run on with no State named.
  4. Watch the Run reach `done` through three confirmed Clears. `PLAN.md` is removed in its own commit, and there is a pull request when `gh` is authenticated, otherwise the branch.
  5. `naiad queue answers <entry>` prints `no questions were asked in <run>`.
  6. Repeat step 3 with `CLAUDE_CONFIG_DIR` set, to confirm the hooks fire from the relocated directory.
  7. Walk every command block in the README by hand once.

## Out of Scope

- A navigational documentation website. Markdown in the repository is this release's documentation.
- A `naiad done` Protocol verb replacing the terminal marker.
- The Queue listing naming the reason for a park beyond the Standing State.
- A watchable or confirm-before-send Answerer.
- A per-Run pull-request override.
- A per-project default Workflow, or any project file the engine reads.
- A Claude Code skill over the authoring verbs.
- A Workflow declaring the project keys its Prompts expect.
- A version key in the Workflow format.
- A session adapter other than tmux.
- Desktop notifications on Linux.
- State keys for the hang bound or the Wait budget.
- A settable permission mode, or per-Workflow tool allowlists.
- A `naiad uninstall` verb. The README documents the manual steps.
- A test send to each notification leg.
- Printing a sample Protocol for a named Workflow and State.
- A file-level `report` default or a file-level `questions` key.
- An arrow-key picker, and any dependency beyond the TOML writer.
- A PEP 541 claim on `naiad`.
- A changelog.
- A `--json` form of `queue answers`.
- A compatibility alias for `naiad state <name>`.

## Further Notes

- **Two decisions no ticket made, taken here:** the `tomlkit` runtime dependency, and doctor's exit code 1, as distinct from the refusals' 2. Ticket 13 said doctor exits non-zero only on a failure. Both are cheap to reverse.
- **Two open questions closed by research:** the version floor is 2.1.221, and personal skills do follow `CLAUDE_CONFIG_DIR`. Tickets 12 and 13 asked the spec to verify both.
- **Edge left as is:** renaming or removing a State under a waiting Entry that names it as its start State leaves that Entry to be refused at kickoff by the existing unknown-State path. Neither verb refuses over it, as ticket 04 anticipated edits under live work.
- **Ordering for `/to-tickets`:**
  - The loader changes (unknown keys, `questions` default, `report`) and the TOML writer come before the authoring verbs.
  - The rename to `naiad announce` comes before any documentation is written.
  - The citation rewrite can run in parallel with everything else, but has to finish before the history filter.
  - The release steps (untracking, filter, recreate, pending publisher, tag) are HITL, and come last.
- **Fixtures to absorb and then drop** at the history filter: the starter draft on `prototype/starter-workflow`, the verb stub on `prototype/verb-surface`, and the PyPI findings on `research/pypi-publishing`.
