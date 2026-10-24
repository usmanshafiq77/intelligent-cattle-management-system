import { fireEvent, render, waitFor } from "@testing-library/react-native";

import {
  DiagnosisScreen,
  HealthAuditScreen,
  HealthDashboardScreen,
  HealthRecordDetailScreen,
  MedicationAdministrationScreen,
  ObservationScreen,
  VaccinationAdministrationScreen,
  VaccinationListScreen,
  VaccinationScheduleScreen,
} from "../src/features/health/screens/HealthScreens";
import { ThemeProvider } from "../src/theme/ThemeProvider";

let mockFarm;
jest.mock("../src/features/farms/context/FarmProvider", () => ({ useFarm: () => mockFarm }));

const FARM_ID = "11111111-1111-4111-8111-111111111111";
const CATTLE_ID = "22222222-2222-4222-8222-222222222222";
const ENCOUNTER_ID = "33333333-3333-4333-8333-333333333333";
const ANIMAL = { id: CATTLE_ID, tag_number: "ICMS-101", name: "Luna" };
const ENCOUNTER = { id: ENCOUNTER_ID, cattle_id: CATTLE_ID, encounter_type: "ILLNESS", symptoms: "Reduced appetite", status: "DRAFT", occurred_at: "2026-10-24T08:00:00Z" };

function api(overrides = {}) {
  return {
    listEncounters: jest.fn().mockResolvedValue([ENCOUNTER]),
    createEncounter: jest.fn().mockResolvedValue(ENCOUNTER),
    getEncounter: jest.fn().mockResolvedValue({ encounter: ENCOUNTER, diagnoses: [], treatments: [] }),
    listDiagnoses: jest.fn().mockResolvedValue([]),
    createDiagnosis: jest.fn().mockResolvedValue({ id: "diagnosis-id" }),
    listVaccinationSchedules: jest.fn().mockResolvedValue([]),
    createVaccinationSchedule: jest.fn().mockResolvedValue({ id: "schedule-id" }),
    listVaccinationAdministrations: jest.fn().mockResolvedValue([]),
    recordVaccinationAdministration: jest.fn().mockResolvedValue({ id: "administration-id" }),
    listTreatments: jest.fn().mockResolvedValue([]),
    listMedicationAdministrations: jest.fn().mockResolvedValue([]),
    recordMedicationAdministration: jest.fn().mockResolvedValue({ id: "medication-id" }),
    listVeterinaryVisits: jest.fn().mockResolvedValue([]),
    listReminders: jest.fn().mockResolvedValue([]),
    listCorrections: jest.fn().mockResolvedValue([]),
    createCorrection: jest.fn().mockResolvedValue({ id: "correction-id" }),
    ...overrides,
  };
}

const animalsApi = { list: jest.fn().mockResolvedValue([ANIMAL]) };
const renderScreen = (node) => render(<ThemeProvider persistPreference={false}>{node}</ThemeProvider>);

beforeEach(() => {
  jest.clearAllMocks();
  mockFarm = { status: "ready", activeFarm: { id: FARM_ID, name: "Green Valley" }, membership: { role: "FARM_OWNER" }, permissions: ["health.view", "health.create", "health.vaccination.manage"], can: jest.fn(() => true) };
});

test("dashboard loads only the active farm and exposes real health navigation", async () => {
  const service = api(); const onNavigate = jest.fn();
  const screen = renderScreen(<HealthDashboardScreen api={service} onNavigate={onNavigate} />);
  await waitFor(() => expect(screen.getByText("Open diagnoses")).toBeTruthy());
  expect(service.listEncounters).toHaveBeenCalledWith(FARM_ID, { limit: 100 });
  fireEvent.press(screen.getByText("Vaccinations"));
  expect(onNavigate).toHaveBeenCalledWith("/vaccinations");
});

