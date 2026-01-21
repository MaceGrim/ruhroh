// Test utilities barrel export
export { server } from "./setup";
export {
  handlers,
  mockDocument,
  mockThread,
  mockUser,
  mockSearchResult,
  mockHealthStatus,
  mockAdminStats,
  mockDocuments,
  mockThreads,
  mockUsers,
} from "./mocks/handlers";

// Re-export custom render functions and testing utilities
export {
  render,
  renderWithQuery,
  renderWithRouter,
  createTestQueryClient,
  screen,
  waitFor,
  within,
  userEvent,
} from "./test-utils";
