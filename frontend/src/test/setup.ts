import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterAll, afterEach, beforeAll } from "vitest";
import { setupServer } from "msw/node";
import { handlers } from "./mocks/handlers";

// Setup MSW server
export const server = setupServer(...handlers);

// Start server before all tests
beforeAll(() => {
  server.listen({ onUnhandledRequest: "error" });
});

// Reset handlers after each test to ensure test isolation
afterEach(() => {
  server.resetHandlers();
  cleanup();
  // Clear localStorage between tests
  localStorage.clear();
});

// Clean up after all tests are done
afterAll(() => {
  server.close();
});

// Mock window.matchMedia for components that use it
Object.defineProperty(window, "matchMedia", {
  writable: true,
  value: (query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
  }),
});

// Mock ResizeObserver
class ResizeObserverMock {
  observe() {}
  unobserve() {}
  disconnect() {}
}

window.ResizeObserver = ResizeObserverMock;

// Mock IntersectionObserver
class IntersectionObserverMock {
  root = null;
  rootMargin = "";
  thresholds = [];
  observe() {}
  unobserve() {}
  disconnect() {}
  takeRecords() {
    return [];
  }
}

window.IntersectionObserver =
  IntersectionObserverMock as unknown as typeof IntersectionObserver;
