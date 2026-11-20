import { privateJsonResponse } from "@/lib/security/private-json";
import { readBoundedJson, RequestBodyTooLargeError } from "@/lib/security/request-body";
import { hasTrustedRequestOrigin } from "@/lib/security/origin";

import {
  backendUrl,
  readJson,
} from "@/lib/api/backend";
import { forwardedBackendHeaders } from "@/lib/api/response-headers";
import {
  getAccessToken,
} from "@/lib/auth/session";
import type {
  ChatTurnResponse,
  ConversationMessageResponse,
} from "@/types/conversation";

type ApiError = {
  detail?: unknown;
};

type ConversationMessageRequest = {
  content?: string;
  document_ids?: string[];
  top_k?: number;
};

type RouteContext = {
  params: Promise<{
    conversationId: string;
  }>;
};

export async function GET(
  _request: Request,
  context: RouteContext,
) {
  const accessToken =
    await getAccessToken();

  if (!accessToken) {
    return privateJsonResponse(
      { detail: "Not authenticated" },
      { status: 401 },
    );
  }

  const { conversationId } =
    await context.params;

  try {
    const response =
      await fetch(
        backendUrl(
          `/conversations/${encodeURIComponent(
            conversationId,
          )}/messages?limit=200&offset=0`,
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
        ConversationMessageResponse[] | ApiError
      >(response);

    return privateJsonResponse(
      data ?? {
        detail:
          "Backend returned an invalid response",
      },
      {
        status: response.status,
        headers:
          forwardedBackendHeaders(
            response,
          ),
      },
    );
  } catch {
    return privateJsonResponse(
      {
        detail:
          "Unable to load conversation messages",
      },
      {
        status: 502,
      },
    );
  }
}

export async function POST(
  request: Request,
  context: RouteContext,
) {
  // Both browser voice fallback and normal chat use cookie authentication.
  if (!hasTrustedRequestOrigin(request)) {
    return privateJsonResponse(
      { detail: "Untrusted request origin" },
      { status: 403, headers: { "Cache-Control": "private, no-store" } },
    );
  }

  const accessToken =
    await getAccessToken();

  if (!accessToken) {
    return privateJsonResponse(
      { detail: "Not authenticated" },
      { status: 401 },
    );
  }

  const { conversationId } =
    await context.params;

  let body: ConversationMessageRequest;

  try {
    body = (await readBoundedJson(
      request,
      131072,
    )) as ConversationMessageRequest;
  } catch (error) {
    if (error instanceof RequestBodyTooLargeError) {
      return privateJsonResponse(
        { detail: "Message request too large" },
        { status: 413 },
      );
    }
    return privateJsonResponse(
      { detail: "Invalid request body" },
      { status: 400 },
    );
  }

  const content =
    typeof body.content === "string"
      ? body.content.trim()
      : "";

  if (!content) {
    return privateJsonResponse(
      { detail: "Message is required" },
      { status: 400 },
    );
  }

  try {
    const response =
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
            document_ids:
              Array.isArray(
                body.document_ids,
              )
                ? body.document_ids
                : [],
            ...(typeof body.top_k ===
            "number"
              ? {
                  top_k:
                    body.top_k,
                }
              : {}),
          }),
          cache: "no-store",
          signal: request.signal,
        },
      );

    const data =
      await readJson<
        ChatTurnResponse | ApiError
      >(response);

    return privateJsonResponse(
      data ?? {
        detail:
          "Backend returned an invalid response",
      },
      {
        status: response.status,
      },
    );
  } catch {
    return privateJsonResponse(
      {
        detail:
          "Unable to send conversation message",
      },
      {
        status: 502,
      },
    );
  }
}
