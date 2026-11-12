import { NextResponse } from "next/server";
import { hasTrustedRequestOrigin } from "@/lib/security/origin";

import { backendUrl } from "@/lib/api/backend";
import {
  clearAccessToken,
  clearRefreshToken,
  clearEmailVerificationToken,
  getAccessToken,
} from "@/lib/auth/session";

/** Revoke the JWT server-side, then always remove local cookies. */
export async function POST(request: Request) {
  if (!hasTrustedRequestOrigin(request)) {
    return NextResponse.json(
      { detail: "Untrusted request origin" },
      { status: 403, headers: { "Cache-Control": "private, no-store" } },
    );
  }

  const token = await getAccessToken();
  let revoked = !token;

  if (token) {
    try {
      const response = await fetch(backendUrl("/auth/logout"), {
        method: "POST",
        headers: { Authorization: "Bearer " + token },
        cache: "no-store",
      });
      revoked = response.ok || response.status === 401;
    } catch {
      revoked = false;
    }
  }

  await clearAccessToken();
  await clearRefreshToken();
  await clearEmailVerificationToken();

  return NextResponse.json(
    revoked
      ? { success: true }
      : { success: false, detail: "Signed out locally, but remote token revocation could not be confirmed." },
    { status: revoked ? 200 : 503, headers: { "Cache-Control": "no-store" } },
  );
}
