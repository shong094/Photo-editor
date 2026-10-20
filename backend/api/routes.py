"""HTTP 路由。"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.concurrency import run_in_threadpool

from ..core.image_io import decode_image, encode_image
from ..core.registry import get_filter, list_filters
from ..core.roi import Rect, apply_filter
from .schemas import ProcessRequest, ProcessResponse

router = APIRouter(prefix="/api")


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/filters")
def filters() -> list[dict]:
    """列出所有功能及其參數規格，前端依此動態產生介面。"""
    return [f.describe() for f in list_filters()]


@router.post("/filters/{name}", response_model=ProcessResponse)
async def process(name: str, req: ProcessRequest) -> ProcessResponse:
    try:
        flt = get_filter(name)
    except KeyError as e:
        raise HTTPException(404, e.args[0])

    try:
        params = flt.validate_params(req.params)
        image = decode_image(req.image)
        roi = Rect(**req.roi.model_dump()) if req.roi else None
        result = await run_in_threadpool(apply_filter, image, flt, params, roi)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return ProcessResponse(image=encode_image(result))
