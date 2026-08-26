import { authApi } from "../api";

export interface LoginPayload {
  username: string;
  password: string;
}

export interface LoginResult {
  role: "auditor" | "taxpayer";
  full_name: string;
  user_id: string | null;
  /** Null means the account exists but hasn't completed the financial intake yet. */
  profile_id: string | null;
}

export interface SignupPayload {
  first_name: string;
  last_name: string;
  email: string;
  mobile_number: string;
  country: string;
  date_of_birth: string;
  gender: "male" | "female" | "other";
  address: string;
  city: string;
  postal_code: string;
  profile_picture?: string | null;
  password: string;
  confirm_password: string;
}

export interface SignupResult {
  user_id: string;
  email: string;
  full_name: string;
}

export async function login(payload: LoginPayload): Promise<LoginResult> {
  const { data } = await authApi.post<LoginResult>("/login", payload);
  return data;
}

export async function signup(payload: SignupPayload): Promise<SignupResult> {
  const { data } = await authApi.post<SignupResult>("/signup", payload);
  return data;
}
