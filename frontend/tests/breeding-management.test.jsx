import { fireEvent, render, waitFor } from "@testing-library/react-native";

import { BreedingDashboardScreen, HeatCycleScreen, OffspringRegistrationScreen, PregnancyTrackingScreen } from "../src/features/breeding/screens/BreedingScreens";
import { ThemeProvider } from "../src/theme/ThemeProvider";

let mockFarm;
jest.mock("../src/features/farms/context/FarmProvider", () => ({ useFarm: () => mockFarm }));
const FARM = "11111111-1111-4111-8111-111111111111";

function api(overrides = {}) { return {
  dashboard: jest.fn().mockResolvedValue({ heat_observations: 1, planned_breedings: 0, completed_breedings: 1, currently_pregnant: 1, upcoming_calvings: 1, pending_follow_ups: 2, calves_born: 1 }),
  listReminders: jest.fn().mockResolvedValue([]), listHeat: jest.fn().mockResolvedValue([]), createHeat: jest.fn().mockResolvedValue({ id: "heat" }),
  listExams: jest.fn().mockResolvedValue([]), listLosses: jest.fn().mockResolvedValue([]), createExam: jest.fn().mockResolvedValue({ id: "exam" }),
  registerOffspring: jest.fn().mockResolvedValue({ id: "offspring" }), ...overrides,
}; }
const mount = (node) => render(<ThemeProvider persistPreference={false}>{node}</ThemeProvider>);

beforeEach(() => { mockFarm = { status: "ready", activeFarm: { id: FARM, name: "Farm" }, membership: { role: "FARM_OWNER" }, can: jest.fn().mockReturnValue(true) }; });

test("owner dashboard loads farm-scoped reproductive summary and working navigation", async () => {
  const service = api(); const navigate = jest.fn(); const screen = mount(<BreedingDashboardScreen api={service} onNavigate={navigate} />);
  await waitFor(() => expect(service.dashboard).toHaveBeenCalledWith(FARM));
  fireEvent.press(screen.getByText("Heat cycles"));
  expect(navigate).toHaveBeenCalledWith("/breeding/heat");
});

test("worker heat screen validates and submits an observation without clinical controls", async () => {
  mockFarm.membership.role = "WORKER";
  mockFarm.can = jest.fn((p) => ["breeding.view", "breeding.heat.record", "breeding.calving.record"].includes(p));
  const service = api(); const screen = mount(<HeatCycleScreen api={service} />);
  await waitFor(() => expect(service.listHeat).toHaveBeenCalledWith(FARM));
  fireEvent.changeText(screen.getByTestId("heat-cattle"), "22222222-2222-4222-8222-222222222222");
  fireEvent.changeText(screen.getByTestId("heat-signs"), "Standing heat observed");
  fireEvent.press(screen.getByTestId("heat-submit"));
  await waitFor(() => expect(service.createHeat).toHaveBeenCalledWith(FARM, expect.objectContaining({ cattle_id: "22222222-2222-4222-8222-222222222222", create_reminder: true })));
});

test("owner can view pregnancy history but cannot see veterinarian diagnosis form", async () => {
  const service = api(); const screen = mount(<PregnancyTrackingScreen api={service} />);
  await waitFor(() => expect(service.listExams).toHaveBeenCalledWith(FARM));
  expect(screen.getByText(/only to an authorized Veterinarian/)).toBeTruthy();
  expect(screen.queryByTestId("exam-submit")).toBeNull();
});

test("authorized veterinarian receives the clinical examination workflow", async () => {
  mockFarm.membership.role = "VETERINARIAN";
  mockFarm.can = jest.fn((p) => ["breeding.view", "breeding.pregnancy.assess"].includes(p));
  const service = api(); const screen = mount(<PregnancyTrackingScreen api={service} />);
  await waitFor(() => expect(screen.getByTestId("exam-submit")).toBeTruthy());
  fireEvent.changeText(screen.getByTestId("exam-cattle"), "22222222-2222-4222-8222-222222222222");
  fireEvent.changeText(screen.getByTestId("exam-assessment"), "Clinical examination performed");
  fireEvent.press(screen.getByTestId("exam-submit"));
  await waitFor(() => expect(service.createExam).toHaveBeenCalledWith(FARM, expect.objectContaining({ assessment: "INCONCLUSIVE", clinical_assessment: "Clinical examination performed" })));
});

test("offspring form integrates with canonical registration API", async () => {
  const service = api(); const screen = mount(<OffspringRegistrationScreen api={service} />);
  fireEvent.changeText(screen.getByTestId("offspring-calving"), "33333333-3333-4333-8333-333333333333");
  fireEvent.changeText(screen.getByTestId("offspring-tag"), "CALF-101");
  fireEvent.press(screen.getByTestId("offspring-submit"));
  await waitFor(() => expect(service.registerOffspring).toHaveBeenCalledWith(FARM, "33333333-3333-4333-8333-333333333333", expect.objectContaining({ tag_number: "CALF-101", category: "CALF" })));
});
