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
          redirect: "manual",
        },
      );

    // Only forward a backend-authorized, short-lived private Neon S3 link.
    // Never follow it server-side: Vercel's Function payload is limited,
    // and a 25 MB file must transfer directly to the authenticated browser.
    if (response.status === 307) {
      const destination = response.headers.get("location");
      if (!destination) {
        return NextResponse.json(
          { detail: "Private document link unavailable" },
          { status: 502, headers: { "Cache-Control": "private, no-store" } },
        );
      }
      let target: URL;
      try {
        target = new URL(destination);
      } catch {
        return NextResponse.json(
          { detail: "Invalid private document link" },
          { status: 502 },
        );
      }
      if (
        target.protocol !== "https:" ||
        !target.hostname.endsWith(".aws.neon.tech") ||
        target.username || target.password || target.port
      ) {
        return NextResponse.json(
          { detail: "Invalid private document destination" },
          { status: 502 },
        );
      }
      return NextResponse.redirect(target, {
        status: 307,
        headers: {
          "Cache-Control": "private, no-store",
          "Referrer-Policy": "no-referrer",
          "X-Content-Type-Options": "nosniff",
        },
      });
    }

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