test("switching farms reloads health data without retaining the previous farm scope", async () => {
  const service = api();
  const screen = renderScreen(<HealthDashboardScreen api={service} onNavigate={jest.fn()} />);
  await waitFor(() => expect(service.listEncounters).toHaveBeenCalledWith(FARM_ID, { limit: 100 }));
  const secondFarm = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";
  mockFarm = { ...mockFarm, activeFarm: { id: secondFarm, name: "Second Farm" } };
  screen.rerender(<ThemeProvider persistPreference={false}><HealthDashboardScreen api={service} onNavigate={jest.fn()} /></ThemeProvider>);
  await waitFor(() => expect(service.listEncounters).toHaveBeenCalledWith(secondFarm, { limit: 100 }));
});

test("worker observation sends factual fields without clinical impersonation", async () => {
  mockFarm.membership.role = "WORKER";
  const service = api(); const screen = renderScreen(<ObservationScreen api={service} animalsApi={animalsApi} />);
  await waitFor(() => expect(screen.getByText("Luna: 22222222-2222-4222-8222-222222222222")).toBeTruthy());
  fireEvent.changeText(screen.getByTestId("health-cattle"), CATTLE_ID);
  fireEvent.changeText(screen.getByTestId("observation-symptoms"), "Coughing after feeding");
  fireEvent.press(screen.getByTestId("observation-submit"));
  await waitFor(() => expect(service.createEncounter).toHaveBeenCalledWith(FARM_ID, expect.objectContaining({ cattle_id: CATTLE_ID, symptoms: "Coughing after feeding", clinical_observations: null, finalize: false })));
  expect(screen.queryByTestId("clinical-observations")).toBeNull();
});

test("only a veterinarian receives diagnosis entry controls", async () => {
  const ownerApi = api(); const owner = renderScreen(<DiagnosisScreen api={ownerApi} />);
  await waitFor(() => expect(owner.getByText("Diagnosis controls are available only to an authorized Veterinarian.")).toBeTruthy());
  expect(owner.queryByTestId("diagnosis-submit")).toBeNull();
  owner.unmount();

  mockFarm.membership.role = "VETERINARIAN";
  const vetApi = api(); const vet = renderScreen(<DiagnosisScreen api={vetApi} />);
  await waitFor(() => expect(vet.getByTestId("diagnosis-submit")).toBeTruthy());
  fireEvent.changeText(vet.getByTestId("diagnosis-encounter"), ENCOUNTER_ID);
  fireEvent.changeText(vet.getByTestId("diagnosis-condition"), "Respiratory infection");
  fireEvent.press(vet.getByTestId("diagnosis-submit"));
  await waitFor(() => expect(vetApi.createDiagnosis).toHaveBeenCalledWith(FARM_ID, expect.objectContaining({ encounter_id: ENCOUNTER_ID, condition_name: "Respiratory infection" })));
});

test("vaccination schedule validates dates and remains distinct from administration", async () => {
  const service = api(); const screen = renderScreen(<VaccinationScheduleScreen api={service} animalsApi={animalsApi} />);
  await waitFor(() => expect(screen.getByTestId("schedule-submit")).toBeTruthy());
  fireEvent.changeText(screen.getByTestId("health-cattle"), CATTLE_ID);
  fireEvent.changeText(screen.getByTestId("vaccine-name"), "Veterinarian configured vaccine");
  fireEvent.changeText(screen.getByLabelText("Scheduled date"), "2026-11-10");
  fireEvent.changeText(screen.getByLabelText("Due date"), "2026-11-01");
  fireEvent.press(screen.getByTestId("schedule-submit"));
  expect(service.createVaccinationSchedule).not.toHaveBeenCalled();
  expect(screen.getByText(/use a due date on or after/)).toBeTruthy();
});

test("vaccine administration is hidden from owner and submitted by veterinarian", async () => {
  const owner = renderScreen(<VaccinationAdministrationScreen api={api()} animalsApi={animalsApi} />);
  await waitFor(() => expect(owner.getByText(/not an authorized Veterinarian/)).toBeTruthy());
  expect(owner.queryByTestId("administration-submit")).toBeNull(); owner.unmount();
  mockFarm.membership.role = "VETERINARIAN";
  const service = api(); const vet = renderScreen(<VaccinationAdministrationScreen api={service} animalsApi={animalsApi} />);
  await waitFor(() => expect(vet.getByTestId("administration-submit")).toBeTruthy());
  fireEvent.changeText(vet.getByTestId("health-cattle"), CATTLE_ID);
  fireEvent.changeText(vet.getByTestId("admin-vaccine"), "Verified vaccine");
  fireEvent.changeText(vet.getByTestId("admin-dose"), "2");
  fireEvent.press(vet.getByTestId("administration-submit"));
  await waitFor(() => expect(service.recordVaccinationAdministration).toHaveBeenCalledWith(FARM_ID, expect.objectContaining({ vaccine_name: "Verified vaccine", dose: "2", dose_unit: "mL" })));
});

