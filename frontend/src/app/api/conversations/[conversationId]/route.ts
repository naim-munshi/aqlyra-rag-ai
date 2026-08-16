import { NextResponse } from "next/server";

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
      (await request.json()) as
        ConversationUpdateRequest;
  } catch {
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
