import { NextResponse } from "next/server";

import {
  backendUrl,
  readJson,
} from "@/lib/api/backend";
import { forwardedBackendHeaders } from "@/lib/api/response-headers";
import {
  getAccessToken,
} from "@/lib/auth/session";
import {
  buildConversationTitle,
} from "@/lib/conversation/title";
import type {
  ConversationResponse,
} from "@/types/conversation";

type NormalChatStreamRequest = {
  content?: string;
  display_content?: string;
  conversation_id?: string | null;
  document_ids?: string[];
};

type ApiError = {
  detail?: unknown;
};

export async function POST(
  request: Request,
) {
  const accessToken =
    await getAccessToken();

  if (!accessToken) {
    return NextResponse.json(
      {
        detail: "Not authenticated",
      },
      {
        status: 401,
      },
    );
  }

  let body: NormalChatStreamRequest;

  try {
    body =
      (await request.json()) as
        NormalChatStreamRequest;
  } catch {
    return NextResponse.json(
      {
        detail: "Invalid request body",
      },
      {
        status: 400,
      },
    );
  }

  const content =
    typeof body.content === "string"
      ? body.content.trim()
      : "";

  if (!content) {
    return NextResponse.json(
      {
        detail: "Message is required",
      },
      {
        status: 400,
      },
    );
  }

  if (
    body.document_ids !== undefined &&
    (
      !Array.isArray(
        body.document_ids,
      ) ||
      body.document_ids.some(
        (value) =>
          typeof value !== "string" ||
          !value.trim(),
      )
    )
  ) {
    return NextResponse.json(
      {
        detail:
          "Invalid document IDs",
      },
      {
        status: 400,
      },
    );
  }

  const displayContent =
    typeof body.display_content ===
      "string"
      ? body.display_content
      : undefined;

  const documentIds =
    (body.document_ids ?? []).map(
      (value) => value.trim(),
    );

  let conversationId =
    typeof body.conversation_id === "string"
      ? body.conversation_id.trim()
      : "";

  try {
    if (!conversationId) {
      const createResponse =
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
              title:
                buildConversationTitle(
                  content,
                ),
              mode: "normal",
            }),
            cache: "no-store",
            signal: request.signal,
          },
        );

      const createData =
        await readJson<
          ConversationResponse | ApiError
        >(createResponse);

      if (!createResponse.ok) {
        return NextResponse.json(
          createData ?? {
            detail:
              "Unable to create conversation",
          },
          {
            status: createResponse.status,
          },
        );
      }

      if (
        !createData ||
        !("id" in createData) ||
        typeof createData.id !==
          "string"
      ) {
        return NextResponse.json(
          {
            detail:
              "Backend returned an invalid conversation",
          },
          {
            status: 502,
          },
        );
      }

      conversationId =
        createData.id;
    }

    if (documentIds.length > 0) {
      const backendResponse =
        await fetch(
          backendUrl(
            `/conversations/${encodeURIComponent(
              conversationId,
            )}/messages`,
          ),
          {
            method: "POST",
            headers: {
              "Content-Type":
                "application/json",
              Authorization:
                `Bearer ${accessToken}`,
            },
            body: JSON.stringify({
              content,
              ...(displayContent !==
              undefined
                ? {
                    display_content:
                      displayContent,
                  }
                : {}),
              document_ids:
                documentIds,
            }),
            cache: "no-store",
            signal: request.signal,
          },
        );

      const data =
        await readJson<
          Record<string, unknown> |
          ApiError
        >(backendResponse);

      if (!backendResponse.ok) {
        return NextResponse.json(
          data ?? {
            detail:
              "Unable to process attachment",
          },
          {
            status:
              backendResponse.status,
            headers:
              forwardedBackendHeaders(
                backendResponse,
              ),
          },
        );
      }

      if (!data) {
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

      const streamBody = [
        "event: start\n",
        `data: ${JSON.stringify({
          conversation_id:
            conversationId,
          mode: "normal",
        })}\n\n`,
        "event: complete\n",
        `data: ${JSON.stringify(
          data,
        )}\n\n`,
      ].join("");

      return new Response(
        streamBody,
        {
          status: 200,
          headers: {
            "Content-Type":
              "text/event-stream; charset=utf-8",
            "Cache-Control":
              "no-cache, no-transform",
            "X-Accel-Buffering":
              "no",
          },
        },
      );
    }

    const backendResponse =
      await fetch(
        backendUrl(
          `/conversations/${encodeURIComponent(
            conversationId,
          )}/messages/stream`,
        ),
        {
          method: "POST",
          headers: {
            "Content-Type":
              "application/json",
            Authorization:
              `Bearer ${accessToken}`,
          },
          body: JSON.stringify({
            content,
            ...(displayContent !==
            undefined
              ? {
                  display_content:
                    displayContent,
                }
              : {}),
            document_ids:
              documentIds,
          }),
          cache: "no-store",
          signal: request.signal,
        },
      );

    if (!backendResponse.body) {
      const errorData =
        await readJson<ApiError>(
          backendResponse,
        );

      return NextResponse.json(
        errorData ?? {
          detail:
            "Backend returned an empty stream",
        },
        {
          status:
            backendResponse.ok
              ? 502
              : backendResponse.status,
          headers:
            forwardedBackendHeaders(
              backendResponse,
            ),
        },
      );
    }

    return new Response(
      backendResponse.body,
      {
        status: backendResponse.status,
        headers: {
          "Content-Type":
            backendResponse.headers.get(
              "content-type",
            ) ??
            "text/event-stream; charset=utf-8",
          "Cache-Control":
            "no-cache, no-transform",
          "X-Accel-Buffering": "no",
          ...forwardedBackendHeaders(
            backendResponse,
          ),
        },
      },
    );
  } catch (error) {
    if (
      error instanceof DOMException &&
      error.name === "AbortError"
    ) {
      throw error;
    }

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
