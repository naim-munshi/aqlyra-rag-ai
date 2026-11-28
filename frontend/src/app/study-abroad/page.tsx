import { redirect } from "next/navigation";
import { getAccessToken } from "@/lib/auth/session";
import { backendUrl } from "@/lib/api/backend";
import { StudyAbroadWorkspace } from "@/components/study-abroad/study-abroad-workspace";

export default async function StudyAbroadPage() {
  const token = await getAccessToken();
  if (!token) redirect("/login");
  let active = false;
  try {
    const response = await fetch(backendUrl("/users/me"), {
      headers: { Authorization: `Bearer ${token}` }, cache: "no-store",
    });
    active = response.ok;
  } catch { active = false; }
  if (!active) redirect("/login");
  return <StudyAbroadWorkspace />;
}
