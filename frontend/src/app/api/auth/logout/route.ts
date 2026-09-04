import { NextResponse } from "next/server";

import {
  clearAccessToken,
  clearEmailVerificationToken,
} from "@/lib/auth/session";

export async function POST() {
  await clearAccessToken();
  await clearEmailVerificationToken();

  return NextResponse.json({
    success: true,
  });
}
