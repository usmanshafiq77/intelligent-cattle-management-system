import { act, fireEvent, render, waitFor } from "@testing-library/react-native";
import { Pressable, Text } from "react-native";

import { ApiError } from "../src/api/errors";
import { AuthProvider, useAuth } from "../src/features/auth/context/AuthProvider";
import { FarmProvider, useFarm } from "../src/features/farms/context/FarmProvider";

const USER = Object.freeze({
  id: "user-1",
  full_name: "ICMS User",
  email: "user@example.com",
  is_system_admin: false,
  status: "ACTIVE",
  is_email_verified: true,
  created_at: "2026-10-17T00:00:00Z",
});

const FARM_A = Object.freeze({ id: "farm-a", name: "North Farm", owner_id: "user-1", location: null, description: null, created_at: "2026-10-01T00:00:00Z" });
const FARM_B = Object.freeze({ id: "farm-b", name: "South Farm", owner_id: "user-2", location: "Lahore", description: null, created_at: "2026-10-02T00:00:00Z" });

function permissionResponse(farmId, role = "WORKER", permissions = ["farm.view"]) {
  return { farm_id: farmId, membership_id: `member-${farmId}`, predefined_role: role, custom_role_ids: [], permissions };
}

function deferred() {
  let resolve;
  let reject;
  const promise = new Promise((resolvePromise, rejectPromise) => { resolve = resolvePromise; reject = rejectPromise; });
  return { promise, resolve, reject };
}

function createTransport() {
  let token = "token";
  let expirationListener;
  return {
    configureAuthTokenProvider: jest.fn(),
    getAccessToken: jest.fn(async () => token),
    setAccessToken: jest.fn(async (next) => { token = next; }),
    removeAccessToken: jest.fn(async () => { token = null; }),
    subscribeToSessionExpiration: jest.fn((listener) => { expirationListener = listener; return jest.fn(); }),
    expire: () => expirationListener?.({ reason: "unauthorized", token }),
  };
}

let currentFarm;
let currentAuth;
function Probe() {
  currentFarm = useFarm();
  currentAuth = useAuth();
  return (
    <>
      <Text testID="farm-status">{currentFarm.status}</Text>
      <Text testID="active-farm">{currentFarm.activeFarm?.id || "none"}</Text>
      <Text testID="role">{currentFarm.membership?.role || "none"}</Text>
      <Text testID="permissions">{currentFarm.permissions.join(",")}</Text>
      <Pressable testID="select-a" onPress={() => { void currentFarm.selectFarm("farm-a"); }}><Text>A</Text></Pressable>
      <Pressable testID="select-b" onPress={() => { void currentFarm.selectFarm("farm-b"); }}><Text>B</Text></Pressable>
      <Pressable testID="select-invalid" onPress={() => { void currentFarm.selectFarm("not-accessible"); }}><Text>Invalid</Text></Pressable>
      <Pressable testID="refresh" onPress={() => { void currentFarm.refreshFarms(); }}><Text>Refresh</Text></Pressable>
      <Pressable testID="logout" onPress={() => { void currentAuth.logout(); }}><Text>Logout</Text></Pressable>
    </>
  );
}

function mount({ farmApi, authApi = { getCurrentUser: jest.fn().mockResolvedValue(USER) }, transport = createTransport() }) {
  const tokenProvider = { getToken: jest.fn(), setToken: jest.fn(), removeToken: jest.fn() };
  const screen = render(
    <AuthProvider api={authApi} transport={transport} tokenProvider={tokenProvider}>
      <FarmProvider api={farmApi}><Probe /></FarmProvider>
    </AuthProvider>,
  );
  return { screen, transport };
}

afterEach(() => {
  currentFarm = null;
  currentAuth = null;
});

test("one verified farm is selected and hydrated automatically", async () => {
  const farmApi = { listFarms: jest.fn().mockResolvedValue([FARM_A]), getEffectivePermissions: jest.fn().mockResolvedValue(permissionResponse("farm-a", "FARM_OWNER", ["farm.view", "staff.view"])) };
  const { screen } = mount({ farmApi });
  await waitFor(() => expect(screen.getByTestId("farm-status").props.children).toBe("ready"));
  expect(screen.getByTestId("active-farm").props.children).toBe("farm-a");
  expect(screen.getByTestId("role").props.children).toBe("FARM_OWNER");
  expect(currentFarm.can("staff.view")).toBe(true);
  expect(currentFarm.can("unknown.permission")).toBe(false);
});

