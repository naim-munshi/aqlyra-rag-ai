import { createHash, createHmac } from "node:crypto";
import { isIP } from "node:net";
import { NextResponse } from "next/server";

import { backendUrl } from "@/lib/api/backend";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const headers = { "Cache-Control": "private, no-store" };
const maxBodyBytes = 4500;

export async function POST(request: Request) {
  // Never trust browser-supplied IP values or expose the signing key.
  // Vercel overwrites X-Forwarded-For at its own ingress.
  const secret = process.env.GUEST_PROXY_SECRET;
  const clientIp = process.env.VERCEL === "1"
    ? request.headers.get("x-vercel-forwarded-for") ??
      request.headers.get("x-forwarded-for")
    : null;
  if (!secret || secret.length < 32 || !clientIp || isIP(clientIp) === 0) {
    return NextResponse.json(
      { detail: "Guest chat is not available yet" },
      { status: 503, headers },
    );
  }
  let body: string;
  try {
    body = await request.text();
    if (Buffer.byteLength(body, "utf8") > maxBodyBytes) {
      return NextResponse.json(
        { detail: "Guest message is too long" },
        { status: 413, headers },
      );
    }
    JSON.parse(body);
  } catch {
    return NextResponse.json(
      { detail: "Invalid request body" },
      { status: 400, headers },
    );
  }
  const timestamp = String(Math.floor(Date.now() / 1000));
  const digest = createHash("sha256").update(body).digest("hex");
  const signature = createHmac("sha256", secret)
    .update(timestamp + ":" + clientIp + ":" + digest)
    .digest("hex");
  try {
    const upstream = await fetch(backendUrl("/guest/chat"), {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Aqlyra-Guest-IP": clientIp,
        "X-Aqlyra-Guest-Timestamp": timestamp,
        "X-Aqlyra-Guest-Signature": signature,
      },
      body,
      cache: "no-store",
      signal: AbortSignal.timeout(20_000),
    });
    const data = await upstream.json().catch(() => ({
      detail: "Guest service is temporarily unavailable",
    }));
    const upstreamHeaders = new Headers(headers);
    const retryAfter = upstream.headers.get("retry-after");
    if (retryAfter) upstreamHeaders.set("Retry-After", retryAfter);
    return NextResponse.json(data, {
      status: upstream.status, headers: upstreamHeaders,
    });
  } catch {
    return NextResponse.json(
      { detail: "Guest service is temporarily unavailable" },
      { status: 503, headers },
    );
  }
}
