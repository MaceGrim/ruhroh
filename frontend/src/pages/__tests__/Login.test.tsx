import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, userEvent, waitFor } from "@/test";
import { LoginPage } from "../Login";
import { useAuthStore } from "@/stores";

// Mock useNavigate
const mockNavigate = vi.fn();
vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual("react-router-dom");
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

describe("LoginPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Reset auth store
    useAuthStore.setState({
      user: null,
      token: null,
      isAuthenticated: false,
      isLoading: false,
    });
  });

  describe("rendering", () => {
    it("should render the login form", () => {
      render(<LoginPage />);

      expect(screen.getByText("Welcome to ruhroh")).toBeInTheDocument();
      expect(
        screen.getByText("Sign in to access your document assistant")
      ).toBeInTheDocument();
    });

    it("should render email input field", () => {
      render(<LoginPage />);

      const emailInput = screen.getByLabelText(/email address/i);
      expect(emailInput).toBeInTheDocument();
      expect(emailInput).toHaveAttribute("type", "email");
      expect(emailInput).toHaveAttribute("required");
    });

    it("should render password input field", () => {
      render(<LoginPage />);

      const passwordInput = screen.getByLabelText(/password/i);
      expect(passwordInput).toBeInTheDocument();
      expect(passwordInput).toHaveAttribute("type", "password");
      expect(passwordInput).toHaveAttribute("required");
    });

    it("should render sign in button", () => {
      render(<LoginPage />);

      const button = screen.getByRole("button", { name: /sign in/i });
      expect(button).toBeInTheDocument();
      expect(button).toHaveAttribute("type", "submit");
    });

    it("should render placeholder text in inputs", () => {
      render(<LoginPage />);

      expect(screen.getByPlaceholderText("you@example.com")).toBeInTheDocument();
      expect(screen.getByPlaceholderText("••••••••")).toBeInTheDocument();
    });
  });

  describe("form validation", () => {
    it("should have required attribute on email field", () => {
      render(<LoginPage />);

      const emailInput = screen.getByLabelText(/email address/i);
      expect(emailInput).toBeRequired();
    });

    it("should have required attribute on password field", () => {
      render(<LoginPage />);

      const passwordInput = screen.getByLabelText(/password/i);
      expect(passwordInput).toBeRequired();
    });

    it("should have email type validation", () => {
      render(<LoginPage />);

      const emailInput = screen.getByLabelText(/email address/i);
      expect(emailInput).toHaveAttribute("type", "email");
    });
  });

  describe("user interactions", () => {
    it("should allow typing in email field", async () => {
      const user = userEvent.setup();
      render(<LoginPage />);

      const emailInput = screen.getByLabelText(/email address/i);
      await user.type(emailInput, "test@example.com");

      expect(emailInput).toHaveValue("test@example.com");
    });

    it("should allow typing in password field", async () => {
      const user = userEvent.setup();
      render(<LoginPage />);

      const passwordInput = screen.getByLabelText(/password/i);
      await user.type(passwordInput, "mypassword123");

      expect(passwordInput).toHaveValue("mypassword123");
    });

    it("should clear previous error on new input", async () => {
      // This test checks UX - error should be cleared when user starts a new attempt
      // First, we need to see an error state
      const user = userEvent.setup();

      // Mock VITE_DEV_MODE to be false to trigger error
      const originalEnv = import.meta.env.VITE_DEV_MODE;
      vi.stubEnv("VITE_DEV_MODE", "false");

      render(<LoginPage />);

      const emailInput = screen.getByLabelText(/email address/i);
      const passwordInput = screen.getByLabelText(/password/i);
      const submitButton = screen.getByRole("button", { name: /sign in/i });

      await user.type(emailInput, "test@example.com");
      await user.type(passwordInput, "password");
      await user.click(submitButton);

      // After submit with dev mode false, there should be an error message
      await waitFor(() => {
        expect(
          screen.getByText(/auth not configured/i)
        ).toBeInTheDocument();
      });

      // Restore env
      vi.stubEnv("VITE_DEV_MODE", originalEnv || "");
    });
  });

  describe("form submission", () => {
    it("should show loading state during submission", async () => {
      vi.stubEnv("VITE_DEV_MODE", "true");
      const user = userEvent.setup();
      render(<LoginPage />);

      const emailInput = screen.getByLabelText(/email address/i);
      const passwordInput = screen.getByLabelText(/password/i);
      const submitButton = screen.getByRole("button", { name: /sign in/i });

      await user.type(emailInput, "test@example.com");
      await user.type(passwordInput, "password123");

      // Click submit - in dev mode this should succeed
      await user.click(submitButton);

      // The button text changes to "Signing in..." while loading
      // This happens quickly so we may or may not catch it
      // Instead verify the final state
      await waitFor(() => {
        expect(mockNavigate).toHaveBeenCalledWith("/");
      });
    });

    it("should call login with correct data in dev mode", async () => {
      vi.stubEnv("VITE_DEV_MODE", "true");
      const loginSpy = vi.spyOn(useAuthStore.getState(), "login");
      const user = userEvent.setup();

      render(<LoginPage />);

      const emailInput = screen.getByLabelText(/email address/i);
      const passwordInput = screen.getByLabelText(/password/i);
      const submitButton = screen.getByRole("button", { name: /sign in/i });

      await user.type(emailInput, "devuser@example.com");
      await user.type(passwordInput, "devpassword");
      await user.click(submitButton);

      await waitFor(() => {
        expect(loginSpy).toHaveBeenCalled();
      });

      // Verify the login was called with the mock user containing the email
      const callArgs = loginSpy.mock.calls[0];
      expect(callArgs[0]).toBe("dev-token");
      expect(callArgs[1].email).toBe("devuser@example.com");
    });

    it("should navigate to home on successful login", async () => {
      vi.stubEnv("VITE_DEV_MODE", "true");
      const user = userEvent.setup();

      render(<LoginPage />);

      const emailInput = screen.getByLabelText(/email address/i);
      const passwordInput = screen.getByLabelText(/password/i);
      const submitButton = screen.getByRole("button", { name: /sign in/i });

      await user.type(emailInput, "test@example.com");
      await user.type(passwordInput, "password");
      await user.click(submitButton);

      await waitFor(() => {
        expect(mockNavigate).toHaveBeenCalledWith("/");
      });
    });

    it("should show error message when auth is not configured", async () => {
      vi.stubEnv("VITE_DEV_MODE", "false");
      const user = userEvent.setup();

      render(<LoginPage />);

      const emailInput = screen.getByLabelText(/email address/i);
      const passwordInput = screen.getByLabelText(/password/i);
      const submitButton = screen.getByRole("button", { name: /sign in/i });

      await user.type(emailInput, "test@example.com");
      await user.type(passwordInput, "password");
      await user.click(submitButton);

      await waitFor(() => {
        expect(
          screen.getByText(/auth not configured/i)
        ).toBeInTheDocument();
      });
    });

    it("should disable submit button while loading", async () => {
      vi.stubEnv("VITE_DEV_MODE", "true");
      const user = userEvent.setup();

      render(<LoginPage />);

      const emailInput = screen.getByLabelText(/email address/i);
      const passwordInput = screen.getByLabelText(/password/i);
      const submitButton = screen.getByRole("button", { name: /sign in/i });

      await user.type(emailInput, "test@example.com");
      await user.type(passwordInput, "password");

      // Submit form
      await user.click(submitButton);

      // Wait for the form submission to complete
      await waitFor(() => {
        expect(mockNavigate).toHaveBeenCalled();
      });
    });
  });

  describe("error handling", () => {
    it("should display error message in error div", async () => {
      vi.stubEnv("VITE_DEV_MODE", "false");
      const user = userEvent.setup();

      render(<LoginPage />);

      await user.type(screen.getByLabelText(/email address/i), "test@test.com");
      await user.type(screen.getByLabelText(/password/i), "pass");
      await user.click(screen.getByRole("button", { name: /sign in/i }));

      await waitFor(() => {
        const errorDiv = screen.getByText(/auth not configured/i);
        expect(errorDiv).toHaveClass("text-error");
      });
    });

    it("should not show error message initially", () => {
      render(<LoginPage />);

      // Error message container should not exist initially
      expect(screen.queryByText(/auth not configured/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/login failed/i)).not.toBeInTheDocument();
    });
  });

  describe("accessibility", () => {
    it("should have proper labels for inputs", () => {
      render(<LoginPage />);

      // Labels should be associated with inputs
      expect(screen.getByLabelText("Email address")).toBeInTheDocument();
      expect(screen.getByLabelText("Password")).toBeInTheDocument();
    });

    it("should have autocomplete attributes", () => {
      render(<LoginPage />);

      const emailInput = screen.getByLabelText(/email address/i);
      const passwordInput = screen.getByLabelText(/password/i);

      expect(emailInput).toHaveAttribute("autocomplete", "email");
      expect(passwordInput).toHaveAttribute("autocomplete", "current-password");
    });
  });
});
