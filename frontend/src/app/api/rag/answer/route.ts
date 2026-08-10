import { NextResponse } from "next/server";

import {
  backendUrl,
  readJson,
} from "@/lib/api/backend";
import { getAccessToken } from "@/lib/auth/session";
import type {
  RAGAnswerRequest,
  RAGAnswerResponse,
  RAGErrorResponse,
} from "@/types/rag";

export async function POST(request: Request) {
  const accessToken = await getAccessToken();

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

  let body: RAGAnswerRequest;

  try {
    body =
      (await request.json()) as RAGAnswerRequest;
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

  if (
    typeof body.question !== "string" ||
    !body.question.trim()
  ) {
    return NextResponse.json(
      {
        detail: "Question is required",
      },
      {
        status: 400,
      },
    );
  }

  try {
    const response = await fetch(
      backendUrl("/rag/answer"),
      {
        method: "POST",

        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${accessToken}`,
        },

        body: JSON.stringify({
          ...body,
          question: body.question.trim(),
        }),

        cache: "no-store",
      },
    );

    const data =
      await readJson<
        RAGAnswerResponse | RAGErrorResponse
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
          "Unable to connect to RAG service",
      },
      {
        status: 502,
      },
    );
  }
}