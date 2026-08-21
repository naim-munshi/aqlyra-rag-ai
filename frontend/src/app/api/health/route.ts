export const dynamic = "force-dynamic";

const NO_STORE_HEADERS = {
  "Cache-Control": "no-store, max-age=0",
};

export async function GET() {
  const configuredBaseUrl =
    process.env.BACKEND_API_URL?.trim();

  if (!configuredBaseUrl) {
    return Response.json(
      {
        status: "unavailable",
      },
      {
        status: 503,
        headers: NO_STORE_HEADERS,
      },
    );
  }

  const baseUrl =
    configuredBaseUrl.replace(
      /\/+$/,
      "",
    );

  const controller =
    new AbortController();

  const timeout = setTimeout(
    () => controller.abort(),
    3000,
  );

  try {
    const response = await fetch(
      `${baseUrl}/readiness`,
      {
        method: "GET",
        cache: "no-store",
        signal: controller.signal,
      },
    );

    const requestId =
      response.headers.get(
        "x-request-id",
      );

    const headers: Record<
      string,
      string
    > = {
      ...NO_STORE_HEADERS,
    };

    if (requestId) {
      headers["X-Request-ID"] =
        requestId;
    }

    if (!response.ok) {
      return Response.json(
        {
          status: "unavailable",
        },
        {
          status: 503,
          headers,
        },
      );
    }

    return Response.json(
      {
        status: "ready",
      },
      {
        status: 200,
        headers,
      },
    );
  } catch {
    return Response.json(
      {
        status: "unavailable",
      },
      {
        status: 503,
        headers: NO_STORE_HEADERS,
      },
    );
  } finally {
    clearTimeout(
      timeout,
    );
  }
}
