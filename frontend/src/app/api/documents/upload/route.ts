import { NextRequest, NextResponse } from "next/server";

import { backendUrl, readJson } from "@/lib/api/backend";
import { forwardedBackendHeaders } from "@/lib/api/response-headers";
import { getAccessToken } from "@/lib/auth/session";
import type { DocumentResponse } from "@/types/document";
import { readBoundedBodyBytes, RequestBodyTooLargeError } from "@/lib/security/request-body";

// 25 MiB backend file cap plus at most 1 MiB multipart envelope overhead.
const MAX_FILE_BYTES = 25 * 1024 * 1024;
const MAX_MULTIPART_BYTES = MAX_FILE_BYTES + 1024 * 1024;

type ErrorResponse = {
  detail?: unknown;
};

export async function POST(request: NextRequest) {
  const accessToken = await getAccessToken();

  if (!accessToken) {
    return NextResponse.json(
      { detail: "Not authenticated" },
      { status: 401 },
    );
  }

  try {
    // Request.formData() can buffer an unchecked multipart body. First
    // enforce the byte cap even if Content-Length is absent or forged.
    const contentType = request.headers.get("content-type") ?? "";
    if (!contentType.toLowerCase().startsWith("multipart/form-data;")) {
      return NextResponse.json(
        { detail: "Multipart form data is required" }, { status: 415 },
      );
    }
    const bytes = await readBoundedBodyBytes(request, MAX_MULTIPART_BYTES);
    const boundedBytes = new Uint8Array(bytes.byteLength);
    boundedBytes.set(bytes);
    const bounded = new Request(request.url, {
      method: "POST",
      headers: { "Content-Type": contentType },
      body: boundedBytes,
    });
    const incomingFormData = await bounded.formData();
    const file = incomingFormData.get("file");

    if (!(file instanceof File)) {
      return NextResponse.json(
        { detail: "Document file is required" },
        { status: 400 },
      );
    }

    if (file.size > MAX_FILE_BYTES) {
      return NextResponse.json(
        { detail: "Document file is too large" }, { status: 413 },
      );
    }

    const backendFormData = new FormData();
    backendFormData.append("file", file);

    const response = await fetch(
      backendUrl("/documents/upload"),
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${accessToken}`,
        },
        body: backendFormData,
        cache: "no-store",
      },
    );

    const data =
      await readJson<DocumentResponse | ErrorResponse>(
        response,
      );

    return NextResponse.json(
      data ?? { detail: "Backend returned an invalid response" },
      {
        status: response.status,
        headers:
          forwardedBackendHeaders(
            response,
          ),
      },
    );
  } catch (error) {
    if (error instanceof RequestBodyTooLargeError) {
      return NextResponse.json(
        { detail: "Document upload is too large" }, { status: 413 },
      );
    }
    return NextResponse.json(
      { detail: "Unable to upload document" },
      { status: 502 },
    );
  }
}