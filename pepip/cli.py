"""Command-line interface for pepip.

This module defines the top-level and install subcommand parsers, routes
`pepip install` to the internal installer, and forwards all other commands to
`uv` so pepip can act as a drop-in CLI wrapper.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from pepip.installer import PEPIP_HOME, _uv_executable, install


def _build_root_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pepip",
        description=(
            "pepip — shared package store installer.\n\n"
            "Use `pepip install ...` to install packages into pepip's immutable "
            "shared store at %(pepip_home)s/packages and link them into the "
            "project-local virtual environment.\n"
            "All other commands are forwarded to `uv` unchanged so pepip can "
            "serve as a drop-in CLI replacement."
        )
        % {"pepip_home": PEPIP_HOME},
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  pepip install numpy pandas\n"
            "  pepip install -r requirements.txt --venv .venv\n"
            "  pepip sync --all\n"
            "  pepip run python -m pytest\n"
            "  pepip pip install '.[all]'"
        ),
    )
    return parser


def _build_install_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pepip install",
        description=(
            "Install one or more packages (or a requirements file) into the "
            "shared package store and create symlinks inside the project-local "
            ".venv directory."
        ),
    )
    parser.add_argument(
        "packages",
        nargs="*",
        metavar="PACKAGE",
        help="Package specifiers to install (e.g. 'numpy', 'pandas>=2.0', or '.[all]')",
    )
    parser.add_argument(
        "-r",
        "--requirements",
        metavar="FILE",
        help="Install packages listed in the given requirements file",
    )
    parser.add_argument(
        "--venv",
        metavar="PATH",
        default=".venv",
        help="Path to the project-local virtual environment (default: .venv)",
    )
    return parser


def _run_uv(args: list[str]) -> int:
    uv = _uv_executable()
    subprocess.run([uv, *args], check=True)
    return 0


def main(argv=None) -> int:
    """Entry point for the ``pepip`` command-line tool.

    Parameters
    ----------
    argv:
        Argument list (defaults to ``sys.argv[1:]``).

    Returns
    -------
    int
        Exit code (0 on success, non-zero on failure).
    """
    argv = list(sys.argv[1:] if argv is None else argv)
    root_parser = _build_root_parser()

    if not argv:
        root_parser.print_help()
        return 0

    if argv[0] in {"-h", "--help"}:
        root_parser.print_help()
        return 0

    if argv[0] == "install":
        parser = _build_install_parser()
        args = parser.parse_args(argv[1:])
        if not args.packages and not args.requirements:
            parser.parse_args(["--help"], namespace=None)
            # parse_args above will raise SystemExit via --help; this line is
            # a safety net in case that behaviour changes.
            return 1  # pragma: no cover

        try:
            linked_entries = install(
                packages=args.packages or None,
                requirements_file=args.requirements,
                local_venv=Path(args.venv),
            )
        except FileNotFoundError as exc:
            print(f"pepip: error: {exc}", file=sys.stderr)
            return 1
        except Exception as exc:  # noqa: BLE001
            print(f"pepip: error: {exc}", file=sys.stderr)
            return 1

        pkg_word = "entry" if len(linked_entries) == 1 else "entries"
        print(
            f"Successfully installed and linked {len(linked_entries)} "
            f"{pkg_word} into '{args.venv}'."
        )
        return 0

    try:
        return _run_uv(argv)
    except FileNotFoundError as exc:
        print(f"pepip: error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001
        print(f"pepip: error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
