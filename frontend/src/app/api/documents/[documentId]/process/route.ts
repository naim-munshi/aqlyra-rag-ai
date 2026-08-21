import { NextResponse } from "next/server";

import { backendUrl, readJson } from "@/lib/api/backend";
import { forwardedBackendHeaders } from "@/lib/api/response-headers";
import { getAccessToken } from "@/lib/auth/session";
import type { DocumentResponse } from "@/types/document";

type ErrorResponse = {
  detail?: unknown;
};

type RouteContext = {
  params: Promise<{
    documentId: string;
  }>;
};

export async function POST(
  _request: Request,
  context: RouteContext,
) {
  const accessToken = await getAccessToken();

  if (!accessToken) {
    return NextResponse.json(
      { detail: "Not authenticated" },
      { status: 401 },
    );
  }

  const { documentId } = await context.params;

  try {
    const response = await fetch(
      backendUrl(
        `/documents/${encodeURIComponent(documentId)}/process`,
      ),
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${accessToken}`,
        },
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
        headers:
          forwardedBackendHeaders(
            response,
          ),
      },
    );
  } catch {
    return NextResponse.json(
      { detail: "Unable to process document" },
      { status: 502 },
    );
  }
}