import { useEffect, useState } from "react";
import { TrendingUp } from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";

import { AuditorImpactProjectionView } from "../components/auditor-recommendations/impact-projection-view";
import { PageHeader } from "../components/page-header";
import { ProfilePicker } from "../components/profile-picker";
import { useActiveProfileId } from "../store/dashboard-store";

export function ImpactPage() {
  const activeProfileId = useActiveProfileId();
  const [profileId, setProfileId] = useState(activeProfileId ?? "");

  useEffect(() => {
    if (activeProfileId && activeProfileId !== profileId) setProfileId(activeProfileId);
  }, [activeProfileId, profileId]);

  return (
    <div className="space-y-6">
      <PageHeader
        icon={TrendingUp}
        title="Impact Lab"
        description="Monte Carlo financial impact projection for a selected strategy."
      />

      <Card className="max-w-md border-border/70 shadow-sm">
        <CardContent className="p-4">
          <ProfilePicker value={profileId} onChange={setProfileId} label="Taxpayer profile" />
        </CardContent>
      </Card>

      {profileId ? (
        <AuditorImpactProjectionView profileId={profileId} />
      ) : (
        <Card className="border-dashed">
          <CardContent className="py-12 text-center text-sm text-muted-foreground">
            Select a profile, then open a strategy from Smart Recommendations via View Impact.
          </CardContent>
        </Card>
      )}
    </div>
  );
}
