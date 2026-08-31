#!/usr/bin/env python3
"""Compatibility entrypoint; use :mod:`tools.forward_sim_ports`."""

from __future__ import annotations

if __package__:
    from tools import forward_sim_ports as _implementation
else:  # Direct execution adds ``tools/`` to sys.path.
    import forward_sim_ports as _implementation

main = _implementation.main


def __getattr__(name: str):
    return getattr(_implementation, name)


if __name__ == "__main__":
    raise SystemExit(main())
