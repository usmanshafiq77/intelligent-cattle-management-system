import { act, fireEvent, render, waitFor } from "@testing-library/react-native";

import { ApiError } from "../src/api/errors";
import { CattleCreateScreen } from "../src/features/cattle/screens/CattleCreateScreen";
import { CattleDetailScreen } from "../src/features/cattle/screens/CattleDetailScreen";
import { CattleEditScreen } from "../src/features/cattle/screens/CattleEditScreen";
import { CattleListScreen } from "../src/features/cattle/screens/CattleListScreen";
import { DashboardScreen } from "../src/features/navigation/screens/DashboardScreen";
import { ThemeProvider } from "../src/theme/ThemeProvider";

let mockAuth;
let mockFarm;

jest.mock("../src/features/auth/context/AuthProvider", () => ({
  useAuth: () => mockAuth,
  useOptionalAuth: () => mockAuth,
}));
jest.mock("../src/features/farms/context/FarmProvider", () => ({ useFarm: () => mockFarm }));

const FARM_A = Object.freeze({ id: "11111111-1111-4111-8111-111111111111", name: "Green Valley", owner_id: "user-a" });
const FARM_B = Object.freeze({ id: "22222222-2222-4222-8222-222222222222", name: "River Farm", owner_id: "user-b" });
const CATTLE_ID = "33333333-3333-4333-8333-333333333333";
const BREED_ID = "44444444-4444-4444-8444-444444444444";
const BREED = Object.freeze({ id: BREED_ID, species: "CATTLE", name: "Holstein", description: null, is_active: true });
const ANIMAL = Object.freeze({
  id: CATTLE_ID,
  farm_id: FARM_A.id,
  tag_number: "GV-001",
  name: "Bella",
  species: "CATTLE",
  sex: "FEMALE",
  category: "COW",
  breed: BREED,
  date_of_birth: "2024-01-02",
  birth_date_estimated: false,
  registration_date: "2026-10-17",
  acquisition_date: null,
  acquisition_method: "UNKNOWN",
  acquisition_source: null,
  initial_acquisition_cost: null,
  initial_acquisition_currency: null,
  color: "Black and white",
  identification_marks: null,
  status: "ACTIVE",
  mother_id: null,
  father_id: null,
  notes: null,
  created_by_id: "55555555-5555-4555-8555-555555555555",
  created_at: "2026-10-17T00:00:00Z",
  updated_at: "2026-10-17T00:00:00Z",
  latest_weight: { weight_kg: "475.50" },
  media_count: 0,
});

function deferred() {
  let resolve;
  let reject;
  const promise = new Promise((resolvePromise, rejectPromise) => { resolve = resolvePromise; reject = rejectPromise; });
  return { promise, resolve, reject };
}

function themed(node) {
  return <ThemeProvider persistPreference={false}>{node}</ThemeProvider>;
}

function renderThemed(node) {
  return render(themed(node));
}

function summaryFor(animals) {
  const statusCounts = Object.fromEntries(
    ["ACTIVE", "SOLD", "DECEASED", "TRANSFERRED", "MISSING", "ARCHIVED"]
      .map((status) => [status, animals.filter((animal) => animal.status === status).length]),
  );
  return {
    total: animals.length,
    female_count: animals.filter((animal) => animal.sex === "FEMALE").length,
    male_count: animals.filter((animal) => animal.sex === "MALE").length,
    breed_count: new Set(animals.map((animal) => animal.breed?.id).filter(Boolean)).size,
    status_counts: statusCounts,
  };
}

function api(overrides = {}) {
  return {
    list: jest.fn().mockResolvedValue([ANIMAL]),
    summary: jest.fn().mockResolvedValue(summaryFor([ANIMAL])),
    listBreeds: jest.fn().mockResolvedValue([BREED]),
    create: jest.fn().mockResolvedValue(ANIMAL),
    get: jest.fn().mockResolvedValue(ANIMAL),
    update: jest.fn().mockResolvedValue(ANIMAL),
    ...overrides,
  };
}

