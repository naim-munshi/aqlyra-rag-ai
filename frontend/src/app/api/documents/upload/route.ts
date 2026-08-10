import { NextRequest, NextResponse } from "next/server";

import { backendUrl, readJson } from "@/lib/api/backend";
import { getAccessToken } from "@/lib/auth/session";
import type { DocumentResponse } from "@/types/document";

type ErrorResponse = {
  detail?: unknown;
};

export async function POST(request: NextRequest) {
  const accessToken = await getAccessToken();

  if (!accessToken) {
    return NextResponse.json(
      { detail: "Not authenticated" },
      { status: 401 },
    );
  }

  try {
    const incomingFormData = await request.formData();
    const file = incomingFormData.get("file");

    if (!(file instanceof File)) {
      return NextResponse.json(
        { detail: "Document file is required" },
        { status: 400 },
      );
    }

    const backendFormData = new FormData();
    backendFormData.append("file", file);

    const response = await fetch(
      backendUrl("/documents/upload"),
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${accessToken}`,
        },
        body: backendFormData,
        cache: "no-store",
      },
    );

    const data =
      await readJson<DocumentResponse | ErrorResponse>(
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
      { detail: "Unable to upload document" },
      { status: 502 },
    );
  }
}