
import os
import httpx
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse, Response

app = FastAPI()

# Set this environment variable in Vercel.
VIDEO_URL = os.environ.get("VIDEO_URL", "")


@app.get("/stream")
async def stream_video(request: Request):
    if not VIDEO_URL.startswith("https://"):
        raise HTTPException(
            status_code=503,
            detail="Configure an authorized HTTPS VIDEO_URL"
        )

    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    # Preserve browser seeking requests.
    range_header = request.headers.get("range")
    if range_header:
        headers["Range"] = range_header

    client = httpx.AsyncClient(
        follow_redirects=True,
        timeout=httpx.Timeout(60.0, connect=10.0)
    )

    try:
        upstream_request = client.build_request(
            "GET", VIDEO_URL, headers=headers
        )
        upstream = await client.send(
            upstream_request, stream=True
        )

        if upstream.status_code not in (200, 206, 416):
            await upstream.aclose()
            await client.aclose()
            raise HTTPException(
                status_code=502,
                detail=f"Upstream returned HTTP {upstream.status_code}"
            )

        response_headers = {}
        for name in (
            "content-type",
            "content-length",
            "content-range",
            "accept-ranges",
            "last-modified",
            "etag",
        ):
            if name in upstream.headers:
                response_headers[name] = upstream.headers[name]

        async def body():
            try:
                async for chunk in upstream.aiter_bytes():
                    yield chunk
            finally:
                await upstream.aclose()
                await client.aclose()

        return StreamingResponse(
            body(),
            status_code=upstream.status_code,
            headers=response_headers,
            media_type=upstream.headers.get(
                "content-type", "video/mp4"
            ),
        )

    except httpx.HTTPError:
        await client.aclose()
        raise HTTPException(
            status_code=502,
            detail="Unable to connect to the video source"
        )
