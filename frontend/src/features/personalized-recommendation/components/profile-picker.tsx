import { useEffect } from "react";
import { useQuery } from "@tanstack/react-query";

import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";

import { listProfiles } from "../api/profiles";
import { setActiveProfileId, useActiveProfileId } from "../store/dashboard-store";
import { useAuditorWorkspaceStore } from "@/store/auditor-workspace-store";

type Props = {
  value: string;
  onChange: (id: string) => void;
  label?: string;
  syncStore?: boolean;
};

export function ProfilePicker({ value, onChange, label = "Profile", syncStore = true }: Props) {
  const activeProfileId = useActiveProfileId();
  const isLocked = useAuditorWorkspaceStore((s) => s.isLocked);
  const setActiveProfile = useAuditorWorkspaceStore((s) => s.setActiveProfile);

  useEffect(() => {
    if (!value && activeProfileId) {
      onChange(activeProfileId);
    }
  }, [activeProfileId, value, onChange]);

  const profilesQuery = useQuery({
    queryKey: ["profiles", "picker"],
    queryFn: () => listProfiles({ page: 1, page_size: 50 }),
  });

  const profiles = profilesQuery.data?.items ?? [];

  return (
    <div className="space-y-1.5">
      <Label>{label}</Label>
      <Select
        value={value}
        onChange={(e) => {
          const id = e.target.value;
          onChange(id);
          if (syncStore && !isLocked) {
            if (id) {
              const match = profiles.find((p) => p.id === id);
              setActiveProfile(
                id,
                match
                  ? {
                      id: match.id,
                      fullName: match.full_name,
                      occupation: match.occupation,
                      taxYear: match.tax_year,
                      tin: "",
                    }
                  : null,
              );
            } else {
              setActiveProfileId(null);
            }
          }
        }}
        disabled={profilesQuery.isLoading || (syncStore && isLocked)}
      >
        <option value="">
          {profilesQuery.isLoading ? "Loading profiles…" : "Select a profile"}
        </option>
        {profiles.map((p) => (
          <option key={p.id} value={p.id}>
            {p.full_name} · {p.occupation}
          </option>
        ))}
      </Select>
    </div>
  );
}
