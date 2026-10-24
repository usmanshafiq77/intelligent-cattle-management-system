import { act, fireEvent, render, waitFor } from "@testing-library/react-native";

import { ApiError } from "../src/api/errors";
import { FarmCreateScreen } from "../src/features/farms/screens/FarmCreateScreen";
import { FarmDetailsScreen } from "../src/features/farms/screens/FarmDetailsScreen";
import { FarmSelectionScreen } from "../src/features/farms/screens/FarmSelectionScreen";
import { ThemeProvider } from "../src/theme/ThemeProvider";

let mockFarm;
jest.mock("../src/features/farms/context/FarmProvider", () => ({ useFarm: () => mockFarm }));

const FARM = Object.freeze({ id: "farm-a", name: "Green Valley Dairy", owner_id: "user-a", location: "Lahore", description: "A verified dairy farm", created_at: "2026-10-17T00:00:00Z" });

function deferred() {
  let resolve;
  const promise = new Promise((resolvePromise) => { resolve = resolvePromise; });
  return { promise, resolve };
}

function renderThemed(component) {
  return render(<ThemeProvider persistPreference={false}>{component}</ThemeProvider>);
}

beforeEach(() => {
  mockFarm = {
    status: "no-farms",
    farms: [],
    activeFarm: null,
    membership: null,
    permissions: [],
    issue: null,
    isLoading: false,
    createFarm: jest.fn(),
    selectFarm: jest.fn(),
    refreshFarms: jest.fn(),
    can: jest.fn(() => true),
  };
});

test("farm creation form renders the exact supported fields", () => {
  const screen = renderThemed(<FarmCreateScreen onBack={jest.fn()} createFarm={jest.fn()} />);
  expect(screen.getByTestId("farm-name")).toBeTruthy();
  expect(screen.getByTestId("farm-location")).toBeTruthy();
  expect(screen.getByTestId("farm-description")).toBeTruthy();
  expect(screen.queryByText("Edit Farm")).toBeNull();
});

test("farm creation validates required and backend length-constrained fields before requesting", () => {
  const createFarm = jest.fn();
  const screen = renderThemed(<FarmCreateScreen onBack={jest.fn()} createFarm={createFarm} />);
  fireEvent.press(screen.getByTestId("farm-create-submit"));
  expect(screen.getByText("Farm name is required.")).toBeTruthy();
  expect(createFarm).not.toHaveBeenCalled();

  fireEvent.changeText(screen.getByTestId("farm-name"), "x");
  fireEvent.press(screen.getByTestId("farm-create-submit"));
  expect(screen.getByText("Farm name must contain at least 2 characters.")).toBeTruthy();
});

test("successful creation sends normalized supported payload and navigates only after verified activation", async () => {
  const createFarm = jest.fn().mockResolvedValue({ created: true, selected: true, farm: FARM });
  const onCreated = jest.fn();
  const screen = renderThemed(<FarmCreateScreen onBack={jest.fn()} onCreated={onCreated} createFarm={createFarm} />);
  fireEvent.changeText(screen.getByTestId("farm-name"), "  Green Valley Dairy  ");
  fireEvent.changeText(screen.getByTestId("farm-location"), " Lahore ");
  fireEvent.changeText(screen.getByTestId("farm-description"), " ");
  fireEvent.press(screen.getByTestId("farm-create-submit"));
  await waitFor(() => expect(onCreated).toHaveBeenCalledWith(FARM));
  expect(createFarm).toHaveBeenCalledWith({ name: "Green Valley Dairy", location: "Lahore", description: null });
});

test("creation submission is not duplicated while a request is pending", async () => {
  const pending = deferred();
  const createFarm = jest.fn(() => pending.promise);
  const screen = renderThemed(<FarmCreateScreen onBack={jest.fn()} createFarm={createFarm} />);
  fireEvent.changeText(screen.getByTestId("farm-name"), "Green Valley");
  fireEvent.press(screen.getByTestId("farm-create-submit"));
  fireEvent.press(screen.getByTestId("farm-create-submit"));
  expect(createFarm).toHaveBeenCalledTimes(1);
  pending.resolve({ created: false, error: new ApiError("conflict", { status: 409 }) });
  await waitFor(() => expect(screen.getByText(/conflicts with the current server state/i)).toBeTruthy());
});