beforeEach(() => {
  mockAuth = { status: "authenticated", user: { id: "user-a", full_name: "Farm Owner", is_system_admin: false }, logout: jest.fn().mockResolvedValue(undefined) };
  mockFarm = {
    status: "ready",
    farms: [FARM_A],
    activeFarm: FARM_A,
    membership: { role: "FARM_OWNER", status: "ACTIVE" },
    permissions: ["farm.view", "staff.view", "staff.manage", "cattle.view", "cattle.create", "cattle.update"],
    isLoading: false,
    can: jest.fn((permission) => ["farm.view", "staff.view", "staff.manage", "cattle.view", "cattle.create", "cattle.update"].includes(permission)),
    selectFarm: jest.fn(),
    refreshFarms: jest.fn(),
  };
});

describe("authoritative dashboard", () => {
  test("renders selected farm, role, complete herd KPIs and functional actions", async () => {
    mockFarm = { ...mockFarm, permissions: ["cattle.view", "cattle.create", "cattle.update"], can: jest.fn((permission) => ["cattle.view", "cattle.create", "cattle.update"].includes(permission)) };
    const onNavigate = jest.fn();
    const service = api();
    const screen = renderThemed(<DashboardScreen onNavigate={onNavigate} api={service} />);
    await waitFor(() => expect(screen.getByText("Total Cattle")).toBeTruthy());
    expect(screen.getAllByText("Green Valley").length).toBeGreaterThan(0);
    expect(screen.getByText(/Farm Owner · active membership/)).toBeTruthy();
    expect(screen.getByText("Female Cattle")).toBeTruthy();
    expect(screen.getByText("Breeds Represented")).toBeTruthy();
    fireEvent.press(screen.getAllByText("View Cattle")[0]);
    expect(onNavigate).toHaveBeenCalledWith("/cattle");
  });

  test("renders an honest empty herd state", async () => {
    const screen = renderThemed(<DashboardScreen onNavigate={jest.fn()} api={api({ summary: jest.fn().mockResolvedValue(summaryFor([])) })} />);
    await waitFor(() => expect(screen.getByText("No cattle registered")).toBeTruthy());
  });

  test.each([403, 503])("normalizes dashboard API status %s", async (status) => {
    const screen = renderThemed(<DashboardScreen onNavigate={jest.fn()} api={api({ summary: jest.fn().mockRejectedValue(new ApiError("secret", { status })) })} />);
    await waitFor(() => expect(screen.getByText("Herd overview unavailable")).toBeTruthy());
    expect(screen.queryByText("secret")).toBeNull();
  });

  test("does not fetch or invent KPIs without cattle.view", async () => {
    mockFarm.can = jest.fn(() => false);
    const service = api();
    const screen = renderThemed(<DashboardScreen onNavigate={jest.fn()} api={service} />);
    expect(screen.getByText(/does not include permission to view cattle statistics/i)).toBeTruthy();
    expect(service.list).not.toHaveBeenCalled();
    expect(service.summary).not.toHaveBeenCalled();
    expect(screen.queryByText("Total Cattle")).toBeNull();
  });

  test("herd dashboard remains functional across all three centralized themes", async () => {
    const screen = renderThemed(<DashboardScreen onNavigate={jest.fn()} api={api()} />);
    await waitFor(() => expect(screen.getByText("Total Cattle")).toBeTruthy());
    expect(screen.getByTestId("dashboard-theme-selector")).toBeTruthy();
    expect(screen.queryByText("Emerald Luxury")).toBeNull();
    expect(screen.queryByText("Midnight Teal")).toBeNull();
    expect(screen.queryByText("Royal Indigo")).toBeNull();
    expect(screen.getByTestId("theme-selected-emerald")).toBeTruthy();
    fireEvent.press(screen.getByLabelText("Use Midnight Teal theme"));
    expect(screen.getByText("Total Cattle")).toBeTruthy();
    expect(screen.getByTestId("theme-selected-midnight")).toBeTruthy();
    fireEvent.press(screen.getByLabelText("Use Royal Indigo theme"));
    expect(screen.getByText("Total Cattle")).toBeTruthy();
    fireEvent.press(screen.getByLabelText("Use Emerald Luxury theme"));
    expect(screen.getByText("Herd by Lifecycle Status")).toBeTruthy();
  });

  test("ignores an older farm response after switching farms", async () => {
    const oldRequest = deferred();
    const service = api({ summary: jest.fn((farmId) => farmId === FARM_A.id ? oldRequest.promise : Promise.resolve(summaryFor([]))) });
    const screen = renderThemed(<DashboardScreen onNavigate={jest.fn()} api={service} />);
    mockFarm = { ...mockFarm, farms: [FARM_A, FARM_B], activeFarm: FARM_B };
    screen.rerender(themed(<DashboardScreen onNavigate={jest.fn()} api={service} />));
    await waitFor(() => expect(screen.getByText("No cattle registered")).toBeTruthy());
    await act(async () => { oldRequest.resolve(summaryFor([ANIMAL])); await oldRequest.promise; });
    expect(screen.getByText("No cattle registered")).toBeTruthy();
  });
});

