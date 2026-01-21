import { describe, it, expect, beforeEach, vi } from "vitest";
import { useAuthStore } from "../auth";
import { api } from "@/services/api";
import { mockUser } from "@/test";

// Mock the api module
vi.mock("@/services/api", () => ({
  api: {
    setAuthToken: vi.fn(),
    clearAuthToken: vi.fn(),
  },
}));

describe("useAuthStore", () => {
  beforeEach(() => {
    // Reset store state before each test
    useAuthStore.setState({
      user: null,
      token: null,
      isAuthenticated: false,
      isLoading: true,
    });
    vi.clearAllMocks();
    localStorage.clear();
  });

  describe("initial state", () => {
    it("should have null user and token initially", () => {
      const state = useAuthStore.getState();
      expect(state.user).toBeNull();
      expect(state.token).toBeNull();
      expect(state.isAuthenticated).toBe(false);
    });

    it("should have isLoading true initially", () => {
      const state = useAuthStore.getState();
      expect(state.isLoading).toBe(true);
    });
  });

  describe("login", () => {
    it("should set user and token when login is called", () => {
      const user = mockUser({ email: "test@example.com" });
      const token = "test-token-123";

      useAuthStore.getState().login(token, user);

      const state = useAuthStore.getState();
      expect(state.user).toEqual(user);
      expect(state.token).toBe(token);
      expect(state.isAuthenticated).toBe(true);
      expect(state.isLoading).toBe(false);
    });

    it("should call api.setAuthToken with the token", () => {
      const user = mockUser();
      const token = "test-token-123";

      useAuthStore.getState().login(token, user);

      expect(api.setAuthToken).toHaveBeenCalledWith(token);
      expect(api.setAuthToken).toHaveBeenCalledTimes(1);
    });

    it("should update isAuthenticated to true", () => {
      const user = mockUser();
      const token = "test-token";

      expect(useAuthStore.getState().isAuthenticated).toBe(false);

      useAuthStore.getState().login(token, user);

      expect(useAuthStore.getState().isAuthenticated).toBe(true);
    });
  });

  describe("logout", () => {
    it("should clear user and token when logout is called", () => {
      // First login
      const user = mockUser();
      useAuthStore.getState().login("token", user);

      // Then logout
      useAuthStore.getState().logout();

      const state = useAuthStore.getState();
      expect(state.user).toBeNull();
      expect(state.token).toBeNull();
      expect(state.isAuthenticated).toBe(false);
    });

    it("should call api.clearAuthToken", () => {
      useAuthStore.getState().login("token", mockUser());
      vi.clearAllMocks();

      useAuthStore.getState().logout();

      expect(api.clearAuthToken).toHaveBeenCalledTimes(1);
    });

    it("should set isAuthenticated to false", () => {
      useAuthStore.getState().login("token", mockUser());
      expect(useAuthStore.getState().isAuthenticated).toBe(true);

      useAuthStore.getState().logout();

      expect(useAuthStore.getState().isAuthenticated).toBe(false);
    });
  });

  describe("setUser", () => {
    it("should update the user without affecting other state", () => {
      const initialUser = mockUser({ email: "initial@example.com" });
      useAuthStore.getState().login("token", initialUser);

      const updatedUser = mockUser({
        email: "updated@example.com",
        role: "admin",
      });
      useAuthStore.getState().setUser(updatedUser);

      const state = useAuthStore.getState();
      expect(state.user).toEqual(updatedUser);
      expect(state.token).toBe("token"); // Token unchanged
      expect(state.isAuthenticated).toBe(true); // Still authenticated
    });
  });

  describe("setLoading", () => {
    it("should update isLoading state", () => {
      expect(useAuthStore.getState().isLoading).toBe(true);

      useAuthStore.getState().setLoading(false);
      expect(useAuthStore.getState().isLoading).toBe(false);

      useAuthStore.getState().setLoading(true);
      expect(useAuthStore.getState().isLoading).toBe(true);
    });
  });

  describe("persistence", () => {
    it("should persist user, token, and isAuthenticated to localStorage", () => {
      const user = mockUser({ email: "persist@example.com" });
      const token = "persist-token";

      useAuthStore.getState().login(token, user);

      // Check localStorage was updated (zustand persist uses 'auth-storage' key)
      const stored = localStorage.getItem("auth-storage");
      expect(stored).not.toBeNull();

      const parsed = JSON.parse(stored!);
      expect(parsed.state.user).toEqual(user);
      expect(parsed.state.token).toBe(token);
      expect(parsed.state.isAuthenticated).toBe(true);
    });

    it("should not persist isLoading to localStorage", () => {
      useAuthStore.getState().login("token", mockUser());
      useAuthStore.getState().setLoading(false);

      const stored = localStorage.getItem("auth-storage");
      const parsed = JSON.parse(stored!);

      // isLoading should not be in persisted state
      expect(parsed.state).not.toHaveProperty("isLoading");
    });

    it("should restore state from localStorage on rehydration", () => {
      const user = mockUser({ email: "rehydrate@example.com" });
      const token = "rehydrate-token";

      // Manually set localStorage to simulate previous session
      localStorage.setItem(
        "auth-storage",
        JSON.stringify({
          state: {
            user,
            token,
            isAuthenticated: true,
          },
          version: 0,
        })
      );

      // Rehydrate the store
      useAuthStore.persist.rehydrate();

      const state = useAuthStore.getState();
      expect(state.user).toEqual(user);
      expect(state.token).toBe(token);
      expect(state.isAuthenticated).toBe(true);
    });
  });
});
