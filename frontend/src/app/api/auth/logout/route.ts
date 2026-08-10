import { NextResponse } from "next/server";

import { clearAccessToken } from "@/lib/auth/session";

export async function POST() {
  await clearAccessToken();

  return NextResponse.json({
    success: true,
  });
}