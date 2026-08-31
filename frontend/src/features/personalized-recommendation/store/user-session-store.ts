import { create } from "zustand";
import { persist } from "zustand/middleware";

export type SessionRole = "auditor" | "taxpayer";

type UserSessionState = {
  isAuthenticated: boolean;
  role: SessionRole | null;
  userId: string | null;
  profileId: string | null;
  fullName: string | null;
  login: (role: SessionRole, userId: string | null, profileId: string | null, fullName: string) => void;
  setProfileId: (profileId: string) => void;
  logout: () => void;
};

export const useUserSessionStore = create<UserSessionState>()(
  persist(
    (set) => ({
      isAuthenticated: false,
      role: null,
      userId: null,
      profileId: null,
      fullName: null,
      login: (role, userId, profileId, fullName) =>
        set({ isAuthenticated: true, role, userId, profileId, fullName }),
      setProfileId: (profileId) => set({ profileId }),
      logout: () => set({ isAuthenticated: false, role: null, userId: null, profileId: null, fullName: null }),
    }),
    { name: "comp3-user-session" },
  ),
);
