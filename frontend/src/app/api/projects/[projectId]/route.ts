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
  ProjectResponse,
} from "@/types/project";


type ApiError = {
  detail?: unknown;
};

type ProjectUpdateRequest = {
  name?: string;
};

type RouteContext = {
  params: Promise<{
    projectId: string;
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

  const { projectId } =
    await context.params;

  let body: ProjectUpdateRequest;

  try {
    body =
      (await readBoundedJson(request, 16_384)) as
        ProjectUpdateRequest;
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

  const name =
    typeof body.name === "string"
      ? body.name.trim()
      : "";

  if (!name) {
    return NextResponse.json(
      { detail: "Project name is required" },
      { status: 400 },
    );
  }

  try {
    const response = await fetch(
      backendUrl(
        `/projects/${encodeURIComponent(
          projectId,
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
        body: JSON.stringify({ name }),
        cache: "no-store",
      },
    );

    const data =
      await readJson<
        ProjectResponse | ApiError
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
      { detail: "Unable to update project" },
      { status: 502 },
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

  const { projectId } =
    await context.params;

  try {
    const response = await fetch(
      backendUrl(
        `/projects/${encodeURIComponent(
          projectId,
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
        { status: 204 },
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
      { detail: "Unable to delete project" },
      { status: 502 },
    );
  }
}
