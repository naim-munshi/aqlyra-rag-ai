import { createHash, createHmac } from "node:crypto";
import { isIP } from "node:net";
import { NextResponse } from "next/server";

import { backendUrl } from "@/lib/api/backend";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function POST(request: Request) {
  if (process.env.NEXT_PUBLIC_AQLYRA_GUEST_ENABLED !== "true") {
    return NextResponse.json(
      { ok: false },
      { status: 503, headers: { "Cache-Control": "private, no-store" } },
    );
  }
  const secret = process.env.GUEST_PROXY_SECRET;
  // Require the Vercel-authored client-IP header; never fall back to
  // arbitrary forwarded headers supplied along another ingress path.
  const clientIp = process.env.VERCEL === "1"
    ? request.headers.get("x-vercel-forwarded-for")
    : null;
  const noStore = { "Cache-Control": "private, no-store" };
  if (!secret || secret.length < 32 || !clientIp || isIP(clientIp) === 0) {
    return NextResponse.json({ ok: false }, { status: 503, headers: noStore });
  }
  const body = "{}";
  const timestamp = String(Math.floor(Date.now() / 1000));
  const digest = createHash("sha256").update(body).digest("hex");
  const signature = createHmac("sha256", secret)
    .update(timestamp + ":" + clientIp + ":" + digest)
    .digest("hex");
  try {
    const result = await fetch(backendUrl("/guest/visit"), {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Aqlyra-Guest-IP": clientIp,
        "X-Aqlyra-Guest-Timestamp": timestamp,
        "X-Aqlyra-Guest-Signature": signature,
      },
      body,
      cache: "no-store",
      signal: AbortSignal.timeout(8_000),
    });
    return NextResponse.json(
      { ok: result.ok },
      { status: result.ok ? 200 : result.status, headers: noStore },
    );
  } catch {
    return NextResponse.json({ ok: false }, { status: 503, headers: noStore });
  }
}
