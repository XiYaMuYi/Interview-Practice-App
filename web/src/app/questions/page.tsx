import QuestionsPageClient from "./QuestionsPageClient";

// Opt out of static generation — this page uses useSearchParams()
export const dynamic = "force-dynamic";

export default function QuestionsPage() {
  return <QuestionsPageClient />;
}
