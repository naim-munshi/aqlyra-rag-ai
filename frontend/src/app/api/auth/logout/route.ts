import { NextResponse } from "next/server";

import { backendUrl } from "@/lib/api/backend";
import {
  clearAccessToken,
  clearEmailVerificationToken,
  getAccessToken,
} from "@/lib/auth/session";

/** Revoke the JWT server-side, then always remove local cookies. */
export async function POST() {
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
  await clearEmailVerificationToken();

  return NextResponse.json(
    revoked
      ? { success: true }
      : { success: false, detail: "Signed out locally, but remote token revocation could not be confirmed." },
    { status: revoked ? 200 : 503, headers: { "Cache-Control": "no-store" } },
  );
}
