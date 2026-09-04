import { NextResponse } from "next/server";

import {
  backendUrl,
  readJson,
} from "@/lib/api/backend";
import {
  getAccessToken,
} from "@/lib/auth/session";
import type {
  ConversationMode,
  ConversationResponse,
} from "@/types/conversation";

type ApiError = {
  detail?: unknown;
};

type ConversationCreateRequest = {
  title?: string;
  mode?: ConversationMode;
  project_id?: string | null;
};

export async function GET() {
  const accessToken =
    await getAccessToken();

  if (!accessToken) {
    return NextResponse.json(
      { detail: "Not authenticated" },
      { status: 401 },
    );
  }

  const pageSize = 100;
  const allConversations: ConversationResponse[] = [];
  let offset = 0;

  try {
    while (true) {
      const response = await fetch(
        backendUrl(
          `/conversations?limit=${pageSize}&offset=${offset}`,
        ),
        {
          method: "GET",
          headers: {
            Authorization:
              `Bearer ${accessToken}`,
          },
          cache: "no-store",
        },
      );

      const data =
        await readJson<
          ConversationResponse[] | ApiError
        >(response);

      if (!response.ok) {
        return NextResponse.json(
          data ?? {
            detail:
              "Backend returned an invalid response",
          },
          {
            status: response.status,
          },
        );
      }

      if (!Array.isArray(data)) {
        return NextResponse.json(
          {
            detail:
              "Backend returned an invalid response",
          },
          {
            status: 502,
          },
        );
      }

      allConversations.push(...data);

      if (data.length < pageSize) {
        break;
      }

      offset += pageSize;
    }

    return NextResponse.json(
      allConversations,
    );
  } catch {
    return NextResponse.json(
      {
        detail:
          "Unable to connect to conversation service",
      },
      {
        status: 502,
      },
    );
  }
}

export async function POST(
  request: Request,
) {
  const accessToken =
    await getAccessToken();

  if (!accessToken) {
    return NextResponse.json(
      { detail: "Not authenticated" },
      { status: 401 },
    );
  }

  let body: ConversationCreateRequest;

  try {
    body =
      (await request.json()) as
        ConversationCreateRequest;
  } catch {
    return NextResponse.json(
      { detail: "Invalid request body" },
      { status: 400 },
    );
  }

  const title =
    typeof body.title === "string"
      ? body.title.trim()
      : "";

  const projectId =
    typeof body.project_id === "string"
      ? body.project_id.trim()
      : body.project_id === null
        ? null
        : undefined;

  if (
    body.project_id !== undefined &&
    projectId === undefined
  ) {
    return NextResponse.json(
      { detail: "Invalid project ID" },
      { status: 400 },
    );
  }

  if (
    !title ||
    (
      body.mode !== "normal" &&
      body.mode !== "knowledge"
    )
  ) {
    return NextResponse.json(
      {
        detail:
          "Valid title and mode are required",
      },
      {
        status: 400,
      },
    );
  }

  try {
    const response =
      await fetch(
        backendUrl("/conversations"),
        {
          method: "POST",
          headers: {
            "Content-Type":
              "application/json",
            Authorization:
              `Bearer ${accessToken}`,
          },
          body: JSON.stringify({
            title,
            mode: body.mode,
            ...(projectId
              ? { project_id: projectId }
              : {}),
          }),
          cache: "no-store",
          signal: request.signal,
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
          "Unable to create conversation",
      },
      {
        status: 502,
      },
    );
  }
}
