import { recommendationApi } from "../api";
import type {
  DerivedFeatures,
  FinancialProfile,
  FinancialProfileCreate,
  PaginatedProfiles,
  ProfileHistorySnapshot,
} from "../types";

export interface ListProfilesParams {
  page?: number;
  page_size?: number;
  occupation?: string;
  district?: string;
}

export async function createProfile(
  payload: FinancialProfileCreate,
  userId?: string,
): Promise<FinancialProfile> {
  const { data } = await recommendationApi.post<FinancialProfile>("/profiles", payload, {
    params: userId ? { user_id: userId } : undefined,
  });
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

export async function getProfileHistory(
  profileId: string,
  months = 36,
): Promise<ProfileHistorySnapshot[]> {
  const { data } = await recommendationApi.get<ProfileHistorySnapshot[]>(
    `/profiles/${profileId}/history`,
    { params: { months } },
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

export async function setEligibilityOverride(
  profileId: string,
  flag: string,
  value: boolean | null,
): Promise<DerivedFeatures> {
  const { data } = await recommendationApi.patch<DerivedFeatures>(
    `/profiles/${profileId}/eligibility-overrides`,
    { flag, value },
  );
  return data;
}
