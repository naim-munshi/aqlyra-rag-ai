import { NextResponse } from "next/server";
import { trustedProxyClientIp } from "@/lib/security/client-ip";

import { backendUrl, readJson } from "@/lib/api/backend";
import {
  clearEmailVerificationToken,
  setAccessToken,
  getEmailVerificationToken,
} from "@/lib/auth/session";

type ClaimBody = {
  code: string;
  username: string;
  new_password: string;
};

export async function POST(request: Request) {
  let body: ClaimBody;
  try {
    body = (await request.json()) as ClaimBody;
  } catch {
    return NextResponse.json({ detail: "Invalid request" }, { status: 400 });
  }

  const ticket = await getEmailVerificationToken();
  if (!ticket) {
    return NextResponse.json(
      { detail: "Request a new email verification code first." },
      { status: 400 },
    );
  }

  try {
    const headers = new Headers({ "Content-Type": "application/json" });
    const clientIp = trustedProxyClientIp(request);
    if (clientIp) headers.set("X-Aqlyra-Client-IP", clientIp);
    const response = await fetch(backendUrl("/auth/claim-pending-email"), {
      method: "POST",
      headers,
      body: JSON.stringify({ ...body, verification_token: ticket }),
      cache: "no-store",
    });
    const data = await readJson<{ access_token?: string; detail?: string }>(
      response,
    );
    if (!response.ok || !data?.access_token) {
      return NextResponse.json(
        { detail: data?.detail ?? "Unable to verify ownership." },
        { status: response.status === 200 ? 502 : response.status },
      );
    }

    await setAccessToken(data.access_token);
    await clearEmailVerificationToken();
    return NextResponse.json({ success: true }, {
      headers: { "Cache-Control": "no-store" },
    });
  } catch {
    return NextResponse.json(
      { detail: "Aqlyra authentication is unavailable." },
      { status: 502 },
    );
  }
}
