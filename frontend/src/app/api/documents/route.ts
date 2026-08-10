import { NextResponse } from "next/server";

import { backendUrl, readJson } from "@/lib/api/backend";
import { getAccessToken } from "@/lib/auth/session";
import type { DocumentListResponse } from "@/types/document";

type ErrorResponse = {
  detail?: unknown;
};

export async function GET() {
  const accessToken = await getAccessToken();

  if (!accessToken) {
    return NextResponse.json(
      { detail: "Not authenticated" },
      { status: 401 },
    );
  }

  try {
    const response = await fetch(
      backendUrl("/documents?limit=100&offset=0"),
      {
        method: "GET",
        headers: {
          Authorization: `Bearer ${accessToken}`,
        },
        cache: "no-store",
      },
    );

    const data =
      await readJson<DocumentListResponse | ErrorResponse>(
        response,
      );

    return NextResponse.json(
      data ?? { detail: "Backend returned an invalid response" },
      {
        status: response.status,
      },
    );
  } catch {
    return NextResponse.json(
      { detail: "Unable to connect to backend" },
      { status: 502 },
    );
  }
}