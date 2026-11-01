
export const config = {
  runtime: "nodejs",
};

export default async function handler(req, res) {
  if (req.method !== "GET" && req.method !== "HEAD") {
    res.setHeader("Allow", "GET, HEAD");
    return res.status(405).end();
  }

  const videoUrl =
    "https://cdn2.ixifile.xyz/5/Tharki%20Buddha%20(2026)%20UnCut.mp4";

  try {
    const headers = {
      "User-Agent": "Mozilla/5.0",
      "Referer": "https://bindasmood.com/",
    };

    if (req.headers.range) {
      headers.Range = req.headers.range;
    }

    if (req.headers["if-range"]) {
      headers["If-Range"] = req.headers["if-range"];
    }

    const upstream = await fetch(videoUrl, {
      method: req.method,
      headers,
      redirect: "follow",
      signal: AbortSignal.timeout(25000),
    });

    res.status(upstream.status);

    for (const name of [
      "content-type",
      "content-length",
      "content-range",
      "accept-ranges",
      "last-modified",
      "etag",
    ]) {
      const value = upstream.headers.get(name);
      if (value) res.setHeader(name, value);
    }

    if (!upstream.ok && upstream.status !== 206) {
      await upstream.body?.cancel();
      return res.end("Upstream video request failed");
    }

    if (req.method === "HEAD" || !upstream.body) {
      await upstream.body?.cancel();
      return res.end();
    }

    req.on("close", () => {
      if (!res.writableEnded) {
        upstream.body?.cancel().catch(() => {});
      }
    });

    const reader = upstream.body.getReader();

    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        if (res.destroyed) {
          await reader.cancel();
          break;
        }

        if (!res.write(Buffer.from(value))) {
          await new Promise((resolve) =>
            res.once("drain", resolve)
          );
        }
      }

      if (!res.destroyed) res.end();
    } catch {
      if (!res.destroyed) res.destroy();
    }
  } catch (error) {
    if (!res.headersSent) {
      res.status(502).send("Video source unavailable");
    } else if (!res.destroyed) {
      res.destroy();
    }
  }
}