test("zero farms produces an honest no-farm state without a permission request", async () => {
  const farmApi = { listFarms: jest.fn().mockResolvedValue([]), getEffectivePermissions: jest.fn() };
  mount({ farmApi });
  await waitFor(() => expect(currentFarm.status).toBe("no-farms"));
  expect(currentFarm.activeFarm).toBeNull();
  expect(farmApi.getEffectivePermissions).not.toHaveBeenCalled();
});

test("inactive memberships omitted by the backend grant no farm context", async () => {
  const farmApi = { listFarms: jest.fn().mockResolvedValue([]), getEffectivePermissions: jest.fn() };
  mount({ farmApi });
  await waitFor(() => expect(currentFarm.status).toBe("no-farms"));
  expect(currentFarm.membership).toBeNull();
  expect(currentFarm.can("farm.view")).toBe(false);
});

test("multiple farms require explicit selection and verify the selected membership", async () => {
  const farmApi = { listFarms: jest.fn().mockResolvedValue([FARM_A, FARM_B]), getEffectivePermissions: jest.fn((id) => Promise.resolve(permissionResponse(id, id === "farm-b" ? "VETERINARIAN" : "WORKER", ["farm.view", "health.view"]))) };
  const { screen } = mount({ farmApi });
  await waitFor(() => expect(currentFarm.status).toBe("selection-required"));
  expect(currentFarm.activeFarm).toBeNull();
  fireEvent.press(screen.getByTestId("select-b"));
  await waitFor(() => expect(currentFarm.status).toBe("ready"));
  expect(currentFarm.activeFarm.id).toBe("farm-b");
  expect(currentFarm.membership.role).toBe("VETERINARIAN");
});

test("an arbitrary farm id outside the verified list is rejected locally", async () => {
  const farmApi = { listFarms: jest.fn().mockResolvedValue([FARM_A, FARM_B]), getEffectivePermissions: jest.fn() };
  const { screen } = mount({ farmApi });
  await waitFor(() => expect(currentFarm.status).toBe("selection-required"));
  fireEvent.press(screen.getByTestId("select-invalid"));
  expect(currentFarm.issue.kind).toBe("invalid-selection");
  expect(farmApi.getEffectivePermissions).not.toHaveBeenCalled();
});

test.each([
  [403, "access"],
  [404, "access"],
  [429, "rate-limit"],
  [503, "unavailable"],
])("permission verification failure %s clears farm-scoped state", async (status, kind) => {
  const farmApi = { listFarms: jest.fn().mockResolvedValue([FARM_A]), getEffectivePermissions: jest.fn().mockRejectedValue(new ApiError("unsafe server detail", { status })) };
  mount({ farmApi });
  await waitFor(() => expect(currentFarm.status).toBe("permission-unavailable"));
  expect(currentFarm.issue.kind).toBe(kind);
  expect(currentFarm.activeFarm).toBeNull();
  expect(currentFarm.permissions).toEqual([]);
});

test("unknown backend role fails closed", async () => {
  const farmApi = { listFarms: jest.fn().mockResolvedValue([FARM_A]), getEffectivePermissions: jest.fn().mockResolvedValue(permissionResponse("farm-a", "UNTRUSTED_ROLE", ["farm.view"])) };
  mount({ farmApi });
  await waitFor(() => expect(currentFarm.status).toBe("permission-unavailable"));
  expect(currentFarm.activeFarm).toBeNull();
  expect(currentFarm.can("farm.view")).toBe(false);
});

