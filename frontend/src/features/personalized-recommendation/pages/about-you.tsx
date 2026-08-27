import { Navigate, useNavigate } from "react-router-dom";
import { CheckCircle2, LogOut } from "lucide-react";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

import { BehaviouralQuestionsPanel } from "../components/behavioural-questions-panel";
import { useUserSessionStore } from "../store/user-session-store";

const DOT_GRID_BG =
  "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='40' height='40'%3E%3Ccircle cx='2' cy='2' r='1.4' fill='white' fill-opacity='0.14'/%3E%3C/svg%3E";

export function AboutYouPage() {
  const navigate = useNavigate();
  const isAuthenticated = useUserSessionStore((s) => s.isAuthenticated);
  const role = useUserSessionStore((s) => s.role);
  const profileId = useUserSessionStore((s) => s.profileId);
  const fullName = useUserSessionStore((s) => s.fullName);
  const logout = useUserSessionStore((s) => s.logout);

  if (!isAuthenticated || role !== "taxpayer") {
    return <Navigate to="/login" replace />;
  }
  if (!profileId) {
    return <Navigate to="/taxwise" replace />;
  }

  return (
    <div
      className="relative flex min-h-screen items-center justify-center overflow-hidden px-4 py-10"
      style={{
        background:
          "radial-gradient(1200px circle at 15% 20%, color-mix(in srgb, var(--tax-accent) 55%, transparent) 0%, transparent 42%)," +
          "radial-gradient(1000px circle at 85% 75%, color-mix(in srgb, var(--primary) 65%, transparent) 0%, transparent 50%)," +
          "radial-gradient(800px circle at 50% 100%, color-mix(in srgb, var(--tax-accent) 30%, transparent) 0%, transparent 55%)," +
          "linear-gradient(160deg, #241419 0%, #150d10 55%, #1b1013 100%)",
      }}
    >
      <div
        className="pointer-events-none absolute inset-0 opacity-40"
        style={{ backgroundImage: `url("${DOT_GRID_BG}")`, backgroundSize: "40px 40px" }}
        aria-hidden
      />

      <div className="relative z-10 flex w-full max-w-xl flex-col items-center">
        <div className="mb-6 flex flex-col items-center gap-2 text-center">
          <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-white/10 shadow-lg ring-1 ring-white/20 backdrop-blur-sm">
            <CheckCircle2 className="h-7 w-7 text-white" />
          </div>
          <div className="text-lg font-semibold tracking-tight text-white">
            {fullName ? `Welcome, ${fullName.split(" ")[0]}` : "Before we begin"}
          </div>
          <button
            type="button"
            onClick={() => {
              logout();
              navigate("/login", { replace: true });
            }}
            className="mt-1 inline-flex items-center gap-1.5 text-sm text-white/70 transition-colors hover:text-white"
          >
            <LogOut className="h-3.5 w-3.5" />
            Sign out and switch account
          </button>
        </div>

        <Card className="w-full border-white/10 bg-white/95 shadow-2xl backdrop-blur-md">
          <CardHeader>
            <CardTitle>About You</CardTitle>
            <CardDescription>
              A few quick questions to tailor your recommendations.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <BehaviouralQuestionsPanel
              profileId={profileId}
              finishLabel="Submit Answer"
              onFinish={() => navigate("/taxwise", { replace: true })}
            />
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
