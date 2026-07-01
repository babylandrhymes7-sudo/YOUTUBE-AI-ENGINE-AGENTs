"""Application entry point.

TODO: Expose the FastAPI application object and lifespan events from this module.
"""

from __future__ import annotations

from .startup import bootstrap_runtime


def main() -> dict[str, str | int]:
    """Run the local bootstrap sequence and return its startup context."""

    return bootstrap_runtime()


if __name__ == "__main__":
    print(main())

