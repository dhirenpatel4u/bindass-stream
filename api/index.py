
import os
from pathlib import Path

import httpx
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import FileResponse, StreamingResponse

app = FastAPI()

BASE_DIR = Path(__file__).resolve().parent.parent
VIDEO_URL = os.getenv("VIDEO_URL", "")


@app.get("/")
async def home():
    return FileResponse(BASE_DIR / "index.html")


@app.get("/api/stream")
async def stream(request: Request):
    if not VIDEO_URL.startswith("https://"):
        raise HTTPException(
            status_code=503,
            detail="VIDEO_URL is not configured"
        )

    headers = {"User-Agent": "Mozilla/5.0"}

    byte_range = request.headers.get("range")
    if byte_range:
        headers["Range"] = byte_range

    client = httpx.AsyncClient(
        follow_redirects=True,
        timeout=httpx.Timeout(60, connect=10)
    )

    try:
        upstream_request = client.build_request(
            "GET", VIDEO_URL, headers=headers
        )
        upstream = await client.send(
            upstream_request, stream=True
        )

        if upstream.status_code not in (200, 206, 416):
            status = upstream.status_code
            await upstream.aclose()
            await client.aclose()
            raise HTTPException(
                status_code=502,
                detail=f"Video source returned HTTP {status}"
            )

        forwarded = {}
        for name in (
            "content-type",
            "content-length",
            "content-range",
            "accept-ranges",
            "last-modified",
            "etag",
        ):
            if name in upstream.headers:
                forwarded[name] = upstream.headers[name]

        async def stream_body():
            try:
                async for chunk in upstream.aiter_raw():
                    yield chunk
            finally:
                await upstream.aclose()
                await client.aclose()

        return StreamingResponse(
            stream_body(),
            status_code=upstream.status_code,
            headers=forwarded,
            media_type=None
        )

    except httpx.HTTPError as exc:
        await client.aclose()
        raise HTTPException(
            status_code=502,
            detail="Unable to connect to video source"
        ) from exc
