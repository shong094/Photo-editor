"""筆刷相關的 HTTP 路由。"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.concurrency import run_in_threadpool

from ..core.brush import brushes, paint_stroke
from ..core.image_io import decode_image, encode_image
from .schemas import StrokeRequest, StrokeResponse

router = APIRouter(prefix="/api/brushes")


@router.get("")
def list_brushes() -> list[dict]:
    """列出所有筆刷，前端依此產生筆刷選項。"""
    return [b.describe() for b in brushes.all()]


@router.post("/{name}/stroke", response_model=StrokeResponse)
async def stroke(name: str, req: StrokeRequest) -> StrokeResponse:
    try:
        brush = brushes.get(name)
    except KeyError as e:
        raise HTTPException(404, e.args[0])

    color = tuple(int(req.color[i : i + 2], 16) for i in (1, 3, 5)) if req.color else None
    try:
        image = decode_image(req.image)
        source = decode_image(req.source) if req.source else None
        result = await run_in_threadpool(
            paint_stroke, image, brush, req.points, req.size, color, req.opacity, req.seed, source
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    return StrokeResponse(image=encode_image(result))