test("backend field errors and ambiguous network outcomes are shown safely", async () => {
  const fieldError = new ApiError("invalid", { status: 422, fieldErrors: { name: ["Name is already reserved"] } });
  const createFarm = jest.fn().mockResolvedValueOnce({ created: false, error: fieldError }).mockResolvedValueOnce({ created: false, error: new ApiError("offline", { code: "NETWORK_ERROR", category: "network" }), ambiguous: true });
  const screen = renderThemed(<FarmCreateScreen onBack={jest.fn()} createFarm={createFarm} />);
  fireEvent.changeText(screen.getByTestId("farm-name"), "Green Valley");
  fireEvent.press(screen.getByTestId("farm-create-submit"));
  await waitFor(() => expect(screen.getByText("Name is already reserved")).toBeTruthy());
  fireEvent.press(screen.getByTestId("farm-create-submit"));
  await waitFor(() => expect(screen.getByText(/could not confirm whether the farm was created/i)).toBeTruthy());
});

test("creation confirmed but permission hydration unavailable does not permit another blind retry", async () => {
  const screen = renderThemed(<FarmCreateScreen onBack={jest.fn()} createFarm={jest.fn().mockResolvedValue({ created: true, selected: false, farm: FARM })} />);
  fireEvent.changeText(screen.getByTestId("farm-name"), "Green Valley");
  fireEvent.press(screen.getByTestId("farm-create-submit"));
  await waitFor(() => expect(screen.getByText(/farm was created, but its access could not be confirmed/i)).toBeTruthy());
});

test("selection screen supports verified multi-farm selection and refresh", () => {
  mockFarm = {
    ...mockFarm,
    status: "selection-required",
    farms: [FARM, { ...FARM, id: "farm-b", name: "River Farm" }],
  };
  const screen = renderThemed(<FarmSelectionScreen onBack={jest.fn()} onCreate={jest.fn()} />);
  fireEvent.press(screen.getByTestId("farm-option-farm-b"));
  expect(mockFarm.selectFarm).toHaveBeenCalledWith("farm-b");
  fireEvent.press(screen.getByText("Refresh farm list"));
  expect(mockFarm.refreshFarms).toHaveBeenCalled();
});

test("selection screen provides new-user onboarding for an empty verified list", () => {
  const onCreate = jest.fn();
  const screen = renderThemed(<FarmSelectionScreen onBack={jest.fn()} onCreate={onCreate} />);
  expect(screen.getByText("Create your first farm")).toBeTruthy();
  fireEvent.press(screen.getByText("Create Farm"));
  expect(onCreate).toHaveBeenCalled();
});

test("farm details fetches and renders a server-confirmed read-only response", async () => {
  mockFarm = { ...mockFarm, status: "ready", activeFarm: FARM, membership: { role: "FARM_OWNER", status: "ACTIVE" }, can: jest.fn(() => true) };
  const api = { get: jest.fn().mockResolvedValue(FARM) };
  const screen = renderThemed(<FarmDetailsScreen onBack={jest.fn()} api={api} />);
  await waitFor(() => expect(screen.getByText("Green Valley Dairy")).toBeTruthy());
  expect(api.get).toHaveBeenCalledWith("farm-a", expect.any(Object));
  expect(screen.getByText(/Editing and deletion are unavailable/i)).toBeTruthy();
});

test.each([401, 403, 404, 409, 429, 503])("farm detail error %s is safe and retryable", async (status) => {
  mockFarm = { ...mockFarm, status: "ready", activeFarm: FARM, membership: { role: "WORKER", status: "ACTIVE" }, can: jest.fn(() => true) };
  const api = { get: jest.fn().mockRejectedValue(new ApiError("sensitive response", { status, retryAfterSeconds: 5 })) };
  const screen = renderThemed(<FarmDetailsScreen onBack={jest.fn()} api={api} />);
  await waitFor(() => expect(screen.getByText("Farm details unavailable")).toBeTruthy());
  expect(screen.queryByText("sensitive response")).toBeNull();
  expect(screen.getByText("Retry")).toBeTruthy();
});
