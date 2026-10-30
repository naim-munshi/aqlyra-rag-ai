import { redirect } from "next/navigation";

// Legacy bookmark compatibility: files remain owner-scoped and can be
// generated, listed, and downloaded from the main Aqlyra chat. The
// artifact API and existing stored files are not deleted.
export default function ArtifactsPage() {
  redirect("/");
}