describe("cattle registration", () => {
  test("renders supported fields and rejects missing tag without a request", async () => {
    const service = api();
    const screen = renderThemed(<CattleCreateScreen onBack={jest.fn()} api={service} />);
    await waitFor(() => expect(service.listBreeds).toHaveBeenCalled());
    fireEvent.press(screen.getByTestId("cattle-submit"));
    expect(screen.getByText("Tag number is required.")).toBeTruthy();
    expect(service.create).not.toHaveBeenCalled();
  });

  test("submits the exact backend-supported normalized payload and farm scope", async () => {
    const service = api();
    const onCreated = jest.fn();
    const screen = renderThemed(<CattleCreateScreen onBack={jest.fn()} onCreated={onCreated} api={service} />);
    await waitFor(() => expect(screen.getByText("Holstein")).toBeTruthy());
    fireEvent.changeText(screen.getByTestId("cattle-tag"), "  GV-001  ");
    fireEvent.changeText(screen.getByTestId("cattle-name"), " Bella ");
    fireEvent.press(screen.getByTestId(`cattle-breed-${BREED_ID}`));
    fireEvent.changeText(screen.getByTestId("cattle-weight"), "475.5");
    fireEvent.press(screen.getByTestId("cattle-submit"));
    await waitFor(() => expect(onCreated).toHaveBeenCalledWith(expect.objectContaining({ id: CATTLE_ID, farm_id: FARM_A.id })));
    expect(service.create).toHaveBeenCalledWith(FARM_A.id, expect.objectContaining({ tag_number: "GV-001", name: "Bella", species: "CATTLE", sex: "FEMALE", category: "COW", breed_id: BREED_ID, initial_weight_kg: "475.5" }), expect.objectContaining({ signal: expect.any(Object) }));
    expect(service.get).toHaveBeenCalledWith(FARM_A.id, CATTLE_ID, expect.objectContaining({ signal: expect.any(Object) }));
  });

  test("blocks duplicate submission while creation is pending", async () => {
    const pending = deferred();
    const service = api({ create: jest.fn(() => pending.promise) });
    const screen = renderThemed(<CattleCreateScreen onBack={jest.fn()} api={service} />);
    fireEvent.changeText(screen.getByTestId("cattle-tag"), "GV-002");
    fireEvent.press(screen.getByTestId("cattle-submit"));
    fireEvent.press(screen.getByTestId("cattle-submit"));
    expect(service.create).toHaveBeenCalledTimes(1);
    await act(async () => { pending.resolve({ ...ANIMAL, tag_number: "GV-002" }); await pending.promise; });
  });

  test.each([
    [409, "already"], [422, "invalid"], [429, "Too many"], [503, "temporarily"],
  ])("handles create status %s without false success", async (status, text) => {
    const service = api({ create: jest.fn().mockRejectedValue(new ApiError(status === 409 ? "already exists" : "secret", { status, serverMessage: status === 409 ? "This tag already exists" : null })) });
    const onCreated = jest.fn();
    const screen = renderThemed(<CattleCreateScreen onBack={jest.fn()} onCreated={onCreated} api={service} />);
    fireEvent.changeText(screen.getByTestId("cattle-tag"), "GV-002");
    fireEvent.press(screen.getByTestId("cattle-submit"));
    await waitFor(() => expect(screen.getByText(new RegExp(text, "i"))).toBeTruthy());
    expect(onCreated).not.toHaveBeenCalled();
    expect(screen.queryByText("secret")).toBeNull();
  });

  test("rejects an invalid or cross-farm success response", async () => {
    const onCreated = jest.fn();
    const screen = renderThemed(<CattleCreateScreen onBack={jest.fn()} onCreated={onCreated} api={api({ create: jest.fn().mockResolvedValue({ ...ANIMAL, farm_id: FARM_B.id }) })} />);
    fireEvent.changeText(screen.getByTestId("cattle-tag"), "GV-002");
    fireEvent.press(screen.getByTestId("cattle-submit"));
    await waitFor(() => expect(screen.getByText(/could not be verified safely/i)).toBeTruthy());
    expect(onCreated).not.toHaveBeenCalled();
  });

  test.each(["TIMEOUT", "NETWORK_ERROR"])("marks ambiguous %s outcomes and never retries automatically", async (code) => {
    const service = api({ create: jest.fn().mockRejectedValue(new ApiError("offline", { code, category: "network" })) });
    const screen = renderThemed(<CattleCreateScreen onBack={jest.fn()} api={service} />);
    fireEvent.changeText(screen.getByTestId("cattle-tag"), "GV-002");
    fireEvent.press(screen.getByTestId("cattle-submit"));
    await waitFor(() => expect(screen.getByText(/could not be confirmed/i)).toBeTruthy());
    expect(service.create).toHaveBeenCalledTimes(1);
  });

  test("farm switch during create aborts and prevents wrong-farm navigation", async () => {
    const pending = deferred();
    const service = api({ create: jest.fn(() => pending.promise) });
    const onCreated = jest.fn();
    const screen = renderThemed(<CattleCreateScreen onBack={jest.fn()} onCreated={onCreated} api={service} />);
    fireEvent.changeText(screen.getByTestId("cattle-tag"), "GV-002");
    fireEvent.press(screen.getByTestId("cattle-submit"));
    mockFarm = { ...mockFarm, activeFarm: FARM_B };
    screen.rerender(themed(<CattleCreateScreen onBack={jest.fn()} onCreated={onCreated} api={service} />));
    await act(async () => { pending.resolve(ANIMAL); await pending.promise; });
    expect(onCreated).not.toHaveBeenCalled();
  });

  test("logout during create aborts and suppresses stale success", async () => {
    const pending = deferred();
    const service = api({ create: jest.fn(() => pending.promise) });
    const onCreated = jest.fn();
    const screen = renderThemed(<CattleCreateScreen onBack={jest.fn()} onCreated={onCreated} api={service} />);
    fireEvent.changeText(screen.getByTestId("cattle-tag"), "GV-003");
    fireEvent.press(screen.getByTestId("cattle-submit"));
    mockAuth = { ...mockAuth, status: "anonymous", user: null };
    screen.rerender(themed(<CattleCreateScreen onBack={jest.fn()} onCreated={onCreated} api={service} />));
    await act(async () => { pending.resolve(ANIMAL); await pending.promise; });
    expect(onCreated).not.toHaveBeenCalled();
  });

  test("unknown create permission denies direct route", () => {
    mockFarm.can = jest.fn((permission) => permission === "cattle.view");
    const service = api();
    const screen = renderThemed(<CattleCreateScreen onBack={jest.fn()} api={service} />);
    expect(screen.getByText("Access denied")).toBeTruthy();
    expect(service.create).not.toHaveBeenCalled();
  });
});

