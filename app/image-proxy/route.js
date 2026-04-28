const R2_PUBLIC_BASE_URL = "https://pub-7c46b568179e4640898dada0f351a0f2.r2.dev";
const R2_HOSTNAME = new URL(R2_PUBLIC_BASE_URL).hostname;
const CACHE_CONTROL = "public, max-age=86400, s-maxage=31536000, stale-while-revalidate=604800";

function targetImageUrl(src) {
  if (!src) {
    return null;
  }

  try {
    const url = new URL(src);
    if (url.protocol !== "https:" || url.hostname !== R2_HOSTNAME) {
      return null;
    }
    return url;
  } catch {
    return null;
  }
}

export async function GET(request) {
  const requestUrl = new URL(request.url);
  const targetUrl = targetImageUrl(requestUrl.searchParams.get("src"));

  if (!targetUrl) {
    return new Response("Invalid image URL", { status: 400 });
  }

  let upstream;
  try {
    upstream = await fetch(targetUrl, {
      headers: {
        Accept: request.headers.get("accept") || "image/*",
      },
      next: {
        revalidate: 31536000,
      },
    });
  } catch {
    return new Response("Image fetch failed", { status: 502 });
  }

  if (!upstream.ok) {
    return new Response("Image fetch failed", { status: upstream.status });
  }

  const contentType = upstream.headers.get("content-type") || "application/octet-stream";
  if (!contentType.startsWith("image/")) {
    return new Response("Unsupported image content", { status: 502 });
  }

  const headers = new Headers({
    "Cache-Control": CACHE_CONTROL,
    "Content-Type": contentType,
    "X-Content-Type-Options": "nosniff",
  });

  for (const headerName of ["content-length", "etag", "last-modified"]) {
    const value = upstream.headers.get(headerName);
    if (value) {
      headers.set(headerName, value);
    }
  }

  return new Response(upstream.body, {
    headers,
    status: 200,
  });
}
