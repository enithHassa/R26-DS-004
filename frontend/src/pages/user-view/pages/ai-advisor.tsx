import { Navigate } from "react-router-dom";

import { ChatPage } from "@/features/language-model/pages/chat";
import { useUserSessionStore } from "@/features/personalized-recommendation/store/user-session-store";
import { UserViewShell } from "@/pages/user-view/components/user-view-shell";

/**
 * TaxWise → AI Advisor.
 *
 * Mounts the Component 4 (language model) chat inside the taxpayer portal shell.
 * The chat component reads `userId` / `profileId` from the shared user-session
 * store, so turns are grounded in the signed-in taxpayer's own record and saved
 * chats are scoped to their `users.id` server-side (llm_chat_sessions).
 *
 * `.uv-chat` retints the reused shadcn components to the dark TaxWise palette
 * (see user-view-theme.css).
 */
export function UserAiAdvisorPage() {
  const userId = useUserSessionStore((s) => s.userId);
  const profileId = useUserSessionStore((s) => s.profileId);
  const fullName = useUserSessionStore((s) => s.fullName);

  if (!profileId) {
    return <Navigate to="/login" replace />;
  }

  const firstName = fullName?.split(/\s+/)[0] ?? "there";

  return (
    <UserViewShell
      title="AI Advisor"
      subtitle={`Ask about Sri Lankan income tax and your own record, ${firstName}`}
    >
      <div className="uv-chat mx-auto min-h-[72vh] max-w-7xl">
        {/* key on userId so switching accounts fully resets the chat state */}
        <ChatPage key={userId ?? "anon"} />
      </div>
    </UserViewShell>
  );
}
