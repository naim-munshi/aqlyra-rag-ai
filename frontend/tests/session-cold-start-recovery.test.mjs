import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";

import {
  canReloadAfterRecovery,
  RECOVERY_CHECK_INTERVAL_MS,
  RECOVERY_CHECK_TIMEOUT_MS,
  RECOVERY_MAX_CHECKS,
} from "../src/lib/status/recovery.ts";

test("only a verified ready response and resolved session can reload", () => {
  assert.equal(canReloadAfterRecovery(200, { status: "ready" }, 200), true);
  assert.equal(canReloadAfterRecovery(200, { status: "ready" }, 401), true);
  for (const sessionStatus of [0, 403, 408, 429, 500, 502, 503, 504]) {
    assert.equal(
      canReloadAfterRecovery(200, { status: "ready" }, sessionStatus),
      false,
    );
  }
  for (const healthBody of [
    null, undefined, "ready", [], {}, { status: "unavailable" },
  ]) {
    assert.equal(canReloadAfterRecovery(200, healthBody, 200), false);
  }
  for (const http of [0, 401, 403, 500, 502, 503, 504]) {
    assert.equal(
      canReloadAfterRecovery(http, { status: "ready" }, 200),
      false,
    );
  }
});

test("cold-start polling is bounded to prevent unbounded backend wake traffic", () => {
  assert.ok(RECOVERY_CHECK_INTERVAL_MS >= 5000);
  assert.ok(RECOVERY_CHECK_TIMEOUT_MS >= 10000);
  assert.ok(RECOVERY_CHECK_TIMEOUT_MS <= 20000);
  assert.ok(RECOVERY_MAX_CHECKS > 1 && RECOVERY_MAX_CHECKS <= 15);

  const source = readFileSync(
    new URL(
      "../src/components/status/session-service-unavailable.tsx",
      import.meta.url,
    ),
    "utf8",
  );
  assert.match(source, /useEffect\(/);
  assert.match(source, /fetch\("\/api\/health"/);
  assert.match(source, /fetch\("\/api\/auth\/me"/);
  assert.match(source, /canReloadAfterRecovery/);
  assert.match(source, /clearTimeout\(deadline\)/);
  assert.match(source, /activeController\?\.abort\(\)/);
  assert.match(source, /attempted >= RECOVERY_MAX_CHECKS/);
  assert.doesNotMatch(source, /clearAccessToken|clearRefreshToken|localStorage/);
  assert.doesNotMatch(source, /method:\s*["']POST["']/);
});
