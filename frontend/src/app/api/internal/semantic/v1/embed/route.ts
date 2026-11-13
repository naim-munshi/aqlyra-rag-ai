import { readBoundedJson, RequestBodyTooLargeError } from "@/lib/security/request-body";

// Opt-in backend-to-Vercel relay for the EXISTING authenticated Render worker.
// No worker secrets are stored here and the destination never comes from user input.
export const dynamic = "force-dynamic";
export const runtime = "nodejs";
export const maxDuration = 60;

const DESTINATION = "https://aqlyra-semantic-worker.onrender.com/v1/embed";
const NO_STORE = {
  "Cache-Control": "private, no-store, max-age=0",
  "X-Content-Type-Options": "nosniff",
};
const MAX_REQUEST_BYTES = 55_000;
const MAX_RESPONSE_BYTES = 250_000;

function jsonError(status: number, detail: string, retryAfter?: string) {
  const headers: Record<string, string> = { ...NO_STORE };
  if (retryAfter && /^\d{1,5}$/.test(retryAfter)) {
    headers["Retry-After"] = retryAfter;
  }
  return Response.json({ detail }, { status, headers });
}

export async function POST(request: Request) {
  // Forward only bounded bearer requests; the worker validates the actual
  // secret with constant-time comparison. No cookies or browser auth bypass.
  const authorization = request.headers.get("authorization") || "";
  if (!/^Bearer [A-Za-z0-9._~+/=-]{32,1024}$/.test(authorization)) {
    return jsonError(401, "Unauthorized");
  }
  if (request.headers.get("content-type")?.split(";")[0].trim().toLowerCase() !== "application/json") {
    return jsonError(415, "JSON body required");
  }

  let input: unknown;
  try {
    input = await readBoundedJson(request, MAX_REQUEST_BYTES);
  } catch (error) {
    return error instanceof RequestBodyTooLargeError
      ? jsonError(413, "Request body too large")
      : jsonError(400, "Invalid JSON body");
  }
  if (!input || typeof input !== "object" || Array.isArray(input)) {
    return jsonError(422, "Invalid embedding request");
  }
  const data = input as Record<string, unknown>;
  if (
    Object.keys(data).some((key) => key !== "mode" && key !== "texts") ||
    (data.mode !== "query" && data.mode !== "passage") ||
    !Array.isArray(data.texts) ||
    data.texts.length < 1 ||
    data.texts.length > 8 ||
    !data.texts.every(
      (text: unknown) => typeof text === "string" && text.trim().length > 0 && text.length <= 6000
    )
  ) {
    return jsonError(422, "Invalid embedding request");
  }

  try {
    const upstream = await fetch(DESTINATION, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: authorization,
      },
      body: JSON.stringify({ mode: data.mode, texts: data.texts }),
      cache: "no-store",
      redirect: "manual",
      signal: AbortSignal.timeout(55_000),
    });

    // Never echo upstream error bodies or arbitrary headers (which could
    // disclose worker internals). Let the existing 429 cooldown work.
    if (upstream.status !== 200) {
      const status = [401, 429, 503].includes(upstream.status)
        ? upstream.status : 502;
      return jsonError(
        status,
        "Semantic worker is unavailable",
        upstream.headers.get("retry-after") || undefined,
      );
    }
    const reportedLength = upstream.headers.get("content-length");
    if (
      reportedLength !== null &&
      (!Number.isSafeInteger(Number(reportedLength)) ||
        Number(reportedLength) > MAX_RESPONSE_BYTES)
    ) {
      return jsonError(502, "Invalid semantic response");
    }
    const payload = await upstream.arrayBuffer();
    if (payload.byteLength > MAX_RESPONSE_BYTES) {
      return jsonError(502, "Invalid semantic response");
    }
    return new Response(payload, {
      status: 200,
      headers: {
        ...NO_STORE,
        "Content-Type": "application/json",
      },
    });
  } catch {
    // Never leak private texts, bearer token, URL internals or body content.
    return jsonError(503, "Semantic worker is unavailable");
  }
}