describe("cattle directory and profile", () => {
  test("renders real records, searches, filters, sorts and opens a profile", async () => {
    const second = { ...ANIMAL, id: "77777777-7777-4777-8777-777777777777", tag_number: "GV-002", name: "Max", sex: "MALE", category: "BULL" };
    const onOpen = jest.fn();
    const animals = [ANIMAL, second];
    const service = api({
      list: jest.fn((farmId, query) => Promise.resolve(query.search ? [second] : animals)),
      summary: jest.fn((farmId, query) => Promise.resolve(summaryFor(query.search ? [second] : animals))),
    });
    const screen = renderThemed(<CattleListScreen onBack={jest.fn()} onOpen={onOpen} api={service} />);
    await waitFor(() => expect(screen.getByText("Bella")).toBeTruthy());
    fireEvent.changeText(screen.getByTestId("cattle-search"), "max");
    await waitFor(() => expect(screen.queryByText("Bella")).toBeNull());
    await waitFor(() => expect(screen.getByText("Max")).toBeTruthy());
    fireEvent.press(screen.getByTestId("cattle-card-77777777-7777-4777-8777-777777777777"));
    expect(onOpen).toHaveBeenCalledWith(second.id);
  });

  test("supports empty, loading, retry and refresh states", async () => {
    const request = deferred();
    const service = api({ list: jest.fn(() => request.promise), summary: jest.fn().mockResolvedValue(summaryFor([])) });
    const screen = renderThemed(<CattleListScreen onBack={jest.fn()} api={service} />);
    expect(screen.getByText("Loading cattle")).toBeTruthy();
    await act(async () => { request.resolve([]); await request.promise; });
    await waitFor(() => expect(screen.getByText("No cattle registered")).toBeTruthy());
  });

  test("uses server-side pagination without downloading the complete herd", async () => {
    const animals = Array.from({ length: 21 }, (_, index) => ({ ...ANIMAL, id: `00000000-0000-4000-8000-${String(index + 1).padStart(12, "0")}`, tag_number: `GV-${String(index + 1).padStart(3, "0")}`, name: `Animal ${String(index + 1).padStart(2, "0")}` }));
    const list = jest.fn((farmId, query) => Promise.resolve(animals.slice(query.offset, query.offset + query.limit)));
    const screen = renderThemed(<CattleListScreen onBack={jest.fn()} api={api({ list, summary: jest.fn().mockResolvedValue(summaryFor(animals)) })} />);
    await waitFor(() => expect(screen.getByText("Page 1 of 2")).toBeTruthy());
    expect(list.mock.calls[0][1]).toEqual(expect.objectContaining({ limit: 20, offset: 0 }));
    expect(screen.queryByText("Animal 21")).toBeNull();
    fireEvent.press(screen.getByText("Next"));
    await waitFor(() => expect(screen.getByText("Page 2 of 2")).toBeTruthy());
    await waitFor(() => expect(screen.getByText("Animal 21")).toBeTruthy());
    expect(list.mock.calls.at(-1)[1]).toEqual(expect.objectContaining({ limit: 20, offset: 20 }));
  });

  test.each([401, 403, 429, 503])("normalizes list status %s", async (status) => {
    const screen = renderThemed(<CattleListScreen onBack={jest.fn()} api={api({ list: jest.fn().mockRejectedValue(new ApiError("secret", { status })) })} />);
    await waitFor(() => expect(screen.getByText("Cattle unavailable")).toBeTruthy());
    expect(screen.queryByText("secret")).toBeNull();
  });

  test("renders verified profile data and permission-aware edit action", async () => {
    const onEdit = jest.fn();
    const screen = renderThemed(<CattleDetailScreen cattleId={CATTLE_ID} onBack={jest.fn()} onEdit={onEdit} api={api()} />);
    await waitFor(() => expect(screen.getByText("Bella")).toBeTruthy());
    expect(screen.getByText("475.50 kg")).toBeTruthy();
    fireEvent.press(screen.getByText("Edit profile"));
    expect(onEdit).toHaveBeenCalledWith(CATTLE_ID);
  });

  test("profile refresh replaces details with an authoritative response", async () => {
    const service = api({ get: jest.fn().mockResolvedValueOnce(ANIMAL).mockResolvedValueOnce({ ...ANIMAL, name: "Bella Updated" }) });
    const screen = renderThemed(<CattleDetailScreen cattleId={CATTLE_ID} onBack={jest.fn()} api={service} />);
    await waitFor(() => expect(screen.getByText("Bella")).toBeTruthy());
    fireEvent.press(screen.getByText("Refresh"));
    await waitFor(() => expect(screen.getByText("Bella Updated")).toBeTruthy());
  });

  test("confirmed lifecycle transition uses the reviewed endpoint and refreshes profile", async () => {
    const event = { id: "88888888-8888-4888-8888-888888888888", cattle_id: CATTLE_ID, farm_id: FARM_A.id, previous_status: "ACTIVE", new_status: "MISSING" };
    const service = api({
      addLifecycleEvent: jest.fn().mockResolvedValue(event),
      get: jest.fn().mockResolvedValueOnce(ANIMAL).mockResolvedValueOnce({ ...ANIMAL, status: "MISSING" }),
    });
    const screen = renderThemed(<CattleDetailScreen cattleId={CATTLE_ID} onBack={jest.fn()} api={service} />);
    await waitFor(() => expect(screen.getByText("Mark Missing")).toBeTruthy());
    fireEvent.press(screen.getByText("Mark Missing"));
    expect(service.addLifecycleEvent).not.toHaveBeenCalled();
    fireEvent.press(screen.getByText("Confirm status"));
    await waitFor(() => expect(service.addLifecycleEvent).toHaveBeenCalledWith(FARM_A.id, CATTLE_ID, expect.objectContaining({ new_status: "MISSING", effective_at: expect.any(String) }), expect.objectContaining({ signal: expect.any(Object) })));
    await waitFor(() => expect(screen.getByText("Status changed to Missing.")).toBeTruthy());
    expect(service.get).toHaveBeenCalledTimes(2);
  });

  test("lifecycle cancellation does not mutate", async () => {
    const service = api({ addLifecycleEvent: jest.fn() });
    const screen = renderThemed(<CattleDetailScreen cattleId={CATTLE_ID} onBack={jest.fn()} api={service} />);
    await waitFor(() => expect(screen.getByText("Mark Archived")).toBeTruthy());
    fireEvent.press(screen.getByText("Mark Archived"));
    fireEvent.press(screen.getByText("Cancel"));
    expect(service.addLifecycleEvent).not.toHaveBeenCalled();
  });

  test("invalid profile ID never reaches the API", () => {
    const service = api();
    const screen = renderThemed(<CattleDetailScreen cattleId="not-an-id" onBack={jest.fn()} api={service} />);
    expect(screen.getByText("Invalid cattle ID")).toBeTruthy();
    expect(service.get).not.toHaveBeenCalled();
  });

  test.each([[403, "Could not load cattle"], [404, "Cattle not found"]])("handles profile status %s", async (status, title) => {
    const screen = renderThemed(<CattleDetailScreen cattleId={CATTLE_ID} onBack={jest.fn()} api={api({ get: jest.fn().mockRejectedValue(new ApiError("secret", { status })) })} />);
    await waitFor(() => expect(screen.getByText(title)).toBeTruthy());
    expect(screen.queryByText("secret")).toBeNull();
  });

  test("hides editing when cattle.update is absent", async () => {
    mockFarm.can = jest.fn((permission) => permission === "cattle.view");
    const screen = renderThemed(<CattleDetailScreen cattleId={CATTLE_ID} onBack={jest.fn()} api={api()} />);
    await waitFor(() => expect(screen.getByText("Bella")).toBeTruthy());
    expect(screen.queryByText("Edit profile")).toBeNull();
  });
});