test("rapid switching cannot restore stale permissions from the previous farm", async () => {
  const requestA = deferred();
  const requestB = deferred();
  const farmApi = {
    listFarms: jest.fn().mockResolvedValue([FARM_A, FARM_B]),
    getEffectivePermissions: jest.fn((id) => id === "farm-a" ? requestA.promise : requestB.promise),
  };
  const { screen } = mount({ farmApi });
  await waitFor(() => expect(currentFarm.status).toBe("selection-required"));
  fireEvent.press(screen.getByTestId("select-a"));
  await waitFor(() => expect(farmApi.getEffectivePermissions).toHaveBeenCalledWith("farm-a", expect.any(Object)));
  fireEvent.press(screen.getByTestId("select-b"));
  expect(currentFarm.activeFarm).toBeNull();
  expect(currentFarm.permissions).toEqual([]);
  requestB.resolve(permissionResponse("farm-b", "VETERINARIAN", ["farm.view", "health.view"]));
  await waitFor(() => expect(currentFarm.activeFarm?.id).toBe("farm-b"));
  requestA.resolve(permissionResponse("farm-a", "FARM_OWNER", ["farm.manage"]));
  await act(async () => { await requestA.promise; });
  expect(currentFarm.activeFarm.id).toBe("farm-b");
  expect(currentFarm.permissions).toEqual(["farm.view", "health.view"]);
});

test("logout during farm loading prevents late farm data from appearing", async () => {
  const farms = deferred();
  const farmApi = { listFarms: jest.fn(() => farms.promise), getEffectivePermissions: jest.fn() };
  const { screen } = mount({ farmApi });
  await waitFor(() => expect(currentFarm.status).toBe("loading"));
  fireEvent.press(screen.getByTestId("logout"));
  await waitFor(() => expect(currentAuth.status).toBe("unauthenticated"));
  farms.resolve([FARM_A]);
  await act(async () => { await farms.promise; });
  expect(currentFarm.status).toBe("idle");
  expect(currentFarm.activeFarm).toBeNull();
});

test("refresh removes a revoked membership and never preserves its permissions", async () => {
  const farmApi = {
    listFarms: jest.fn().mockResolvedValueOnce([FARM_A]).mockResolvedValueOnce([]),
    getEffectivePermissions: jest.fn().mockResolvedValue(permissionResponse("farm-a", "WORKER", ["farm.view", "cattle.view"])),
  };
  const { screen } = mount({ farmApi });
  await waitFor(() => expect(currentFarm.status).toBe("ready"));
  fireEvent.press(screen.getByTestId("refresh"));
  await waitFor(() => expect(currentFarm.status).toBe("no-farms"));
  expect(currentFarm.permissions).toEqual([]);
  expect(currentFarm.activeFarm).toBeNull();
});

test("a backend 401 exposes no farm data while the transport owns session invalidation", async () => {
  const farmApi = { listFarms: jest.fn().mockRejectedValue(new ApiError("Expired", { status: 401 })), getEffectivePermissions: jest.fn() };
  mount({ farmApi });
  await waitFor(() => expect(currentFarm.status).toBe("unavailable"));
  expect(currentFarm.farms).toEqual([]);
  expect(currentFarm.permissions).toEqual([]);
});

test("FarmProvider creates, re-lists, and activates only the backend-confirmed owner farm", async () => {
  const created = { ...FARM_A, id: "farm-created", name: "Created Farm" };
  const farmApi = {
    listFarms: jest.fn().mockResolvedValueOnce([]).mockResolvedValueOnce([created]),
    createFarm: jest.fn().mockResolvedValue(created),
    getEffectivePermissions: jest.fn().mockResolvedValue(permissionResponse("farm-created", "FARM_OWNER", ["farm.view", "farm.manage"])),
  };
  mount({ farmApi });
  await waitFor(() => expect(currentFarm.status).toBe("no-farms"));
  let result;
  await act(async () => { result = await currentFarm.createFarm({ name: "Created Farm", location: null, description: null }); });
  expect(result).toMatchObject({ created: true, selected: true, farm: created });
  expect(farmApi.createFarm).toHaveBeenCalledWith({ name: "Created Farm", location: null, description: null }, expect.any(Object));
  expect(currentFarm.activeFarm).toEqual(created);
  expect(currentFarm.membership.role).toBe("FARM_OWNER");
  expect(currentFarm.can("farm.manage")).toBe(true);
});
