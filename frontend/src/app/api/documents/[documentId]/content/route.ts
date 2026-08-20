import { NextResponse } from "next/server";

import {
  backendUrl,
  readJson,
} from "@/lib/api/backend";
import {
  getAccessToken,
} from "@/lib/auth/session";


type ApiError = {
  detail?: unknown;
};

type RouteContext = {
  params: Promise<{
    documentId: string;
  }>;
};


export async function GET(
  _request: Request,
  context: RouteContext,
) {
  const accessToken =
    await getAccessToken();

  if (!accessToken) {
    return NextResponse.json(
      {
        detail:
          "Not authenticated",
      },
      {
        status: 401,
      },
    );
  }

  const { documentId } =
    await context.params;

  try {
    const response =
      await fetch(
        backendUrl(
          `/documents/${encodeURIComponent(
            documentId,
          )}/content`,
        ),
        {
          headers: {
            Authorization:
              `Bearer ${accessToken}`,
          },
          cache: "no-store",
        },
      );

    if (!response.ok) {
      const data =
        await readJson<ApiError>(
          response,
        );

      return NextResponse.json(
        data ?? {
          detail:
            "Unable to load document content",
        },
        {
          status: response.status,
        },
      );
    }

    const headers =
      new Headers();

    const contentType =
      response.headers.get(
        "content-type",
      );

    const contentLength =
      response.headers.get(
        "content-length",
      );

    const contentDisposition =
      response.headers.get(
        "content-disposition",
      );

    if (contentType) {
      headers.set(
        "Content-Type",
        contentType,
      );
    }

    if (contentLength) {
      headers.set(
        "Content-Length",
        contentLength,
      );
    }

    if (contentDisposition) {
      headers.set(
        "Content-Disposition",
        contentDisposition,
      );
    }

    headers.set(
      "Cache-Control",
      "private, no-store",
    );

    return new Response(
      response.body,
      {
        status: 200,
        headers,
      },
    );
  } catch {
    return NextResponse.json(
      {
        detail:
          "Unable to load document content",
      },
      {
        status: 502,
      },
    );
  }
}
