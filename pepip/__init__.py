"""pepip — shared global environment package installer using symlinks."""

__version__ = "0.0.1"
__all__ = ["install"]

from pepip.installer import install

__doc__ = """
pepip installs Python packages into a single shared global virtual environment
(``~/.pepip/global-venv``) using ``uv``, then creates symlinks inside the
project-local ``.venv`` directory so each project can activate its own
environment while reusing already-downloaded packages.

Usage::

    pepip install numpy pandas
    pepip install -r requirements.txt
"""
