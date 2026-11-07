import { NextResponse } from "next/server";
import { hasTrustedRequestOrigin } from "@/lib/security/origin";
import { readBoundedJson, RequestBodyTooLargeError } from "@/lib/security/request-body";

import {
  backendUrl,
  readJson,
} from "@/lib/api/backend";
import {
  getAccessToken,
} from "@/lib/auth/session";
import type {
  ConversationResponse,
} from "@/types/conversation";

type ApiError = {
  detail?: unknown;
};

type ConversationUpdateRequest = {
  title?: string;
  is_pinned?: boolean;
  project_id?: string | null;
};

type RouteContext = {
  params: Promise<{
    conversationId: string;
  }>;
};

export async function PATCH(
  request: Request,
  context: RouteContext,
) {
  if (!hasTrustedRequestOrigin(request)) {
    return NextResponse.json({ detail: "Cross-origin request denied" }, {
      status: 403, headers: { "Cache-Control": "private, no-store" },
    });
  }
  const accessToken =
    await getAccessToken();

  if (!accessToken) {
    return NextResponse.json(
      { detail: "Not authenticated" },
      { status: 401 },
    );
  }

  const { conversationId } =
    await context.params;

  let body: ConversationUpdateRequest;

  try {
    body =
      (await readBoundedJson(request, 16_384)) as
        ConversationUpdateRequest;
  } catch (error) {
    if (error instanceof RequestBodyTooLargeError) {
      return NextResponse.json({ detail: "Request body too large" }, {
        status: 413, headers: { "Cache-Control": "private, no-store" },
      });
    }
    return NextResponse.json(
      { detail: "Invalid request body" },
      { status: 400 },
    );
  }

  try {
    const response = await fetch(
      backendUrl(
        `/conversations/${encodeURIComponent(
          conversationId,
        )}`,
      ),
      {
        method: "PATCH",
        headers: {
          "Content-Type":
            "application/json",
          Authorization:
            `Bearer ${accessToken}`,
        },
        body: JSON.stringify(body),
        cache: "no-store",
      },
    );

    const data =
      await readJson<
        ConversationResponse | ApiError
      >(response);

    return NextResponse.json(
      data ?? {
        detail:
          "Backend returned an invalid response",
      },
      {
        status: response.status,
      },
    );
  } catch {
    return NextResponse.json(
      {
        detail:
          "Unable to update conversation",
      },
      {
        status: 502,
      },
    );
  }
}



export async function DELETE(
  request: Request,
  context: RouteContext,
) {
  if (!hasTrustedRequestOrigin(request)) {
    return NextResponse.json({ detail: "Cross-origin request denied" }, {
      status: 403, headers: { "Cache-Control": "private, no-store" },
    });
  }
  const accessToken =
    await getAccessToken();

  if (!accessToken) {
    return NextResponse.json(
      { detail: "Not authenticated" },
      { status: 401 },
    );
  }

  const { conversationId } =
    await context.params;

  try {
    const response = await fetch(
      backendUrl(
        `/conversations/${encodeURIComponent(
          conversationId,
        )}`,
      ),
      {
        method: "DELETE",
        headers: {
          Authorization:
            `Bearer ${accessToken}`,
        },
        cache: "no-store",
      },
    );

    if (response.status === 204) {
      return new Response(
        null,
        {
          status: 204,
        },
      );
    }

    const data =
      await readJson<ApiError>(
        response,
      );

    return NextResponse.json(
      data ?? {
        detail:
          "Backend returned an invalid response",
      },
      {
        status: response.status,
      },
    );
  } catch {
    return NextResponse.json(
      {
        detail:
          "Unable to delete conversation",
      },
      {
        status: 502,
      },
    );
  }
}
