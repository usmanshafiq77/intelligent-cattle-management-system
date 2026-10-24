import { fireEvent, render, waitFor } from "@testing-library/react-native";

const mockDeliverMilkCsv = jest.fn().mockResolvedValue("downloaded");
jest.mock("../src/features/milk/milkExport", () => ({
  deliverMilkCsv: (...args) => mockDeliverMilkCsv(...args),
  milkRowsToCsv: jest.requireActual("../src/features/milk/milkExport").milkRowsToCsv,
}));

import {
  DailyMilkEntryScreen,
  LactationRecordsScreen,
  MilkAnalyticsScreen,
  MilkAvailabilityScreen,
  MilkDashboardScreen,
  MilkRecordDetailsScreen,
  MilkReportsScreen,
  detectProductionDrop,
} from "../src/features/milk/screens/MilkScreens";
import { ThemeProvider } from "../src/theme/ThemeProvider";

let mockFarm;
jest.mock("../src/features/farms/context/FarmProvider", () => ({ useFarm: () => mockFarm }));

const FARM = "11111111-1111-4111-8111-111111111111";
const COW = "22222222-2222-4222-8222-222222222222";
const LACTATION = "33333333-3333-4333-8333-333333333333";
const SESSION = "44444444-4444-4444-8444-444444444444";
const cow = { id: COW, tag_number: "C-101", name: "Daisy", sex: "FEMALE", category: "COW", status: "ACTIVE" };
const lactation = { id: LACTATION, cattle_id: COW, sequence_number: 1, start_date: "2026-01-01", dry_off_date: null, end_date: null, status: "ACTIVE" };
const session = { id: SESSION, cattle_id: COW, lactation_id: LACTATION, milking_date: "2026-10-20", session_kind: "MORNING", session_code: "MORNING", effective_volume_liters: "10.250", effective_notes: null, recorded_by_id: "user" };
const summary = { total_volume_liters: "10.250", recorded_animals: 1, record_count: 1, average_per_recorded_animal_liters: "10.250", buckets: [{ period_start: "2026-10-20", volume_liters: "10.250", recorded_animals: 1, record_count: 1 }] };
const breakdown = { session_totals: [{ session_kind: "MORNING", volume_liters: "10.250" }], animal_totals: [{ cattle_id: COW, volume_liters: "10.250" }] };

function api(overrides = {}) {
  return {
    listSessions: jest.fn().mockResolvedValue([session]), createSession: jest.fn().mockResolvedValue(session), getSession: jest.fn().mockResolvedValue(session),
    listLactations: jest.fn().mockResolvedValue([lactation]), createLactation: jest.fn().mockResolvedValue(lactation), transitionLactation: jest.fn().mockResolvedValue({ ...lactation, status: "DRY" }),
    listCorrections: jest.fn().mockResolvedValue([]), createCorrection: jest.fn().mockResolvedValue({ id: "correction" }),
    getProductionAnalytics: jest.fn().mockResolvedValue(summary), getBreakdownAnalytics: jest.fn().mockResolvedValue(breakdown),
    getAvailability: jest.fn().mockResolvedValue({ recorded_production_liters: "10.250", sold_liters: "4.000", available_liters: "6.250" }),
    getAnalyticsDataset: jest.fn().mockResolvedValue([{ cattle_id: COW, milking_date: "2026-10-20", session_kind: "MORNING", volume_liters: "10.250", lactation_number: 1, days_in_milk: 10 }]),
    ...overrides,
  };
}

const cattle = { list: jest.fn().mockResolvedValue([cow]) };
const mount = (node) => render(<ThemeProvider persistPreference={false}>{node}</ThemeProvider>);

beforeEach(() => {
  mockDeliverMilkCsv.mockClear(); cattle.list.mockClear();
  mockFarm = { status: "ready", activeFarm: { id: FARM, name: "Green Valley" }, can: jest.fn().mockReturnValue(true) };
});

