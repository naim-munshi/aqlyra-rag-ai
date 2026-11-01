import { NextResponse } from "next/server";
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
  ConversationMode,
} from "@/types/conversation";


type VoiceSessionRequest = {
  mode?: ConversationMode;
  conversation_id?: string | null;
  title?: string;
  document_ids?: string[];
};


type VoiceSessionResponse = {
  server_url: string;
  participant_token: string;
  room_name: string;
  conversation_id: string;
  mode: ConversationMode;
};


type ApiError = {
  detail?: unknown;
};

// A LiveKit room JWT is a short-lived bearer capability, never cacheable.
const PRIVATE_VOICE_HEADERS = {
  "Cache-Control": "private, no-store",
  Pragma: "no-cache",
};


export async function POST(
  request: Request,
) {
  // An authenticated voice-room token cannot be minted from a cross-site
  // POST using the user's session cookie.
  if (!hasTrustedRequestOrigin(request)) {
    return NextResponse.json(
      { detail: "Untrusted request origin" },
      { status: 403, headers: PRIVATE_VOICE_HEADERS },
    );
  }

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
        headers: PRIVATE_VOICE_HEADERS,
      },
    );
  }

  let body: VoiceSessionRequest;

  try {
    body =
      (await readBoundedJson(request, 16384)) as
        VoiceSessionRequest;
  } catch (error) {
    if (error instanceof RequestBodyTooLargeError) {
      return NextResponse.json({ detail: "Request body too large" }, { status: 413, headers: PRIVATE_VOICE_HEADERS });
    }
    return NextResponse.json(
      {
        detail:
          "Invalid request body",
      },
      {
        status: 400,
        headers: PRIVATE_VOICE_HEADERS,
      },
    );
  }

  if (
    body.mode !== "normal" &&
    body.mode !== "knowledge"
  ) {
    return NextResponse.json(
      {
        detail:
          "Valid voice mode is required",
      },
      {
        status: 400,
        headers: PRIVATE_VOICE_HEADERS,
      },
    );
  }

  const conversationId =
    typeof body.conversation_id ===
      "string"
      ? body.conversation_id.trim()
      : "";

  const title =
    typeof body.title === "string" &&
    body.title.trim()
      ? body.title.trim()
      : "Voice conversation";

  const documentIds =
    Array.isArray(body.document_ids)
      ? body.document_ids.filter(
          (
            value,
          ): value is string =>
            typeof value ===
              "string" &&
            Boolean(value.trim()),
        )
      : [];

  try {
    const response =
      await fetch(
        backendUrl(
          "/voice/session",
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
            mode: body.mode,
            ...(conversationId
              ? {
                  conversation_id:
                    conversationId,
                }
              : {}),
            title,
            document_ids:
              documentIds,
          }),
          cache: "no-store",
          signal: request.signal,
        },
      );

    const data =
      await readJson<
        VoiceSessionResponse |
        ApiError
      >(response);

    return NextResponse.json(
      data ?? {
        detail:
          "Backend returned an invalid voice response",
      },
      {
        status: response.status,
        headers: {
          ...forwardedBackendHeaders(response),
          ...PRIVATE_VOICE_HEADERS,
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
          "Unable to connect to voice service",
      },
      {
        status: 502,
        headers: PRIVATE_VOICE_HEADERS,
      },
    );
  }
}
