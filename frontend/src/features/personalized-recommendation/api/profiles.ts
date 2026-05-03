import { recommendationApi } from "../api";
import type {
  DerivedFeatures,
  FinancialProfile,
  FinancialProfileCreate,
  PaginatedProfiles,
} from "../types";

export interface ListProfilesParams {
  page?: number;
  page_size?: number;
  occupation?: string;
  district?: string;
}

export async function createProfile(
  payload: FinancialProfileCreate,
): Promise<FinancialProfile> {
  const { data } = await recommendationApi.post<FinancialProfile>("/profiles", payload);
  return data;
}

export async function listProfiles(params: ListProfilesParams = {}): Promise<PaginatedProfiles> {
  const { data } = await recommendationApi.get<PaginatedProfiles>("/profiles", { params });
  return data;
}

export async function getProfile(profileId: string): Promise<FinancialProfile> {
  const { data } = await recommendationApi.get<FinancialProfile>(`/profiles/${profileId}`);
  return data;
}

export async function getProfileFeatures(profileId: string): Promise<DerivedFeatures> {
  const { data } = await recommendationApi.get<DerivedFeatures>(
    `/profiles/${profileId}/features`,
  );
  return data;
}

export async function updateProfile(
  profileId: string,
  payload: Partial<FinancialProfileCreate>,
): Promise<FinancialProfile> {
  const { data } = await recommendationApi.patch<FinancialProfile>(
    `/profiles/${profileId}`,
    payload,
  );
  return data;
}

export async function deleteProfile(profileId: string): Promise<void> {
  await recommendationApi.delete(`/profiles/${profileId}`);
}
