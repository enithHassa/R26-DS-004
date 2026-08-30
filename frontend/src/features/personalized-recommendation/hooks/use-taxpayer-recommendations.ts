import { useQuery } from "@tanstack/react-query";

import { generateRecommendations } from "../api/recommendations";

export function useTaxpayerRecommendations(profileId: string, topK = 5) {
  return useQuery({
    queryKey: ["taxpayer-recommendations", profileId],
    queryFn: () => generateRecommendations({ profile_id: profileId, top_k: topK }),
    enabled: !!profileId,
    refetchOnMount: "always",
  });
}