test("daily entry selects an eligible cow and prevents duplicate taps while saving", async () => {
  let release; const service = api({ createSession: jest.fn(() => new Promise((resolve) => { release = resolve; })) });
  const screen = mount(<DailyMilkEntryScreen api={service} cattle={cattle} />);
  await waitFor(() => expect(screen.getByText("C-101 · Daisy")).toBeTruthy());
  fireEvent.press(screen.getByTestId(`cow-${COW}`));
  fireEvent.changeText(screen.getByTestId("milk-volume"), "12.375");
  fireEvent.press(screen.getByTestId("milk-submit"));
  fireEvent.press(screen.getByTestId("milk-submit"));
  expect(service.createSession).toHaveBeenCalledTimes(1);
  expect(service.createSession).toHaveBeenCalledWith(FARM, expect.objectContaining({ cattle_id: COW, lactation_id: LACTATION, session_kind: "MORNING", volume_liters: "12.375" }));
  release({ ...session, effective_volume_liters: "12.375" });
  await waitFor(() => expect(screen.getByText(/Saved 12.375 L/)).toBeTruthy());
});

test("dashboard uses real farm APIs and exposes authorized workflows", async () => {
  const service = api(); const navigate = jest.fn(); const screen = mount(<MilkDashboardScreen api={service} onNavigate={navigate} />);
  await waitFor(() => expect(service.listSessions).toHaveBeenCalledWith(FARM, { limit: 8 }));
  fireEvent.press(screen.getByText("Record milk"));
  expect(navigate).toHaveBeenCalledWith("/milk/entry");
  expect(screen.getAllByText("10.25 L").length).toBeGreaterThan(0);
});

test("worker record details remain read-only without correction permission", async () => {
  mockFarm.can = jest.fn((permission) => ["milk.view", "milk.record"].includes(permission));
  const screen = mount(<MilkRecordDetailsScreen api={api()} sessionId={SESSION} />);
  await waitFor(() => expect(screen.getByText(/10.25 L/)).toBeTruthy());
  expect(screen.queryByTestId("correction-submit")).toBeNull();
});

test("lactation manager creates a server-backed lactation", async () => {
  const service = api(); const screen = mount(<LactationRecordsScreen api={service} cattle={cattle} />);
  await waitFor(() => expect(screen.getByTestId(`cow-${COW}`)).toBeTruthy());
  fireEvent.press(screen.getByTestId(`cow-${COW}`));
  fireEvent.press(screen.getByTestId("lactation-submit"));
  await waitFor(() => expect(service.createLactation).toHaveBeenCalledWith(FARM, expect.objectContaining({ cattle_id: COW, sequence_number: 1 })));
});

test("analytics renders recorded buckets and does not synthesize missing dates", async () => {
  const screen = mount(<MilkAnalyticsScreen api={api()} />);
  await waitFor(() => expect(screen.getByLabelText("Milk production trend")).toBeTruthy());
  expect(screen.getByText("2026-10-20")).toBeTruthy();
});

test("availability is hidden unless finance permission is verified", () => {
  mockFarm.can = jest.fn((permission) => permission === "milk.view");
  const service = api(); const screen = mount(<MilkAvailabilityScreen api={service} />);
  expect(screen.getByText("Finance permission required")).toBeTruthy();
  expect(service.getAvailability).not.toHaveBeenCalled();
});

test("reports export the authenticated analytics dataset as CSV", async () => {
  const service = api(); const screen = mount(<MilkReportsScreen api={service} />);
  await waitFor(() => expect(screen.getByTestId("milk-export-csv")).toBeTruthy());
  fireEvent.press(screen.getByTestId("milk-export-csv"));
  await waitFor(() => expect(service.getAnalyticsDataset).toHaveBeenCalledWith(FARM, expect.objectContaining({ limit: 5000, offset: 0 })));
  expect(mockDeliverMilkCsv).toHaveBeenCalledWith(expect.stringContaining("cattle_id"), expect.stringMatching(/^milk-production-.*\.csv$/));
});

test("drop indicator requires sufficient completed observations and states the threshold", () => {
  const buckets = [10, 10, 10, 10, 7].map((volume, index) => ({ period_start: `2026-10-${String(index + 10).padStart(2, "0")}`, volume_liters: String(volume) }));
  expect(detectProductionDrop(buckets, "2026-10-20")).toEqual(expect.objectContaining({ reductionPercent: 30 }));
  expect(detectProductionDrop(buckets.slice(0, 4), "2026-10-20")).toBeNull();
});
