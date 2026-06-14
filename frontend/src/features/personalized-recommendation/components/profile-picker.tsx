import { useEffect } from "react";
import { useQuery } from "@tanstack/react-query";

import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";

import { listProfiles } from "../api/profiles";
import { useDashboardStore } from "../store/dashboard-store";

type Props = {
  value: string;
  onChange: (id: string) => void;
  label?: string;
  syncStore?: boolean;
};

export function ProfilePicker({ value, onChange, label = "Profile", syncStore = true }: Props) {
  const setActiveProfileId = useDashboardStore((s) => s.setActiveProfileId);
  const activeProfileId = useDashboardStore((s) => s.activeProfileId);

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
          if (syncStore) setActiveProfileId(id || null);
        }}
        disabled={profilesQuery.isLoading}
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
