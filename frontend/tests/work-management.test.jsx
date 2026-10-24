import { render, waitFor } from "@testing-library/react-native";
import { MyTasksScreen, NotificationInboxScreen, TasksDashboardScreen } from "../src/features/work/screens/WorkScreens";
import { ThemeProvider } from "../src/theme/ThemeProvider";

let mockFarm;
jest.mock("../src/features/farms/context/FarmProvider", () => ({ useFarm: () => mockFarm }));
const FARM_ID = "11111111-1111-4111-8111-111111111111";
const TASK = { id: "22222222-2222-4222-8222-222222222222", farm_id: FARM_ID, title: "Morning feeding", category: "FEEDING", priority: "HIGH", status: "OPEN", due_at: "2026-10-25T06:00:00Z", version: 1, assignee_ids: [], is_overdue: false };
const renderScreen = (node) => render(<ThemeProvider persistPreference={false}>{node}</ThemeProvider>);

beforeEach(() => { mockFarm = { status: "ready", activeFarm: { id: FARM_ID, name: "Farm" }, can: jest.fn().mockReturnValue(true) }; });

test("task dashboard loads farm-scoped work and exposes operational navigation", async () => {
  const api = { listTasks: jest.fn().mockResolvedValue([TASK]) };
  const screen = renderScreen(<TasksDashboardScreen onNavigate={jest.fn()} api={api} />);
  await waitFor(() => expect(screen.getByText("Morning feeding")).toBeTruthy());
  expect(screen.getByText("Worker Assignments →")).toBeTruthy();
});

test("my tasks requests only assignments for the active user", async () => {
  const api = { listTasks: jest.fn().mockResolvedValue([TASK]), updateStatus: jest.fn() };
  const screen = renderScreen(<MyTasksScreen api={api} onOpen={jest.fn()} />);
  await waitFor(() => expect(screen.getByText("Morning feeding")).toBeTruthy());
  expect(api.listTasks).toHaveBeenCalledWith(FARM_ID, { mine: true });
});

test("notification inbox renders private unread count", async () => {
  const api = { notifications: jest.fn().mockResolvedValue({ items: [{ id: "n1", title: "Task assigned", message: "Morning feeding", read_at: null }], unread: 1 }), markAllRead: jest.fn() };
  const screen = renderScreen(<NotificationInboxScreen api={api} onOpen={jest.fn()} />);
  await waitFor(() => expect(screen.getByText("Mark all read (1 unread)")).toBeTruthy());
  expect(api.notifications).toHaveBeenCalledWith({ farm_id: FARM_ID });
});