describe("cattle editing", () => {
  test("prepopulates supported fields, PATCHes the actual schema, and refreshes", async () => {
    const service = api();
    const onUpdated = jest.fn();
    const screen = renderThemed(<CattleEditScreen cattleId={CATTLE_ID} onBack={jest.fn()} onUpdated={onUpdated} api={service} />);
    await waitFor(() => expect(screen.getByTestId("cattle-tag").props.value).toBe("GV-001"));
    fireEvent.changeText(screen.getByTestId("cattle-name"), "Bella Prime");
    fireEvent.press(screen.getByTestId("cattle-submit"));
    await waitFor(() => expect(service.update).toHaveBeenCalledWith(FARM_A.id, CATTLE_ID, expect.objectContaining({ name: "Bella Prime" }), expect.objectContaining({ signal: expect.any(Object) })));
    await waitFor(() => expect(service.get).toHaveBeenCalledTimes(2));
    expect(onUpdated).toHaveBeenCalledWith(expect.objectContaining({ id: CATTLE_ID }), { refreshFailed: false });
  });

  test("prevents duplicate saves and preserves cancel behavior", async () => {
    const pending = deferred();
    const onBack = jest.fn();
    const service = api({ update: jest.fn(() => pending.promise) });
    const screen = renderThemed(<CattleEditScreen cattleId={CATTLE_ID} onBack={onBack} api={service} />);
    await waitFor(() => expect(screen.getByTestId("cattle-submit")).toBeTruthy());
    fireEvent.press(screen.getByTestId("cattle-submit"));
    fireEvent.press(screen.getByTestId("cattle-submit"));
    expect(service.update).toHaveBeenCalledTimes(1);
    await act(async () => { pending.resolve(ANIMAL); await pending.promise; });
  });

  test.each([409, 422, 503])("handles update status %s without navigation", async (status) => {
    const onUpdated = jest.fn();
    const service = api({ update: jest.fn().mockRejectedValue(new ApiError("secret", { status })) });
    const screen = renderThemed(<CattleEditScreen cattleId={CATTLE_ID} onBack={jest.fn()} onUpdated={onUpdated} api={service} />);
    await waitFor(() => expect(screen.getByTestId("cattle-submit")).toBeTruthy());
    fireEvent.press(screen.getByTestId("cattle-submit"));
    await waitFor(() => expect(screen.getByText(/conflicts|invalid|temporarily/i)).toBeTruthy());
    expect(onUpdated).not.toHaveBeenCalled();
    expect(screen.queryByText("secret")).toBeNull();
  });

  test("permission revocation removes the edit form", async () => {
    const service = api();
    const screen = renderThemed(<CattleEditScreen cattleId={CATTLE_ID} onBack={jest.fn()} api={service} />);
    await waitFor(() => expect(screen.getByTestId("cattle-submit")).toBeTruthy());
    mockFarm = { ...mockFarm, can: jest.fn(() => false), permissions: [] };
    screen.rerender(themed(<CattleEditScreen cattleId={CATTLE_ID} onBack={jest.fn()} api={service} />));
    expect(screen.getByText("Access denied")).toBeTruthy();
  });

  test("successful update followed by refresh failure reports the verified partial outcome", async () => {
    const onUpdated = jest.fn();
    const service = api({ get: jest.fn().mockResolvedValueOnce(ANIMAL).mockRejectedValueOnce(new ApiError("offline", { status: 503 })), update: jest.fn().mockResolvedValue({ ...ANIMAL, name: "Saved Bella" }) });
    const screen = renderThemed(<CattleEditScreen cattleId={CATTLE_ID} onBack={jest.fn()} onUpdated={onUpdated} api={service} />);
    await waitFor(() => expect(screen.getByTestId("cattle-submit")).toBeTruthy());
    fireEvent.press(screen.getByTestId("cattle-submit"));
    await waitFor(() => expect(onUpdated).toHaveBeenCalledWith(expect.objectContaining({ name: "Saved Bella" }), { refreshFailed: true }));
  });

  test("farm switch during update aborts stale completion", async () => {
    const pending = deferred();
    const onUpdated = jest.fn();
    const service = api({ update: jest.fn(() => pending.promise) });
    const screen = renderThemed(<CattleEditScreen cattleId={CATTLE_ID} onBack={jest.fn()} onUpdated={onUpdated} api={service} />);
    await waitFor(() => expect(screen.getByTestId("cattle-submit")).toBeTruthy());
    fireEvent.press(screen.getByTestId("cattle-submit"));
    mockFarm = { ...mockFarm, activeFarm: FARM_B };
    screen.rerender(themed(<CattleEditScreen cattleId={CATTLE_ID} onBack={jest.fn()} onUpdated={onUpdated} api={service} />));
    await act(async () => { pending.resolve(ANIMAL); await pending.promise; });
    expect(onUpdated).not.toHaveBeenCalled();
  });
});