test("overdue view filters reminder data returned for the active farm", async () => {
  const service = api({ listReminders: jest.fn().mockResolvedValue([{ kind: "VACCINATION_OVERDUE", source_id: "one", cattle_id: CATTLE_ID, due_at: "2026-10-01T00:00:00Z", title: "Vaccination due: A", overdue: true }, { kind: "VACCINATION_UPCOMING", source_id: "two", cattle_id: CATTLE_ID, due_at: "2026-11-01T00:00:00Z", title: "Vaccination due: B", overdue: false }]) });
  const screen = renderScreen(<VaccinationListScreen mode="overdue" api={service} />);
  await waitFor(() => expect(screen.getByText("Vaccination due: A")).toBeTruthy());
  expect(screen.queryByText("Vaccination due: B")).toBeNull();
  expect(service.listReminders).toHaveBeenCalledWith(FARM_ID, { horizon_days: 365, limit: 200 });
});

test("veterinarian records medication against an existing treatment", async () => {
  mockFarm.membership.role = "VETERINARIAN";
  const service = api({ listTreatments: jest.fn().mockResolvedValue([{ id: "treatment-id", name: "Antibiotic course", status: "ACTIVE" }]) });
  const screen = renderScreen(<MedicationAdministrationScreen api={service} />);
  await waitFor(() => expect(screen.getByTestId("medication-submit")).toBeTruthy());
  fireEvent.changeText(screen.getByTestId("medication-treatment"), "treatment-id");
  fireEvent.changeText(screen.getByTestId("medication-name"), "Prescribed medicine");
  fireEvent.changeText(screen.getByTestId("medication-quantity"), "5");
  fireEvent.press(screen.getByTestId("medication-submit"));
  await waitFor(() => expect(service.recordMedicationAdministration).toHaveBeenCalledWith(FARM_ID, "treatment-id", expect.objectContaining({ medication_name: "Prescribed medicine", quantity: "5", unit: "mL" })));
});

test("record detail uses the farm-scoped encounter endpoint", async () => {
  const service = api(); const screen = renderScreen(<HealthRecordDetailScreen api={service} />);
  fireEvent.changeText(screen.getByTestId("detail-encounter"), ENCOUNTER_ID);
  fireEvent.press(screen.getByTestId("detail-load"));
  await waitFor(() => expect(service.getEncounter).toHaveBeenCalledWith(FARM_ID, ENCOUNTER_ID));
  expect(screen.getByText("Awaiting clinical examination.")).toBeTruthy();
});

test("authorized audit user appends a correction without editing the source", async () => {
  mockFarm.membership.role = "VETERINARIAN";
  const service = api(); const screen = renderScreen(<HealthAuditScreen api={service} />);
  await waitFor(() => expect(screen.getByTestId("correction-submit")).toBeTruthy());
  fireEvent.changeText(screen.getByLabelText("Cattle ID"), CATTLE_ID);
  fireEvent.changeText(screen.getByLabelText("Record ID"), ENCOUNTER_ID);
  fireEvent.changeText(screen.getByLabelText("Reason"), "Clarify original note");
  fireEvent.changeText(screen.getByLabelText("Correction note"), "Observation wording corrected after review");
  fireEvent.press(screen.getByTestId("correction-submit"));
  await waitFor(() => expect(service.createCorrection).toHaveBeenCalledWith(FARM_ID, expect.objectContaining({ cattle_id: CATTLE_ID, record_id: ENCOUNTER_ID, record_type: "ENCOUNTER" })));
});
