import { privateJsonResponse } from "@/lib/security/private-json";
import { readBoundedJson, RequestBodyTooLargeError } from "@/lib/security/request-body";

import {
  backendUrl,
  readJson,
} from "@/lib/api/backend";
import {
  getAccessToken,
} from "@/lib/auth/session";
import type {
  ConversationMode,
} from "@/types/conversation";
import type {
  ProjectResponse,
} from "@/types/project";


type ApiError = {
  detail?: unknown;
};

type ProjectCreateRequest = {
  name?: string;
  mode?: ConversationMode;
};


export async function GET(
  request: Request,
) {
  const accessToken =
    await getAccessToken();

  if (!accessToken) {
    return privateJsonResponse(
      { detail: "Not authenticated" },
      { status: 401 },
    );
  }

  const requestUrl =
    new URL(request.url);
  const mode =
    requestUrl.searchParams.get("mode");

  if (
    mode !== null &&
    mode !== "normal" &&
    mode !== "knowledge"
  ) {
    return privateJsonResponse(
      { detail: "Invalid project mode" },
      { status: 400 },
    );
  }

  const params =
    new URLSearchParams({
      limit: "100",
      offset: "0",
    });

  if (mode !== null) {
    params.set("mode", mode);
  }

  try {
    const response = await fetch(
      backendUrl(
        `/projects?${params.toString()}`,
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
        ProjectResponse[] | ApiError
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
          "Unable to connect to project service",
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
    return privateJsonResponse(
      { detail: "Not authenticated" },
      { status: 401 },
    );
  }

  let body: ProjectCreateRequest;

  try {
    body =
      (await readBoundedJson(request, 16384)) as
        ProjectCreateRequest;
  } catch (error) {
    if (error instanceof RequestBodyTooLargeError) {
      return privateJsonResponse({ detail: "Request body too large" }, { status: 413 });
    }
    return privateJsonResponse(
      { detail: "Invalid request body" },
      { status: 400 },
    );
  }

  const name =
    typeof body.name === "string"
      ? body.name.trim()
      : "";

  if (
    !name ||
    (
      body.mode !== "normal" &&
      body.mode !== "knowledge"
    )
  ) {
    return privateJsonResponse(
      {
        detail:
          "Valid project name and mode are required",
      },
      {
        status: 400,
      },
    );
  }

  try {
    const response = await fetch(
      backendUrl("/projects"),
      {
        method: "POST",
        headers: {
          "Content-Type":
            "application/json",
          Authorization:
            `Bearer ${accessToken}`,
        },
        body: JSON.stringify({
          name,
          mode: body.mode,
        }),
        cache: "no-store",
        signal: request.signal,
      },
    );

    const data =
      await readJson<
        ProjectResponse | ApiError
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
          "Unable to create project",
      },
      {
        status: 502,
      },
    );
  }
}
