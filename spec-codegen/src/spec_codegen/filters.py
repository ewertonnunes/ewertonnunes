"""
Default Jinja filters registered on every Generator.

These solve the byte-stability issues we hit during the journey:
  - pynum:  renders 0.0 as "0" but 0.5 as "0.5", so spec floats can
            still be written as Python int-looking literals when whole.
  - shellesc: escape strings safely inside shell heredocs in templates.
"""
from __future__ import annotations

import shlex
from typing import Any

from jinja2 import Environment


def pynum(x: Any) -> str:
    """Render whole-number floats without trailing .0; everything else str()."""
    if isinstance(x, float) and x.is_integer():
        return str(int(x))
    return str(x)


def shellesc(x: Any) -> str:
    return shlex.quote(str(x))


def register_default_filters(env: Environment) -> None:
    env.filters["pynum"] = pynum
    env.filters["shellesc"] = shellesc
