import { recommendationApi } from "../api";

export interface LoginPayload {
  username: string;
  password: string;
}

export interface LoginResult {
  role: "auditor" | "taxpayer";
  full_name: string;
  user_id: string | null;
  profile_id: string | null;
}

export async function login(payload: LoginPayload): Promise<LoginResult> {
  const { data } = await recommendationApi.post<LoginResult>("/auth/login", payload);
  return data;
}
