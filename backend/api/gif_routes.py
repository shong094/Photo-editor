"""GIF 製作相關的 HTTP 路由。"""
from __future__ import annotations

import base64
import binascii

from fastapi import APIRouter, HTTPException
from fastapi.concurrency import run_in_threadpool

from ..core import gif
from .schemas import GifRequest, GifResponse

router = APIRouter(prefix="/api/gif")


@router.get("/limits")
def limits() -> dict:
    """圖片數量、大小、顯示時間等限制，前端依此事先檢查。"""
    return gif.limits()


@router.post("", response_model=GifResponse)
async def create(req: GifRequest) -> GifResponse:
    try:
        frames = [
            gif.GifFrame(base64.b64decode(f.image, validate=True), f.duration)
            for f in req.frames
        ]
        result = await run_in_threadpool(gif.make_gif, frames, req.play_count, req.width)
    except binascii.Error as e:
        raise HTTPException(400, f"圖片資料格式錯誤：{e}")
    except ValueError as e:
        raise HTTPException(400, str(e))
    return GifResponse(
        gif=base64.b64encode(result.data).decode("ascii"),
        width=result.width, height=result.height, frame_count=result.frame_count,
    )
