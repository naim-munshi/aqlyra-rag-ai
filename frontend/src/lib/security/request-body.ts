/**
 * Bound untrusted API bodies before decoding or parsing them.
 * Reading Request.text()/json() then checking size can exhaust a Node worker.
 * This helper works with both known and chunked/unknown Content-Length.
 */
export class RequestBodyTooLargeError extends Error {
  constructor() {
    super("Request body exceeds the safety limit");
    this.name = "RequestBodyTooLargeError";
  }
}

export async function readBoundedBodyBytes(
  request: Request,
  maxBytes: number,
): Promise<Uint8Array> {
  if (!Number.isSafeInteger(maxBytes) || maxBytes < 1) {
    throw new RangeError("Invalid body limit");
  }
  const lengthHeader = request.headers.get("content-length");
  if (lengthHeader !== null) {
    const declared = Number(lengthHeader);
    if (!Number.isSafeInteger(declared) || declared < 0 || declared > maxBytes) {
      throw new RequestBodyTooLargeError();
    }
  }

  const reader = request.body?.getReader();
  if (!reader) throw new SyntaxError("Missing JSON body");
  const chunks: Uint8Array[] = [];
  let bytes = 0;
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      bytes += value.byteLength;
      if (bytes > maxBytes) {
        await reader.cancel();
        throw new RequestBodyTooLargeError();
      }
      chunks.push(value);
    }
  } finally {
    reader.releaseLock();
  }

  return Buffer.concat(chunks, bytes);
}

export async function readBoundedBodyText(
  request: Request,
  maxBytes: number,
): Promise<string> {
  return new TextDecoder("utf-8", { fatal: true }).decode(
    await readBoundedBodyBytes(request, maxBytes),
  );
}

export async function readBoundedJson<T = unknown>(
  request: Request,
  maxBytes = 16_384,
): Promise<T> {
  return JSON.parse(await readBoundedBodyText(request, maxBytes)) as T;
}
