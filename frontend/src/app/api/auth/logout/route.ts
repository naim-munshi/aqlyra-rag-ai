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

  // A sleeping backend can make refresh throw before the local logout.
  // Explicit user sign-out must still clear every local auth cookie.
  let token: string | null = null;
  let sessionLookupFailed = false;
  try {
    token = await getAccessToken();
  } catch {
    sessionLookupFailed = true;
  }
  let revoked = !token && !sessionLookupFailed;

  if (token) {
    try {
      const response = await fetch(backendUrl("/auth/logout"), {
        method: "POST",
        headers: { Authorization: "Bearer " + token },
        cache: "no-store",
        signal: AbortSignal.timeout(8_000),
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
