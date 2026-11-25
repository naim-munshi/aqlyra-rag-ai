import { privateJsonResponse } from "@/lib/security/private-json";
import { readBoundedJson, RequestBodyTooLargeError } from "@/lib/security/request-body";
import { hasTrustedRequestOrigin } from "@/lib/security/origin";
import { backendUrl, readJson } from "@/lib/api/backend";
import { forwardedBackendHeaders } from "@/lib/api/response-headers";
import { getAccessToken } from "@/lib/auth/session";
import type { AgentApiError, AgentResearchResponse } from "@/types/agent-harness";

type ResearchRequest = {
  question?: string;
  document_ids?: string[];
  chunk_roles?: Array<"content" | "summary" | "proposition">;
  top_k?: number;
  max_context_tokens?: number;
};

export async function POST(request: Request) {
  if (!hasTrustedRequestOrigin(request)) {
    return privateJsonResponse({ detail: "Untrusted request origin" }, { status: 403 });
  }

  const accessToken = await getAccessToken();
  if (!accessToken) {
    return privateJsonResponse({ detail: "Not authenticated" }, { status: 401 });
  }

  let body: ResearchRequest;
  try {
    body = (await readBoundedJson(request, 16_384)) as ResearchRequest;
  } catch (error) {
    if (error instanceof RequestBodyTooLargeError) {
      return privateJsonResponse({ detail: "Request body too large" }, { status: 413 });
    }
    return privateJsonResponse({ detail: "Invalid request body" }, { status: 400 });
  }

  const question = typeof body.question === "string" ? body.question.trim() : "";
  if (!question || question.length > 2_000) {
    return privateJsonResponse({ detail: "Question must contain 1–2,000 characters" }, { status: 400 });
  }
  if (body.document_ids !== undefined &&
      (!Array.isArray(body.document_ids) || body.document_ids.length > 50 ||
       body.document_ids.some((id) => typeof id !== "string" || !id.trim()))) {
    return privateJsonResponse({ detail: "Invalid document scope" }, { status: 400 });
  }

  try {
    const upstream = await fetch(backendUrl("/agent-harness/research"), {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${accessToken}`,
      },
      body: JSON.stringify({
        question,
        document_ids: body.document_ids ?? [],
        ...(body.chunk_roles ? { chunk_roles: body.chunk_roles } : {}),
        ...(typeof body.top_k === "number" ? { top_k: body.top_k } : {}),
        ...(typeof body.max_context_tokens === "number"
          ? { max_context_tokens: body.max_context_tokens }
          : {}),
      }),
      cache: "no-store",
      signal: request.signal,
    });
    const data = await readJson<AgentResearchResponse | AgentApiError>(upstream);
    return privateJsonResponse(
      data ?? { detail: "Backend returned an invalid response" },
      { status: upstream.status, headers: forwardedBackendHeaders(upstream) },
    );
  } catch {
    return privateJsonResponse({ detail: "Unable to connect to Knowledge research agent" }, { status: 502 });
  }
}
