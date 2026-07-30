"""Shell completion command definition and argparse-based candidates."""

from __future__ import annotations

import argparse
from argparse import Namespace
from collections.abc import Callable, Sequence


def add_completion_parser(
    subparsers: argparse._SubParsersAction,
) -> dict[str, argparse.ArgumentParser]:
    parser = subparsers.add_parser(
        "completion",
        help="shell completion script を出力します",
    )
    commands = parser.add_subparsers(dest="completion_shell", metavar="shell")
    commands.add_parser("bash", help="bash completion script を出力します")
    words_parser = commands.add_parser("words", help=argparse.SUPPRESS)
    words_parser.add_argument("--cword", type=int, required=True)
    words_parser.add_argument("words", nargs=argparse.REMAINDER)
    return {"completion": parser}


def run_completion_command(
    args: Namespace,
    *,
    root_parser_factory: Callable[[], argparse.ArgumentParser],
    help_parser: argparse.ArgumentParser,
) -> int:
    if args.completion_shell == "bash":
        print(completion_bash_script(), end="")
        return 0
    if args.completion_shell == "words":
        words = args.words[1:] if args.words[:1] == ["--"] else args.words
        print("\n".join(parser_completion_words(args.cword, words, root_parser_factory)))
        return 0
    help_parser.print_help()
    return 1


def completion_bash_script() -> str:
    return """# Gapless Agent Runtime bash completion.
if command -v register-python-argcomplete >/dev/null 2>&1 && python -c 'import argcomplete' >/dev/null 2>&1; then
  eval "$(register-python-argcomplete gar)"
else
  _gar_completion() {
    local IFS=$'\\n'
    COMPREPLY=($(COMP_LINE="$COMP_LINE" COMP_POINT="$COMP_POINT" "$1" completion words --cword "$COMP_CWORD" -- "${COMP_WORDS[@]}"))
  }
  complete -o nosort -F _gar_completion gar
fi
"""


def parser_completion_words(
    cword: int,
    words: Sequence[str],
    root_parser_factory: Callable[[], argparse.ArgumentParser],
) -> list[str]:
    """Return shell completion candidates from argparse parser structure."""

    parser = root_parser_factory()
    current = words[cword] if cword < len(words) else ""
    tokens = list(words[1:cword])

    index = 0
    while index < len(tokens):
        token = tokens[index]
        subparsers = _subparser_action(parser)
        if subparsers and token in subparsers.choices:
            parser = subparsers.choices[token]
            index += 1
            continue
        if token.startswith("-"):
            option_action = parser._option_string_actions.get(token)
            if option_action and option_action.nargs in (None, 1) and index + 1 < len(tokens):
                index += 2
                continue
        index += 1

    candidates = _parser_options(parser)
    subparsers = _subparser_action(parser)
    if subparsers:
        candidates.extend(subparsers.choices)

    return sorted(candidate for candidate in candidates if candidate.startswith(current))


def _subparser_action(parser: argparse.ArgumentParser) -> argparse._SubParsersAction | None:
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return action
    return None


def _parser_options(parser: argparse.ArgumentParser) -> list[str]:
    options: list[str] = []
    for action in parser._actions:
        options.extend(action.option_strings)
    return options
