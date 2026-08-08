import { create } from "zustand";
import { persist } from "zustand/middleware";

export type SessionRole = "auditor" | "taxpayer";

type UserSessionState = {
  isAuthenticated: boolean;
  role: SessionRole | null;
  profileId: string | null;
  fullName: string | null;
  login: (role: SessionRole, profileId: string | null, fullName: string) => void;
  logout: () => void;
};

export const useUserSessionStore = create<UserSessionState>()(
  persist(
    (set) => ({
      isAuthenticated: false,
      role: null,
      profileId: null,
      fullName: null,
      login: (role, profileId, fullName) => set({ isAuthenticated: true, role, profileId, fullName }),
      logout: () => set({ isAuthenticated: false, role: null, profileId: null, fullName: null }),
    }),
    { name: "comp3-user-session" },
  ),
);
