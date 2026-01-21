import type { ReactElement, ReactNode } from "react";
import { render, type RenderOptions } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, MemoryRouter } from "react-router-dom";

// Create a fresh QueryClient for each test to ensure isolation
function createTestQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        // Turn off retries for tests
        retry: false,
        // Don't cache in tests to ensure fresh data
        staleTime: 0,
        gcTime: 0,
      },
      mutations: {
        retry: false,
      },
    },
  });
}

interface WrapperProps {
  children: ReactNode;
}

interface CustomRenderOptions extends Omit<RenderOptions, "wrapper"> {
  initialEntries?: string[];
  useMemoryRouter?: boolean;
}

/**
 * Custom render function that wraps components with all necessary providers
 */
function customRender(
  ui: ReactElement,
  options: CustomRenderOptions = {}
): ReturnType<typeof render> & { queryClient: QueryClient } {
  const { initialEntries = ["/"], useMemoryRouter = false, ...renderOptions } = options;

  const queryClient = createTestQueryClient();

  function Wrapper({ children }: WrapperProps) {
    const Router = useMemoryRouter ? (
      <MemoryRouter initialEntries={initialEntries}>{children}</MemoryRouter>
    ) : (
      <BrowserRouter>{children}</BrowserRouter>
    );

    return (
      <QueryClientProvider client={queryClient}>
        {Router}
      </QueryClientProvider>
    );
  }

  return {
    ...render(ui, { wrapper: Wrapper, ...renderOptions }),
    queryClient,
  };
}

/**
 * Render with just QueryClient provider (no router)
 */
function renderWithQuery(
  ui: ReactElement,
  options: Omit<RenderOptions, "wrapper"> = {}
): ReturnType<typeof render> & { queryClient: QueryClient } {
  const queryClient = createTestQueryClient();

  function Wrapper({ children }: WrapperProps) {
    return (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );
  }

  return {
    ...render(ui, { wrapper: Wrapper, ...options }),
    queryClient,
  };
}

/**
 * Render with MemoryRouter for testing route-specific behavior
 */
function renderWithRouter(
  ui: ReactElement,
  {
    initialEntries = ["/"],
    ...options
  }: Omit<RenderOptions, "wrapper"> & { initialEntries?: string[] } = {}
): ReturnType<typeof render> & { queryClient: QueryClient } {
  return customRender(ui, { initialEntries, useMemoryRouter: true, ...options });
}

// Re-export everything from testing-library
export * from "@testing-library/react";
export { default as userEvent } from "@testing-library/user-event";

// Override render with custom render
export { customRender as render, renderWithQuery, renderWithRouter, createTestQueryClient };
