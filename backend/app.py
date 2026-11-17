"""後端應用程式進入點。"""
from fastapi import FastAPI

from . import brushes, filters
from .api import brush_routes, gif_routes
from .api.routes import router


def create_app() -> FastAPI:
    filters.load_all()
    brushes.load_all()
    app = FastAPI(title="影像編輯軟體 API")
    app.include_router(router)
    app.include_router(brush_routes.router)
    app.include_router(gif_routes.router)
    return app


app = create_app()
