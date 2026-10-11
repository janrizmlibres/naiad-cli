# 09 — `naiad doctor` and the refusals

Status: resolved
Mode: AFK
Blocked by: 04
Spec: [PRD](../PRD.md), "Doctor and the refusals"; map ticket [13](../issues/13-naiad-doctor-and-the-refusals.md)

**What to build:** One set of checks, each with one severity, used by two callers.

**`naiad doctor`** runs every check, prints one line per finding (severity, what, the command that fixes it), repairs nothing, and exits 1 only when a check fails.
- **fail:**
  - `tmux` on `PATH`;
  - `claude` on `PATH`;
  - `NAIAD_HOME` exists or can be created, and is writable;
  - the hooks are present in the `CLAUDE_CONFIG_DIR`-aware settings file;
  - the hooks name this `naiad`'s absolute path.
- **warn:**
  - `claude --version` is below the floor of 2.1.221, or cannot be parsed ("could not tell");
  - the adopt skill is missing from the `CLAUDE_CONFIG_DIR`-aware skills directory;
  - a library entry does not load, naming the file;
  - a running tmux server's global `PATH` lacks `claude` (doctor only).
- **info:**
  - the library is empty, pointing at `naiad install --starter`;
  - which notification legs will fire.

**`naiad install`** ends by printing doctor's report, and keeps its own exit code.

**The entrances** are `naiad run`, `naiad watch`, `naiad adopt`, and the Supervisor wherever it starts, including a `run` or `adopt` that becomes one. They run the fail-level checks and stop at the first failure with one line on stderr and exit 2: the missing thing, why Naiad needs it, the fix, then `naiad doctor`. `queue add`, the Protocol verbs and the hook verbs never check.

**An Answerer that cannot be run** escalates with the reason "the Answerer could not be run: `claude` is not on PATH" (or the launch failure in a sentence), instead of an exception text.

- [ ] With fake `tmux` and `claude` scripts on a temporary `PATH`, doctor reports each fail, warn and info case, and exits 1 only on a failure.
- [ ] A `claude` below 2.1.221, at it, above it, and unparseable give warn, nothing, nothing, and "could not tell".
- [ ] Each entrance refuses with the one-line sentence and exit 2 when `tmux` is missing. `queue add` still queues.
- [ ] `naiad install` prints the report after its own lines.
- [ ] An `ask` whose Answerer cannot launch parks the Run with the sentence reason.
- [ ] Built test-first, Refactor verdict recorded.
