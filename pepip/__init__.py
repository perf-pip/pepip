"""pepip — shared package-version store installer using symlinks."""

__version__ = "0.0.1"
__all__ = ["install"]

from pepip.installer import install

__doc__ = """
pepip installs resolved Python package versions into an immutable shared store
(``~/.pepip/packages``) using ``uv``, then creates symlinks inside the
project-local ``.venv`` directory so each project can activate its own
environment while reusing package files and uv's download cache.

Usage::

    pepip install numpy pandas
    pepip install -r requirements.txt
"""
