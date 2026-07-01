"""Application entry point for the local FastAPI runtime."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI

from api.news import router as news_router
from api.reports import router as reports_router

from .startup import bootstrap_runtime


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Prepare local storage and validate local-only runtime settings."""

    bootstrap_runtime()
    yield


app = FastAPI(title="YOUTUBE AI AGENT", lifespan=lifespan)
app.include_router(news_router)
app.include_router(reports_router)


@app.get("/health")
def health() -> dict[str, str]:
    """Return a lightweight local health check."""

    return {"status": "ok"}


def main() -> dict[str, str | int]:
    """Run the local bootstrap sequence and return its startup context."""

    return bootstrap_runtime()


if __name__ == "__main__":
    print(main())
