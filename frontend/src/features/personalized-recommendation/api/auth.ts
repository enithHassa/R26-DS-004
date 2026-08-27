/**
 * Shared account auth API — login / signup via gateway ``/api/v1/auth``.
 *
 * Comp 3 recommendation clients should not call these; use this module
 * (or re-exports from ``personalized-recommendation/api/auth``) instead.
 */
export { login, signup } from "@/features/users/api/auth";
export type {
  LoginPayload,
  LoginResult,
  SignupPayload,
  SignupResult,
} from "@/features/users/api/auth";
