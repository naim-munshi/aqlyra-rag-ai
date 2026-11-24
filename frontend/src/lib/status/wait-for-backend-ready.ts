/** A client-side, unauthenticated liveness gate for Render Free cold starts.
 * Never resend a credential-bearing POST. Once readiness succeeds, the caller
 * may submit exactly one login request. Bounded retries avoid request storms.
 */
export const LOGIN_READINESS_MAX_ATTEMPTS = 7;
export const LOGIN_READINESS_INTERVAL_MS = 3500;
export const LOGIN_READINESS_TIMEOUT_MS = 11000;

export async function waitForBackendReady(): Promise<boolean> {
  for (let attempt = 1; attempt <= LOGIN_READINESS_MAX_ATTEMPTS; attempt++) {
    const controller = new AbortController();
    const deadline = setTimeout(
      () => controller.abort(),
      LOGIN_READINESS_TIMEOUT_MS,
    );
    try {
      const response = await fetch("/api/health", {
        method: "GET",
        credentials: "omit",
        cache: "no-store",
        signal: controller.signal,
      });
      if (response.status === 200) {
        const body: unknown = await response.json();
        if (
          typeof body === "object" &&
          body !== null &&
          "status" in body &&
          body.status === "ready"
        ) {
          return true;
        }
      }
    } catch {
      // A sleeping Render instance may fail the first few public GETs.
    } finally {
      clearTimeout(deadline);
    }
    if (attempt < LOGIN_READINESS_MAX_ATTEMPTS) {
      await new Promise<void>((resolve) =>
        setTimeout(resolve, LOGIN_READINESS_INTERVAL_MS),
      );
    }
  }
  return false;
}
