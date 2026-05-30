"""Allow `python -m cofound` to behave like the `cofound` console script."""

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
