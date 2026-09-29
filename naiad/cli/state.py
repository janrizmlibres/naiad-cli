"""`naiad state`: authoring a Workflow's States without leaving the shell.

The noun is the author's alone. What an agent types to say where it is has its
own verb, `naiad announce`, so no State name is reserved here and the tree is a
plain one. Every verb that writes goes through `edit_workflow`, which validates
the result, writes it atomically and puts the previous bytes back if the file
would not load (naiad.runtime.workflow_file); a Prompt is gathered before that
call, so a session in the author's editor is never held open inside a write.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable
from pathlib import Path

from naiad.adapters.editor import EditorError, edit_text
from naiad.cli.library import LibraryError, resolve_workflow
from naiad.cli.picker import pick_states
from naiad.domain.key_table import (
    state_key_help,
    state_row,
    state_value,
)
from naiad.domain.listing import render_state, render_state_list
from naiad.domain.workflow import Workflow, WorkflowError, load_workflow
from naiad.runtime.home import StorageError, default_library_root
from naiad.runtime.state_file import (
    add_state,
    check_placeable,
    move_state,
    remove_state,
    rename_state,
    require_state,
    set_next,
    set_prompt,
    set_state_key,
    unset_state_key,
)
from naiad.runtime.workflow_file import edit_workflow

Handler = Callable[[argparse.Namespace], int]

# What an author reads on `set` and `unset` to learn which keys a State takes
# and what each accepts. `name`, `prompt` and `next` are absent because each
# has a verb of its own, and the refusal names it.
KEYS_HELP = (
    "keys (name, prompt and next have verbs of their own: rename, set-prompt, next):\n"
    + "\n".join(f"  {line}" for line in state_key_help().splitlines())
)

# Said where `add` and `set-prompt` name their sources, because the sentence an
# author needs when no editor is set is the one telling them what else there is.
PROMPT_SOURCES_HELP = (
    "the Prompt comes from $VISUAL, else $EDITOR, unless --from names a file "
    "(- for standard input) or --prompt gives it inline."
)


class PromptSourceError(Exception):
    """A Prompt the author pointed at that cannot be had."""


FAILURES = (LibraryError, WorkflowError, StorageError, EditorError, PromptSourceError)


def _refusing(action: Handler) -> Handler:
    """Every failure an author can cause, read as one line and exit 2."""

    def guarded(arguments: argparse.Namespace) -> int:
        try:
            return action(arguments)
        except FAILURES as error:
            print(f"naiad: {error}", file=sys.stderr)
            return 2

    return guarded


def _workflow_and_state(parser: argparse.ArgumentParser, *, state: bool = True) -> None:
    parser.add_argument(
        "workflow", help="path to the Workflow file, or the bare name of one in the library"
    )
    if state:
        parser.add_argument("state", metavar="STATE", help="the State's name")


def _prompt_sources(parser: argparse.ArgumentParser, *, gate: bool) -> None:
    sources = parser.add_mutually_exclusive_group()
    sources.add_argument(
        "--from",
        dest="prompt_file",
        metavar="FILE",
        help="read the Prompt from FILE, or from standard input with -",
    )
    sources.add_argument(
        "--prompt", dest="prompt_text", metavar="TEXT", help="the Prompt, given inline"
    )
    if gate:
        sources.add_argument(
            "--gate",
            action="store_true",
            help="no Prompt: Naiad delivers nothing and the human types",
        )


def add_state_commands(subcommands: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    state = subcommands.add_parser("state", help="author the States of a Workflow")
    verbs = state.add_subparsers(dest="state_command", required=True, metavar="VERB")

    listing = verbs.add_parser("list", help="a Workflow's States in declared order, with kinds")
    _workflow_and_state(listing, state=False)
    listing.set_defaults(handler=_refusing(_list))

    show = verbs.add_parser("show", help="one State: its line, and its Prompt in full")
    _workflow_and_state(show)
    show.set_defaults(handler=_refusing(_show))

    add = verbs.add_parser(
        "add",
        help="add a State, before the first terminal State unless placed otherwise",
        epilog=PROMPT_SOURCES_HELP + " Keys not given are left absent.",
    )
    _workflow_and_state(add)
    place = add.add_mutually_exclusive_group()
    place.add_argument("--after", metavar="STATE", help="place it after this State")
    place.add_argument("--before", metavar="STATE", help="place it before this State")
    _prompt_sources(add, gate=True)
    add.add_argument("--clear", action="store_true", help="enter it in a fresh context")
    add.add_argument("--model", help="the Model it asks for")
    add.add_argument("--effort", help="the Effort it asks for")
    add.add_argument(
        "--next",
        action="append",
        dest="successors",
        metavar="STATE",
        default=None,
        help="a successor; repeat for each, in order",
    )
    add.add_argument(
        "--terminal",
        action="store_true",
        help="make it end the Run: it lands at the end and takes no Prompt",
    )
    # The human answers a State's Questions unless the Workflow says otherwise
    # (ADR 0050), so opting in is the flag and the other polarity has none.
    add.add_argument(
        "--auto",
        action="store_true",
        help="let the Answerer take its Questions (writes questions = \"answerer\")",
    )
    add.set_defaults(handler=_refusing(_add))

    remove = verbs.add_parser(
        "rm", help="remove a State; refused while another State names it in `next`"
    )
    _workflow_and_state(remove)
    remove.set_defaults(handler=_refusing(_rm))

    rename = verbs.add_parser(
        "rename", help="rename a State, rewriting every `next` that names it"
    )
    _workflow_and_state(rename)
    rename.add_argument("new", help="the State's new name")
    rename.set_defaults(handler=_refusing(_rename))

    set_ = verbs.add_parser(
        "set",
        help="set one of a State's keys",
        epilog=KEYS_HELP,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    _workflow_and_state(set_)
    set_.add_argument("key", help="which key, from the table below")
    set_.add_argument("value", help="what to write, in the shape the table gives")
    set_.set_defaults(handler=_refusing(_set))

    unset = verbs.add_parser(
        "unset",
        help="delete one of a State's keys, leaving it with no opinion",
        epilog=KEYS_HELP,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    _workflow_and_state(unset)
    unset.add_argument("key", help="which key, from the table below")
    unset.set_defaults(handler=_refusing(_unset))

    move = verbs.add_parser("move", help="reorder a State")
    _workflow_and_state(move)
    where = move.add_mutually_exclusive_group(required=True)
    where.add_argument("--after", metavar="OTHER", help="place it after this State")
    where.add_argument("--before", metavar="OTHER", help="place it before this State")
    move.set_defaults(handler=_refusing(_move))

    successors = verbs.add_parser(
        "next",
        help="declare a State's successors, replacing the list; none given opens a picker",
    )
    _workflow_and_state(successors)
    successors.add_argument(
        "successors", metavar="SUCCESSOR", nargs="*", help="a successor; give them in order"
    )
    successors.add_argument("--none", action="store_true", help="clear the successors")
    successors.set_defaults(handler=_refusing(_next))

    prompt = verbs.add_parser(
        "set-prompt", help="replace a State's Prompt", epilog=PROMPT_SOURCES_HELP
    )
    _workflow_and_state(prompt)
    _prompt_sources(prompt, gate=False)
    prompt.set_defaults(handler=_refusing(_set_prompt))


def _path(arguments: argparse.Namespace) -> Path:
    """The file a verb that only writes acts on, resolved as the library resolves it."""
    return resolve_workflow(arguments.workflow, library=default_library_root())


def _position(workflow: Workflow, state: str) -> int:
    return [held.name for held in workflow.states].index(state) + 1


def _load(argument: str) -> tuple[Path, Workflow]:
    """The file an argument names, and what it holds, loaded the way a Run loads it."""
    path = resolve_workflow(argument, library=default_library_root())
    return path, load_workflow(path)


def _list(arguments: argparse.Namespace) -> int:
    print(render_state_list(_load(arguments.workflow)[1]))
    return 0


def _show(arguments: argparse.Namespace) -> int:
    workflow = _load(arguments.workflow)[1]
    print(render_state(workflow, require_state(workflow, arguments.state)))
    return 0


def _add(arguments: argparse.Namespace) -> int:
    path, workflow = _load(arguments.workflow)
    check_placeable(workflow, arguments.state, after=arguments.after, before=arguments.before)
    # The same check `set` makes, ahead of the editor: a key given to `add` is
    # held to what the key table accepts, not to whatever the shell passed.
    model = _checked("model", arguments.model)
    effort = _checked("effort", arguments.effort)

    prompt = None
    gives_a_prompt = arguments.prompt_file is not None or arguments.prompt_text is not None
    if arguments.terminal and gives_a_prompt:
        raise PromptSourceError(
            "a terminal State has no Prompt: drop --terminal, or drop --from and --prompt"
        )
    if not (arguments.gate or arguments.terminal):
        prompt = _prompt_from(arguments)
        if not prompt.strip():
            print(f"the Prompt is empty, so nothing was added to {path.stem}")
            return 0

    edited = edit_workflow(
        path,
        lambda document: add_state(
            document,
            arguments.state,
            prompt=prompt,
            terminal=arguments.terminal,
            clear=arguments.clear,
            model=model,
            effort=effort,
            questions="answerer" if arguments.auto else None,
            successors=arguments.successors or (),
            after=arguments.after,
            before=arguments.before,
        ),
    )
    print(f"{path.stem}: added {arguments.state} at position {_position(edited, arguments.state)}")
    return 0


def _checked(key: str, value: str | None) -> str | None:
    return None if value is None else str(state_value(key, value))


def _set_prompt(arguments: argparse.Namespace) -> int:
    path, workflow = _load(arguments.workflow)
    state = require_state(workflow, arguments.state)

    # A file ends on a newline, and an editor shows a buffer that lacks one as
    # damaged; the newline is dropped again when the Prompt is written.
    current = (state.prompt or "").rstrip("\n")
    prompt = _prompt_from(arguments, current=f"{current}\n" if current else "")
    if not prompt.strip():
        print(f"the Prompt is empty, so nothing was changed in {path.stem}")
        return 0

    edit_workflow(path, lambda document: set_prompt(document, state.name, prompt))
    print(f"{path.stem}/{state.name}: Prompt replaced")
    return 0


def _prompt_from(arguments: argparse.Namespace, *, current: str = "") -> str:
    """The Prompt the author gave: inline, from a file or standard input, or
    typed in their editor, which opens on `current` where there is one."""
    if arguments.prompt_text is not None:
        return str(arguments.prompt_text)
    if arguments.prompt_file == "-":
        return sys.stdin.read()
    if arguments.prompt_file is not None:
        try:
            return Path(arguments.prompt_file).read_text()
        except (OSError, UnicodeDecodeError) as error:
            reason = getattr(error, "strerror", None) or error
            raise PromptSourceError(f"cannot read {arguments.prompt_file} ({reason})") from error
    return edit_text(current)


def _set(arguments: argparse.Namespace) -> int:
    value = state_value(arguments.key, arguments.value)
    path = _path(arguments)
    edit_workflow(
        path, lambda document: set_state_key(document, arguments.state, arguments.key, value)
    )
    shown = str(value).lower() if isinstance(value, bool) else value
    print(f"{path.stem}/{arguments.state}: {arguments.key} = {shown}")
    return 0


def _unset(arguments: argparse.Namespace) -> int:
    state_row(arguments.key)
    path = _path(arguments)
    removed: list[bool] = []
    edit_workflow(
        path,
        lambda document: removed.append(
            unset_state_key(document, arguments.state, arguments.key)
        ),
    )
    said = "removed" if removed == [True] else "was not set"
    print(f"{path.stem}/{arguments.state}: {arguments.key} {said}")
    return 0


def _rename(arguments: argparse.Namespace) -> int:
    path = _path(arguments)
    edit_workflow(path, lambda document: rename_state(document, arguments.state, arguments.new))
    print(f"{path.stem}: renamed {arguments.state} to {arguments.new}")
    return 0


def _rm(arguments: argparse.Namespace) -> int:
    path = _path(arguments)
    edit_workflow(path, lambda document: remove_state(document, arguments.state))
    print(f"{path.stem}: removed {arguments.state}")
    return 0


def _move(arguments: argparse.Namespace) -> int:
    path = _path(arguments)
    edited = edit_workflow(
        path,
        lambda document: move_state(
            document, arguments.state, after=arguments.after, before=arguments.before
        ),
    )
    print(f"{path.stem}: moved {arguments.state} to position {_position(edited, arguments.state)}")
    return 0


def _next(arguments: argparse.Namespace) -> int:
    path, workflow = _load(arguments.workflow)
    state = require_state(workflow, arguments.state)
    successors = list(arguments.successors)
    if arguments.none and successors:
        raise WorkflowError("--none clears the successors: name States or pass --none, not both")

    if not successors and not arguments.none:
        if not (sys.stdin.isatty() and sys.stdout.isatty()):
            raise WorkflowError(
                "`naiad state next` with no States opens a picker, which needs a terminal; "
                f"list the successors instead: naiad state next {arguments.workflow} "
                f"{state.name} STATE [STATE ...]"
            )
        chosen = pick_states(
            state.name,
            [held.name for held in workflow.states],
            state.next_candidates,
        )
        if chosen is None:
            print(f"{path.stem}/{state.name}: successors left as they were")
            return 0
        successors = chosen

    edit_workflow(path, lambda document: set_next(document, state.name, successors))
    told = ", ".join(successors) if successors else "none"
    print(f"{path.stem}/{state.name}: next = {told}")
    return 0
