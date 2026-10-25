
import os
from pathlib import Path
from urllib.parse import urlparse

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse

app = FastAPI()


def get_video_url():
    return os.getenv("VIDEO_URL", "").strip()


@app.get("/")
async def home():
    file_path = Path(__file__).resolve().parent.parent / "index.html"

    if not file_path.is_file():
        raise HTTPException(
            status_code=404,
            detail="index.html not found"
        )

    return FileResponse(file_path)


@app.get("/api/")
async def api_status():
    return {
        "status": "API running",
        "endpoints": [
            "/api/check-config",
            "/api/stream"
        ]
    }


@app.get("/api/check-config")
async def check_config():
    url = get_video_url()
    parsed = urlparse(url) if url else None

    return {
        "video_url_configured": bool(url),
        "https_url": bool(parsed and parsed.scheme == "https"),
        "hostname": parsed.hostname if parsed else None,
        "url_length": len(url)
    }


@app.get("/api/stream")
async def stream_video(request: Request):
    video_url = get_video_url()
    parsed = urlparse(video_url) if video_url else None

    if (
        not parsed
        or parsed.scheme != "https"
        or not parsed.hostname
    ):
        raise HTTPException(
            status_code=503,
            detail="VIDEO_URL is missing or invalid"
        )

    # Forward the browser's byte-range request.
    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    requested_range = request.headers.get("range")
    if requested_range:
        headers["Range"] = requested_range

    timeout = httpx.Timeout(
        60.0,
        connect=10.0
    )

    client = httpx.AsyncClient(
        follow_redirects=True,
        timeout=timeout
    )

    try:
        upstream_request = client.build_request(
            "GET",
            video_url,
            headers=headers
        )

        upstream = await client.send(
            upstream_request,
            stream=True
        )

    except httpx.HTTPError:
        await client.aclose()

        raise HTTPException(
            status_code=502,
            detail="Could not connect to the upstream video source"
        )

    if upstream.status_code not in (200, 206, 416):
        status = upstream.status_code
        content_type = upstream.headers.get(
            "content-type",
            "unknown"
        )

        await upstream.aclose()
        await client.aclose()

        raise HTTPException(
            status_code=502,
            detail={
                "message": "Upstream video request failed",
                "upstream_status": status,
                "upstream_content_type": content_type,
                "hint": "Check the source host's access policy"
            }
        )

    response_headers = {}

    for name in (
        "content-type",
        "content-length",
        "content-range",
        "accept-ranges",
        "last-modified",
        "etag"
    ):
        value = upstream.headers.get(name)
        if value is not None:
            response_headers[name] = value

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
        headers=response_headers
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8000
    )
