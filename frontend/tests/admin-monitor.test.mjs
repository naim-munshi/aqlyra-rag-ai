import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const get = (path) => readFileSync(new URL(path, import.meta.url), "utf8");

test("admin page authenticates before reading monitoring data", () => {
  const page = get("../src/app/admin/page.tsx");
  assert.match(page, /getAccessToken\(/);
  assert.match(page, /if \(!token\) redirect\("\/login"\)/);
  assert.match(page, /response\.status === 403\) notFound\(/);
  assert.match(page, /cache: "no-store"/);
  assert.match(page, /index: false/);
});

test("admin JSON proxy checks session and never caches responses", () => {
  const api = get("../src/app/api/admin/overview/route.ts");
  assert.match(api, /getAccessToken\(/);
  assert.match(api, /Not authenticated/);
  assert.match(api, /response\.status === 401 \|\| response\.status === 403/);
  assert.match(api, /Cache-Control": "private, no-store/);
  assert.doesNotMatch(api, /NEXT_PUBLIC_ADMIN/i);
});

test("private guest monitoring separates visits and chats without claiming unique people", () => {
  const ui = get("../src/components/admin/guest-traffic-panel.tsx");
  assert.match(ui, /chat_requests/);
  assert.match(ui, /item\.visits/);
  assert.match(ui, /at most 24 hours from the first event/);
  assert.match(ui, /not unique people/);
  assert.doesNotMatch(ui, /localStorage/);
});

test("monitor shows only process-local API traffic, not unique visitors", () => {
  const ui = get("../src/components/admin/admin-monitor.tsx");
  assert.match(ui, /single|per backend process/i);
  assert.match(ui, /not unique website visitors/i);
  assert.doesNotMatch(ui, /localStorage|document\.cookie/);
});

test("chat monitoring is backward compatible and uses aggregated account activity", () => {
  const ui = get("../src/components/admin/admin-monitor.tsx");
  const types = get("../src/types/admin.ts");
  assert.match(ui, /data\.chat_activity \?/);
  assert.match(ui, /Chat activity is not yet available on this backend release/);
  assert.match(ui, /active_users_last_24h/);
  assert.match(ui, /user_messages_last_7d/);
  assert.match(ui, /not live-online users or unique website visitors/);
  assert.match(types, /chat_activity\?: AdminChatActivity/);
  assert.match(types, /persisted_authenticated_user_messages/);
  assert.doesNotMatch(ui, /user\.email|message\.content|document\.content/);
});


test("admin registered user controls are private and gated", () => {
  const ui = get("../src/components/admin/user-management-panel.tsx");
  const list = get("../src/app/api/admin/users/route.ts");
  const mutations = get("../src/app/api/admin/users/[userId]/route.ts");
  const parent = get("../src/components/admin/admin-monitor.tsx");
  assert.match(parent, /<UserManagementPanel \/>/);
  assert.match(list, /getAccessToken\(/);
  assert.match(list, /Cache-Control": "private, no-store/);
  assert.match(mutations, /getAccessToken\(/);
  assert.match(mutations, /hasTrustedRequestOrigin\(request\)/);
  assert.match(mutations, /DELETE ACCOUNT/);
  assert.match(mutations, /Cache-Control": "private, no-store/);
  assert.match(mutations, /Content-Type": "application\/json"/);
  assert.match(ui, /can_permanently_delete/);
  assert.match(ui, /confirmEmail\.trim\(\)\.toLowerCase\(\)/);
  assert.match(ui, /Disable/);
  assert.match(ui, /Enable/);
  assert.match(ui, /does not|neither deletes user data/i);
  assert.doesNotMatch(ui, /localStorage|sessionStorage/);
});
