"use client";

import { useState } from "react";
import { LockKeyhole, Search, ShieldAlert, UserRoundCog } from "lucide-react";

type AdminAccount = {
  id: string;
  email: string;
  username: string;
  is_active: boolean;
  is_verified: boolean;
  is_admin: boolean;
  created_at: string;
};

type AccountPage = {
  users: AdminAccount[];
  total: number;
  offset: number;
  limit: number;
  can_permanently_delete: boolean;
};

type AccountAction = "disable" | "enable" | "delete";

const PAGE_SIZE = 25;

export function UserManagementPanel() {
  const [filter, setFilter] = useState("");
  const [page, setPage] = useState<AccountPage | null>(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [selected, setSelected] = useState<{
    account: AdminAccount;
    action: AccountAction;
  } | null>(null);
  const [confirmEmail, setConfirmEmail] = useState("");
  const [confirmPhrase, setConfirmPhrase] = useState("");

  async function load(offset = 0) {
    setLoading(true);
    setError("");
    try {
      const params = new URLSearchParams({
        limit: String(PAGE_SIZE),
        offset: String(offset),
        q: filter.trim().slice(0, 100),
      });
      const response = await fetch("/api/admin/users?" + params.toString(), {
        cache: "no-store",
        credentials: "same-origin",
      });
      if (!response.ok) throw new Error("Unable to load account list. Check Admin access.");
      const result = (await response.json()) as AccountPage;
      if (!Array.isArray(result.users)) throw new Error("Invalid account response");
      setPage(result);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Account list unavailable");
    } finally {
      setLoading(false);
    }
  }

  function prepare(account: AdminAccount, action: AccountAction) {
    setSelected({ account, action });
    setConfirmEmail("");
    setConfirmPhrase("");
    setNotice("");
    setError("");
  }

  async function submitAction(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selected || saving) return;
    if (confirmEmail.trim().toLowerCase() !== selected.account.email.toLowerCase()) {
      setError("Enter the exact account email to confirm.");
      return;
    }
    if (selected.action === "delete" && confirmPhrase !== "DELETE ACCOUNT") {
      setError('Type DELETE ACCOUNT to confirm permanent deletion.');
      return;
    }

    const { account, action } = selected;
    setSaving(true);
    setError("");
    try {
      const response = await fetch("/api/admin/users/" + encodeURIComponent(account.id), {
        method: action === "delete" ? "DELETE" : "PATCH",
        credentials: "same-origin",
        cache: "no-store",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(
          action === "delete"
            ? { confirm_email: confirmEmail, confirmation: "DELETE ACCOUNT" }
            : { confirm_email: confirmEmail, action },
        ),
      });
      const result = (await response.json().catch(() => null)) as
        | { detail?: string }
        | null;
      if (!response.ok) {
        throw new Error(result?.detail ?? "Account action failed.");
      }
      setSelected(null);
      setNotice(
        action === "delete"
          ? "Account deletion completed."
          : action === "disable"
            ? "Account disabled and existing tokens revoked."
            : "Account re-enabled. Previous tokens remain revoked.",
      );
      await load(page?.offset ?? 0);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Account action failed");
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="mt-9 rounded-2xl border border-white/10 bg-[#101827] p-5"
      aria-label="Registered account management">
      <div className="flex items-center gap-3">
        <UserRoundCog size={20} aria-hidden="true" className="text-cyan-300" />
        <div>
          <h2 className="text-lg font-semibold">Registered users</h2>
          <p className="mt-1 text-xs leading-5 text-slate-400">
            Admin-only list of email addresses and account status.
            No private chats, passwords, or user documents are shown.
          </p>
        </div>
      </div>

      <form className="mt-5 flex flex-wrap gap-2" onSubmit={(e) => {
        e.preventDefault();
        void load(0);
      }}>
        <label htmlFor="admin-email-search" className="sr-only">
          Search registered email addresses
        </label>
        <input id="admin-email-search" type="search" maxLength={100}
          placeholder="Search email address"
          value={filter} onChange={(e) => setFilter(e.target.value)}
          className="min-w-0 flex-1 rounded-lg border border-white/15 bg-white/5 px-3 py-2 text-sm text-white placeholder:text-slate-500 sm:min-w-[220px]" />
        <button type="submit" disabled={loading}
          className="inline-flex items-center gap-2 rounded-lg border border-cyan-500/50 px-4 py-2 text-sm font-medium text-cyan-200 disabled:opacity-50">
          <Search size={15} aria-hidden="true" />
          {loading ? "Loading…" : page ? "Search" : "View accounts"}
        </button>
      </form>

      {error && <p role="alert" className="mt-4 rounded-lg border border-amber-500/40 p-3 text-sm text-amber-200">{error}</p>}
      {notice && <p role="status" className="mt-4 text-sm text-emerald-300">{notice}</p>}

      {page && (
        <>
          <div className="mt-4 flex flex-wrap justify-between gap-2 text-xs text-slate-400">
            <span>{page.total} matching registered accounts</span>
            <span>Showing {page.total === 0 ? 0 : page.offset + 1}–{Math.min(page.total, page.offset + page.users.length)}</span>
          </div>
          <div className="mt-4 overflow-x-auto rounded-xl border border-white/10">
            <table className="w-full min-w-[760px] text-left text-sm">
              <thead className="border-b border-white/10 bg-white/5 text-xs text-slate-400">
                <tr>
                  <th className="p-3">Email / account</th>
                  <th className="p-3">Registered (UTC)</th>
                  <th className="p-3">Status</th>
                  <th className="p-3 text-right">Controls</th>
                </tr>
              </thead>
              <tbody>
                {page.users.map((account) => (
                  <tr className="border-b border-white/5" key={account.id}>
                    <td className="p-3">
                      <div className="break-all font-medium text-slate-100">{account.email}</div>
                      <div className="mt-1 text-xs text-slate-500">{account.username}</div>
                    </td>
                    <td className="p-3 text-xs tabular-nums text-slate-300">
                      {account.created_at.replace("T", " ").slice(0, 16)}
                    </td>
                    <td className="p-3">
                      <span className={account.is_active ? "text-emerald-300" : "text-amber-300"}>
                        {account.is_active ? "Enabled" : "Disabled"}
                      </span>
                      <div className="mt-1 text-xs text-slate-500">
                        {account.is_admin ? "Admin" : account.is_verified ? "Verified" : "Unverified"}
                      </div>
                    </td>
                    <td className="p-3 text-right">
                      {account.is_admin ? (
                        <span className="inline-flex items-center gap-1 text-xs text-slate-400">
                          <LockKeyhole size={12} aria-hidden="true" /> Protected
                        </span>
                      ) : (
                        <div className="flex items-center justify-end gap-2">
                          <button type="button" disabled={saving}
                            onClick={() => prepare(account, account.is_active ? "disable" : "enable")}
                            className="rounded-lg border border-white/15 px-3 py-1.5 text-xs text-slate-200 hover:bg-white/5">
                            {account.is_active ? "Disable" : "Enable"}
                          </button>
                          <button type="button"
                            disabled={saving || !page.can_permanently_delete || account.is_active}
                            onClick={() => prepare(account, "delete")}
                            title={
                              !page.can_permanently_delete
                                ? "Permanent deletion is disabled pending storage safety acceptance"
                                : account.is_active
                                  ? "Disable this account first"
                                  : "Permanently delete an eligible empty account"
                            }
                            className="rounded-lg border border-red-500/40 px-3 py-1.5 text-xs text-red-300 disabled:opacity-40">
                            Delete
                          </button>
                        </div>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {page.users.length === 0 &&
              <p className="p-6 text-center text-sm text-slate-400">No matching accounts.</p>}
          </div>
          <div className="mt-4 flex items-center justify-between text-xs">
            <button type="button" onClick={() => void load(Math.max(0, page.offset - PAGE_SIZE))}
              disabled={loading || page.offset <= 0}
              className="rounded-lg border border-white/15 px-3 py-2 text-slate-200 disabled:opacity-40">Previous</button>
            <button type="button" onClick={() => void load(page.offset + PAGE_SIZE)}
              disabled={loading || page.offset + PAGE_SIZE >= page.total}
              className="rounded-lg border border-white/15 px-3 py-2 text-slate-200 disabled:opacity-40">Next</button>
          </div>
          {!page.can_permanently_delete && (
            <p className="mt-4 flex gap-2 text-xs leading-5 text-slate-400">
              <ShieldAlert size={16} className="shrink-0 text-amber-300" aria-hidden="true" />
              Permanent deletion stays locked until storage cleanup and recovery are
              verified. Disable/Enable is available now; neither deletes user data.
            </p>
          )}
        </>
      )}

      {selected && (
        <div role="dialog" aria-modal="true" aria-label="Confirm account action"
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-4">
          <form onSubmit={(e) => void submitAction(e)}
            className="w-full max-w-md rounded-2xl border border-white/20 bg-[#111827] p-6 shadow-2xl">
            <h3 className="text-lg font-semibold text-white">
              {selected.action === "delete" ? "Permanently delete account" :
                selected.action === "disable" ? "Disable account" : "Enable account"}
            </h3>
            <p className="mt-3 break-all text-sm text-slate-300">
              Target: <strong>{selected.account.email}</strong>
            </p>
            <p className="mt-3 text-xs leading-5 text-amber-200">
              {selected.action === "delete"
                ? "This action is irreversible. Uploaded-data accounts cannot be deleted here."
                : "Disabling immediately revokes existing sessions. Re-enabling requires a new sign-in."}
            </p>
            <label htmlFor="admin-confirm-email"
              className="mt-5 block text-xs font-semibold text-slate-300">
              Enter the exact target email address
            </label>
            <input id="admin-confirm-email" type="email" required autoComplete="off"
              value={confirmEmail} onChange={(e) => setConfirmEmail(e.target.value)}
              className="mt-2 w-full rounded-lg border border-white/20 bg-white/5 px-3 py-2 text-sm text-white" />
            {selected.action === "delete" && (
              <>
                <label htmlFor="admin-delete-phrase"
                  className="mt-4 block text-xs font-semibold text-slate-300">
                  Type DELETE ACCOUNT
                </label>
                <input id="admin-delete-phrase" required autoComplete="off"
                  value={confirmPhrase} onChange={(e) => setConfirmPhrase(e.target.value)}
                  className="mt-2 w-full rounded-lg border border-white/20 bg-white/5 px-3 py-2 text-sm text-white" />
              </>
            )}
            <div className="mt-6 flex justify-end gap-2">
              <button type="button" onClick={() => { setSelected(null); setError(""); }}
                disabled={saving} className="rounded-lg border border-white/15 px-4 py-2 text-sm">Cancel</button>
              <button type="submit" disabled={saving ||
                confirmEmail.trim().toLowerCase() !== selected.account.email.toLowerCase() ||
                (selected.action === "delete" && confirmPhrase !== "DELETE ACCOUNT")}
                className="rounded-lg bg-cyan-600 px-4 py-2 text-sm font-medium text-white disabled:opacity-40">
                {saving ? "Applying…" : "Confirm"}
              </button>
            </div>
          </form>
        </div>
      )}
    </section>
  );
}
