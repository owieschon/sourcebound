#!/usr/bin/env python3
"""Compatibility entry point for the packaged Version 0 pre-write policy."""

from sourcebound.write_gate import main


if __name__ == "__main__":
    raise SystemExit(main())
