"""Command-line interface for pepip."""

from __future__ import annotations

import sys
from pathlib import Path

from pepip.installer import PEPIP_HOME, install


def _build_parser():
    import argparse

    parser = argparse.ArgumentParser(
        prog="pepip",
        description=(
            "pepip — shared package store installer.\n\n"
            "Installs resolved package versions into an immutable shared store "
            "(%(pepip_home)s/packages) using uv, then symlinks them into the "
            "project-local .venv so each project can activate its own "
            "environment while reusing packages."
        )
        % {"pepip_home": PEPIP_HOME},
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    subparsers = parser.add_subparsers(dest="command", metavar="<command>")

    # --- install -----------------------------------------------------------
    install_parser = subparsers.add_parser(
        "install",
        help="Install packages into the shared store and link them into .venv",
        description=(
            "Install one or more packages (or a requirements file) into the "
            "shared package store and create symlinks inside the project-local "
            ".venv directory."
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

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
