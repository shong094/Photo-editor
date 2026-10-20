"""後端應用程式進入點。"""
from fastapi import FastAPI

from . import filters
from .api.routes import router


def create_app() -> FastAPI:
    filters.load_all()
    app = FastAPI(title="影像編輯軟體 API")
    app.include_router(router)
    return app


app = create_app()
