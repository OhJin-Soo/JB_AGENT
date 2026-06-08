from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import analyses, chat, history, reports
from app.core.database import init_database


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    init_database()
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="JB Agent",
        description="Cashflow forecasting, net-worth analysis, reporting, and chat APIs.",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.include_router(analyses.router)
    app.include_router(history.router)
    app.include_router(reports.router)
    app.include_router(chat.router)

    return app


app = create_app()
