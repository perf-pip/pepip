"""Command-line interface for pepip."""

from __future__ import annotations

import sys
from pathlib import Path

from pepip.installer import GLOBAL_VENV, install


def _build_parser():
    import argparse

    parser = argparse.ArgumentParser(
        prog="pepip",
        description=(
            "pepip — shared global environment package installer.\n\n"
            "Installs packages into a single global virtual environment "
            "(%(global_venv)s) using uv, then symlinks them into the "
            "project-local .venv so each project can activate its own "
            "environment while reusing already-downloaded packages."
        )
        % {"global_venv": GLOBAL_VENV},
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    subparsers = parser.add_subparsers(dest="command", metavar="<command>")

    # --- install -----------------------------------------------------------
    install_parser = subparsers.add_parser(
        "install",
        help="Install packages into the global env and link them into .venv",
        description=(
            "Install one or more packages (or a requirements file) into the "
            "shared global virtual environment and create symlinks inside the "
            "project-local .venv directory."
        ),
    )
    install_parser.add_argument(
        "packages",
        nargs="*",
        metavar="PACKAGE",
        help="Package specifiers to install (e.g. 'numpy' or 'pandas>=2.0')",
    )
    install_parser.add_argument(
        "-r",
        "--requirements",
        metavar="FILE",
        help="Install packages listed in the given requirements file",
    )
    install_parser.add_argument(
        "--venv",
        metavar="PATH",
        default=".venv",
        help="Path to the project-local virtual environment (default: .venv)",
    )

    return parser


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
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "install":
        if not args.packages and not args.requirements:
            _build_parser().parse_args(["install", "--help"], namespace=None)
            # parse_args above will raise SystemExit via --help; this line is
            # a safety net in case that behaviour changes.
            return 1  # pragma: no cover

        try:
            new_entries = install(
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

        pkg_word = "entry" if len(new_entries) == 1 else "entries"
        print(
            f"Successfully installed {len(new_entries)} new {pkg_word} "
            f"and linked them into '{args.venv}'."
        )
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
