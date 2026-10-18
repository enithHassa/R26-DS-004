import { type ComponentType, useDeferredValue, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Loader2, RefreshCw, Search, Trash2, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";

import { listProfiles } from "../api/profiles";
import type { DerivedFeatures, FinancialProfile } from "../types";
import { ProfileTaxSourceSection } from "./profile-tax-source-section";
import { formatLkr } from "../utils/format-lkr";

type Props = {
  selectedId: string | null;
  selectedProfile?: FinancialProfile;
  features?: DerivedFeatures;
  featuresLoading: boolean;
  featuresError?: string;
  onToggleFlag: (flag: string, nextValue: boolean | null) => void;
  pendingFlag?: string;
  profiles: FinancialProfile[];
  profilesTotal: number;
  page: number;
  pageSize: number;
  profilesLoading: boolean;
  profilesError?: string;
  onSelectProfile: (profile: FinancialProfile) => void;
  onDeleteProfile: (id: string, name: string) => void;
  onRefreshProfiles: () => void;
  onPagePrev: () => void;
  onPageNext: () => void;
  DerivedFeaturesCard: ComponentType<{
    features?: DerivedFeatures;
    isLoading: boolean;
    error?: string;
    placeholder: boolean;
    onToggleFlag: (flag: string, nextValue: boolean | null) => void;
    pendingFlag?: string;
  }>;
};

export function ProfileFeaturesTab({
  selectedId,
  selectedProfile,
  features,
  featuresLoading,
  featuresError,
  onToggleFlag,
  pendingFlag,
  profiles,
  profilesTotal,
  page,
  pageSize,
  profilesLoading,
  profilesError,
  onSelectProfile,
  onDeleteProfile,
  onRefreshProfiles,
  onPagePrev,
  onPageNext,
  DerivedFeaturesCard,
}: Props) {
  const [searchQuery, setSearchQuery] = useState("");
  const deferredSearch = useDeferredValue(searchQuery.trim().toLowerCase());
  const isSearching = deferredSearch.length > 0;

  const searchQueryResult = useQuery({
    queryKey: ["profiles-search", deferredSearch],
    queryFn: async () => {
      const data = await listProfiles({ page: 1, page_size: 200 });
      return data.items.filter(
        (p) =>
          p.full_name.toLowerCase().includes(deferredSearch) ||
          p.occupation.toLowerCase().includes(deferredSearch) ||
          p.district.toLowerCase().includes(deferredSearch),
      );
    },
    enabled: isSearching,
  });

  const displayedProfiles = isSearching ? (searchQueryResult.data ?? []) : profiles;
  const listLoading = isSearching ? searchQueryResult.isFetching : profilesLoading;

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0">
          <div>
            <CardTitle>Recent profiles</CardTitle>
            <CardDescription>
              {profilesTotal ? `${profilesTotal} total · page ${page}` : "Loading…"}
            </CardDescription>
          </div>
          <Button
            size="icon"
            variant="ghost"
            onClick={onRefreshProfiles}
            disabled={profilesLoading}
          >
            <RefreshCw className={profilesLoading ? "h-4 w-4 animate-spin" : "h-4 w-4"} />
          </Button>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="relative">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              type="search"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search by name, occupation, or district…"
              className="pl-9 pr-9"
              aria-label="Search taxpayers"
            />
            {searchQuery && (
              <button
                type="button"
                onClick={() => setSearchQuery("")}
                className="absolute right-2 top-1/2 -translate-y-1/2 rounded-md p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
                aria-label="Clear search"
              >
                <X className="h-4 w-4" />
              </button>
            )}
          </div>
          {isSearching && (
            <p className="text-xs text-muted-foreground">
              {listLoading
                ? "Searching…"
                : `${displayedProfiles.length} match${displayedProfiles.length === 1 ? "" : "es"} for “${searchQuery.trim()}”`}
            </p>
          )}
          {profilesError && !isSearching && (
            <div className="text-sm text-destructive">{profilesError}</div>
          )}
          {searchQueryResult.isError && isSearching && (
            <div className="text-sm text-destructive">
              {(searchQueryResult.error as Error).message}
            </div>
          )}
          {!listLoading && displayedProfiles.length === 0 && (
            <div className="text-sm text-muted-foreground">
              {isSearching
                ? "No taxpayers match your search."
                : "No profiles yet. Create one under the Create profile tab."}
            </div>
          )}
          <ul className="divide-y">
            {displayedProfiles.map((p) => (
              <li
                key={p.id}
                className={`flex cursor-pointer items-center justify-between gap-3 rounded-md px-2 py-3 ${
                  selectedId === p.id ? "bg-accent/50" : "hover:bg-accent/30"
                }`}
                onClick={() => onSelectProfile(p)}
              >
                <div className="min-w-0 flex-1">
                  <div className="truncate text-sm font-medium">{p.full_name}</div>
                  <div className="truncate text-xs text-muted-foreground">
                    {p.occupation} · {p.district} · {formatLkr(p.gross_monthly_income)}/mo
                  </div>
                </div>
                <Button
                  size="icon"
                  variant="ghost"
                  onClick={(e) => {
                    e.stopPropagation();
                    onDeleteProfile(p.id, p.full_name);
                  }}
                >
                  <Trash2 className="h-4 w-4 text-muted-foreground" />
                </Button>
              </li>
            ))}
          </ul>
          {listLoading && displayedProfiles.length === 0 && (
            <div className="flex items-center gap-2 py-4 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              {isSearching ? "Searching taxpayers…" : "Loading profiles…"}
            </div>
          )}
        </CardContent>
        {!isSearching && profilesTotal > pageSize && (
          <CardFooter className="flex justify-between border-t pt-4">
            <Button size="sm" variant="outline" onClick={onPagePrev} disabled={page === 1}>
              Previous
            </Button>
            <Button
              size="sm"
              variant="outline"
              onClick={onPageNext}
              disabled={page * pageSize >= profilesTotal}
            >
              Next
            </Button>
          </CardFooter>
        )}
      </Card>

      <DerivedFeaturesCard
        features={features}
        isLoading={featuresLoading}
        error={featuresError}
        placeholder={!selectedId}
        onToggleFlag={onToggleFlag}
        pendingFlag={pendingFlag}
      />

      <div className="grid gap-6">
        <ProfileTaxSourceSection
          profileId={selectedId}
          taxYear={selectedProfile?.tax_year}
          variant="oe-engine"
          derivedFeatures={features}
        />
      </div>

      {selectedId && featuresLoading && (
        <p className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" />
          Refreshing derived features…
        </p>
      )}

      {selectedId && (
        <Card className="border-primary/20 bg-primary/[0.03]">
          <CardContent className="py-4 text-sm text-muted-foreground">
            Tax figures above are merged with{" "}
            <strong className="font-medium text-foreground">derived features</strong> when ranking
            strategies in Smart Recommendations. Complete the OE Engine interview for full
            relief-aware tax context.
          </CardContent>
        </Card>
      )}
    </div>
  );
}
