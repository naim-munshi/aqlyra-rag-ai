import type { DocumentResponse } from "@/types/document";

const MAX_CLOUD_UPLOAD_BYTES = 25 * 1024 * 1024;
type PrepareResponse = {
  intent_id: string;
  upload_url: string;
  method: "PUT";
  headers: Record<string, string>;
  expires_in_seconds: number;
};

async function detailMessage(response: Response, fallback: string): Promise<string> {
  try {
    const body = (await response.json()) as { detail?: string };
    if (typeof body.detail === "string") return body.detail;
  } catch {
    // Never expose a provider's signed URL or error body in the UI.
  }
  return fallback;
}

export async function uploadViaPrivateCloud(file: File): Promise<DocumentResponse> {
  if (!file.size || file.size > MAX_CLOUD_UPLOAD_BYTES) {
    throw new Error("Choose a document between 1 byte and 25 MB");
  }
  if (!globalThis.crypto?.subtle) {
    throw new Error("Secure HTTPS connection required for cloud upload");
  }
  const hash = await crypto.subtle.digest("SHA-256", await file.arrayBuffer());
  const sha256 = Array.from(new Uint8Array(hash), (n) => n.toString(16).padStart(2, "0")).join("");

  const grantResponse = await fetch("/api/documents/cloud/prepare", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "same-origin",
    body: JSON.stringify({
      filename: file.name, size_bytes: file.size, sha256,
    }),
    cache: "no-store",
  });
  if (!grantResponse.ok) {
    throw new Error(await detailMessage(grantResponse, "Unable to prepare private upload"));
  }
  const grant = (await grantResponse.json()) as PrepareResponse;
  let destination: URL;
  try {
    destination = new URL(grant.upload_url);
  } catch {
    throw new Error("Invalid private upload destination");
  }
  if (
    grant.method !== "PUT" ||
    destination.protocol !== "https:" ||
    !destination.hostname.endsWith(".aws.neon.tech") ||
    destination.username || destination.password || destination.port ||
    !/^[a-f0-9-]{36}$/.test(grant.intent_id) ||
    grant.expires_in_seconds > 120 || grant.expires_in_seconds < 1
  ) {
    throw new Error("Invalid private upload grant");
  }
  const allowedHeaders = Object.keys(grant.headers);
  if (
    allowedHeaders.length !== 1 ||
    allowedHeaders[0].toLowerCase() !== "content-type"
  ) {
    throw new Error("Unexpected private upload headers");
  }
  // PUT bypasses Vercel's 4.5MB function limit; never send auth cookies
  // or JWTs to object storage. CORS must allow this exact frontend origin.
  const uploaded = await fetch(destination.toString(), {
    method: "PUT",
    headers: grant.headers,
    body: file,
    credentials: "omit",
    redirect: "error",
  });
  if (!uploaded.ok) {
    throw new Error("Private object upload failed; retry with a new grant");
  }

  const finalized = await fetch(
    `/api/documents/cloud/${encodeURIComponent(grant.intent_id)}/finalize`,
    { method: "POST", credentials: "same-origin", cache: "no-store" },
  );
  if (!finalized.ok) {
    throw new Error(await detailMessage(
      finalized, "Unable to verify uploaded document",
    ));
  }
  return (await finalized.json()) as DocumentResponse;
}
