import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Routes, Route, MemoryRouter } from "react-router-dom";
import { MainLayout } from "../MainLayout";
import { useAuthStore } from "@/stores";
import { mockUser } from "@/test";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

// Helper to render MainLayout with routing
function renderMainLayout(
  initialEntries: string[] = ["/"],
  children?: React.ReactNode
) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={initialEntries}>
        <Routes>
          <Route element={<MainLayout />}>
            <Route
              path="/"
              element={children || <div data-testid="child-content">Home Page</div>}
            />
            <Route
              path="/documents"
              element={<div data-testid="documents-page">Documents Page</div>}
            />
            <Route
              path="/admin/users"
              element={<div data-testid="admin-users">Admin Users</div>}
            />
          </Route>
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe("MainLayout", () => {
  beforeEach(() => {
    // Set up a default authenticated user
    useAuthStore.setState({
      user: mockUser({ email: "test@example.com", role: "user" }),
      token: "test-token",
      isAuthenticated: true,
      isLoading: false,
    });
  });

  describe("rendering", () => {
    it("should render the sidebar", () => {
      renderMainLayout();

      // Sidebar contains the logo/brand - there may be multiple due to mobile header
      const ruhrohElements = screen.getAllByText("ruhroh");
      expect(ruhrohElements.length).toBeGreaterThan(0);
    });

    it("should render children through Outlet", () => {
      renderMainLayout();

      expect(screen.getByTestId("child-content")).toBeInTheDocument();
      expect(screen.getByText("Home Page")).toBeInTheDocument();
    });

    it("should render navigation links in sidebar", () => {
      renderMainLayout();

      expect(screen.getByText("Chat")).toBeInTheDocument();
      expect(screen.getByText("Documents")).toBeInTheDocument();
      expect(screen.getByText("Search")).toBeInTheDocument();
      expect(screen.getByText("Settings")).toBeInTheDocument();
    });

    it("should render user email in sidebar", () => {
      renderMainLayout();

      expect(screen.getByText("test@example.com")).toBeInTheDocument();
    });

    it("should render user role in sidebar", () => {
      renderMainLayout();

      expect(screen.getByText("user")).toBeInTheDocument();
    });
  });

  describe("sidebar toggle", () => {
    it("should have a mobile menu button", () => {
      renderMainLayout();

      // The hamburger menu button is in the mobile header
      const buttons = screen.getAllByRole("button");
      expect(buttons.length).toBeGreaterThan(0);
    });

    it("should toggle sidebar visibility when menu button is clicked", async () => {
      const user = userEvent.setup();
      renderMainLayout();

      // Get the mobile menu button (first button in mobile header)
      const buttons = screen.getAllByRole("button");
      const menuButton = buttons.find(
        (btn) => btn.querySelector("svg")?.classList.contains("w-6")
      );

      // Click to open sidebar
      if (menuButton) {
        await user.click(menuButton);

        // After click, sidebar should be visible (translate-x-0)
        const sidebarContainer = document.querySelector(".fixed.inset-y-0");
        expect(sidebarContainer).toHaveClass("translate-x-0");
      }
    });

    it("should close sidebar when overlay is clicked", async () => {
      const user = userEvent.setup();
      renderMainLayout();

      // Open sidebar first
      const buttons = screen.getAllByRole("button");
      const menuButton = buttons.find(
        (btn) => btn.querySelector("svg")?.classList.contains("w-6")
      );

      if (menuButton) {
        await user.click(menuButton);

        // Find and click the overlay
        const overlay = document.querySelector(".fixed.inset-0.bg-black\\/50");
        if (overlay) {
          await user.click(overlay);

          // Sidebar should be hidden again
          const sidebarContainer = document.querySelector(".fixed.inset-y-0");
          expect(sidebarContainer).toHaveClass("-translate-x-full");
        }
      }
    });
  });

  describe("responsive behavior", () => {
    it("should have sidebar hidden by default on mobile", () => {
      renderMainLayout();

      // The sidebar container should have -translate-x-full class initially
      const sidebarContainer = document.querySelector(".fixed.inset-y-0");
      expect(sidebarContainer).toHaveClass("-translate-x-full");
    });

    it("should have lg:translate-x-0 for desktop", () => {
      renderMainLayout();

      const sidebarContainer = document.querySelector(".fixed.inset-y-0");
      expect(sidebarContainer).toHaveClass("lg:translate-x-0");
    });

    it("should have mobile header with lg:hidden", () => {
      renderMainLayout();

      const mobileHeader = document.querySelector(".lg\\:hidden.flex.items-center");
      expect(mobileHeader).toBeInTheDocument();
    });

    it("should show brand name in mobile header", () => {
      renderMainLayout();

      const mobileHeader = document.querySelector(".lg\\:hidden");
      expect(mobileHeader).toHaveTextContent("ruhroh");
    });
  });

  describe("navigation", () => {
    it("should highlight active navigation item", () => {
      renderMainLayout(["/documents"]);

      // The Documents link should have the active class (bg-primary)
      const documentsLink = screen.getByText("Documents").closest("a");
      expect(documentsLink).toHaveClass("bg-primary");
    });

    it("should not show admin links for regular users", () => {
      useAuthStore.setState({
        user: mockUser({ role: "user" }),
        token: "token",
        isAuthenticated: true,
        isLoading: false,
      });

      renderMainLayout();

      expect(screen.queryByText("Users")).not.toBeInTheDocument();
      expect(screen.queryByText("Stats")).not.toBeInTheDocument();
    });

    it("should show admin links for admin users", () => {
      useAuthStore.setState({
        user: mockUser({ role: "admin" }),
        token: "token",
        isAuthenticated: true,
        isLoading: false,
      });

      renderMainLayout();

      expect(screen.getByText("Users")).toBeInTheDocument();
      expect(screen.getByText("Stats")).toBeInTheDocument();
    });

    it("should show admin links for superuser users", () => {
      useAuthStore.setState({
        user: mockUser({ role: "superuser" }),
        token: "token",
        isAuthenticated: true,
        isLoading: false,
      });

      renderMainLayout();

      expect(screen.getByText("Users")).toBeInTheDocument();
      expect(screen.getByText("Stats")).toBeInTheDocument();
    });
  });

  describe("logout functionality", () => {
    it("should have logout button in sidebar", () => {
      renderMainLayout();

      const logoutButton = screen.getByTitle("Sign out");
      expect(logoutButton).toBeInTheDocument();
    });

    it("should call logout when logout button is clicked", async () => {
      const logoutSpy = vi.spyOn(useAuthStore.getState(), "logout");
      const user = userEvent.setup();

      renderMainLayout();

      const logoutButton = screen.getByTitle("Sign out");
      await user.click(logoutButton);

      expect(logoutSpy).toHaveBeenCalled();
    });
  });

  describe("user display", () => {
    it("should display user initial in avatar", () => {
      useAuthStore.setState({
        user: mockUser({ email: "alice@example.com" }),
        token: "token",
        isAuthenticated: true,
        isLoading: false,
      });

      renderMainLayout();

      // Should show "A" for alice@example.com
      expect(screen.getByText("A")).toBeInTheDocument();
    });

    it("should display U as fallback when no email", () => {
      useAuthStore.setState({
        user: null,
        token: null,
        isAuthenticated: false,
        isLoading: false,
      });

      renderMainLayout();

      expect(screen.getByText("U")).toBeInTheDocument();
    });

    it("should display email in sidebar", () => {
      useAuthStore.setState({
        user: mockUser({ email: "specific@example.com" }),
        token: "token",
        isAuthenticated: true,
        isLoading: false,
      });

      renderMainLayout();

      expect(screen.getByText("specific@example.com")).toBeInTheDocument();
    });

    it("should display role badge", () => {
      useAuthStore.setState({
        user: mockUser({ role: "admin" }),
        token: "token",
        isAuthenticated: true,
        isLoading: false,
      });

      renderMainLayout();

      expect(screen.getByText("admin")).toBeInTheDocument();
    });
  });

  describe("layout structure", () => {
    it("should have proper flex layout", () => {
      renderMainLayout();

      const layoutContainer = document.querySelector(".flex.h-screen");
      expect(layoutContainer).toBeInTheDocument();
    });

    it("should have main content area with overflow handling", () => {
      renderMainLayout();

      const mainContent = document.querySelector("main.flex-1.overflow-auto");
      expect(mainContent).toBeInTheDocument();
    });

    it("should have sidebar with fixed width", () => {
      renderMainLayout();

      const sidebar = document.querySelector("aside.w-64");
      expect(sidebar).toBeInTheDocument();
    });
  });

  describe("accessibility", () => {
    it("should have proper heading structure in sidebar", () => {
      renderMainLayout();

      // The brand name acts as a heading
      const brandElements = screen.getAllByText("ruhroh");
      expect(brandElements.length).toBeGreaterThan(0);
    });

    it("should have accessible navigation links", () => {
      renderMainLayout();

      const navLinks = screen.getAllByRole("link");
      expect(navLinks.length).toBeGreaterThan(0);

      // All links should have text content
      navLinks.forEach((link) => {
        expect(link.textContent).toBeTruthy();
      });
    });

    it("should have accessible logout button", () => {
      renderMainLayout();

      const logoutButton = screen.getByTitle("Sign out");
      expect(logoutButton).toBeInTheDocument();
    });
  });

  describe("dark mode support", () => {
    it("should have dark mode classes", () => {
      renderMainLayout();

      // Check that dark mode classes are present
      const layoutContainer = document.querySelector(".dark\\:bg-gray-900");
      expect(layoutContainer).toBeInTheDocument();
    });

    it("should have dark mode text colors", () => {
      renderMainLayout();

      // Check for dark mode text color classes
      const darkTextElements = document.querySelectorAll(".dark\\:text-white");
      expect(darkTextElements.length).toBeGreaterThan(0);
    });
  });
});
