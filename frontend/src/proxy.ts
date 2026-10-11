import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

import { hasTrustedRequestOrigin } from "./lib/security/origin";

export function proxy(request: NextRequest) {
  if (!hasTrustedRequestOrigin(request)) {
    return NextResponse.json(
      { detail: "Cross-origin request denied" },
      { status: 403, headers: { "Cache-Control": "no-store" } },
    );
  }

  return NextResponse.next();
}

export const config = {
  matcher: "/api/:path*",
};
