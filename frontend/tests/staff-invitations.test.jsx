import { act, fireEvent, render, waitFor } from "@testing-library/react-native";

import { ApiError } from "../src/api/errors";
import { invitationsApi } from "../src/api/invitations";
import { staffApi } from "../src/api/staff";
import { AcceptInvitationScreen } from "../src/features/staff/screens/AcceptInvitationScreen";
import { InviteStaffScreen } from "../src/features/staff/screens/InviteStaffScreen";
import { StaffScreen } from "../src/features/staff/screens/StaffScreen";
import { ThemeProvider } from "../src/theme/ThemeProvider";

let mockAuth;
let mockFarm;

jest.mock("../src/features/auth/context/AuthProvider", () => ({
  useOptionalAuth: () => mockAuth,
}));
jest.mock("../src/features/farms/context/FarmProvider", () => ({
  useFarm: () => mockFarm,
}));
jest.mock("../src/api/staff", () => ({
  staffApi: { list: jest.fn() },
}));
jest.mock("../src/api/invitations", () => ({
  invitationsApi: { list: jest.fn() },
}));

const farmA = { id: "farm-a", name: "North Farm", owner_id: "owner-user" };
const farmB = { id: "farm-b", name: "South Farm", owner_id: "owner-user" };
const staff = {
  membership_id: "member-a",
  user_id: "user-a",
  name: "Worker One",
  email: "worker@example.com",
  role: "WORKER",
  status: "ACTIVE",
  joined_at: "2026-10-17T00:00:00Z",
  custom_role_ids: [],
};
const inactiveStaff = { ...staff, name: "Inactive Worker", status: "INACTIVE" };
const ownerStaff = {
  ...staff,
  membership_id: "owner-membership",
  user_id: "owner-user",
  name: "Farm Owner",
  email: "owner@example.com",
  role: "FARM_OWNER",
};
const invite = {
  id: "invite-a",
  farm_id: "farm-a",
  email: "invitee@example.com",
  role: "VETERINARIAN",
  status: "PENDING",
  expires_at: "2026-10-24T00:00:00Z",
  created_at: "2026-10-17T00:00:00Z",
};

function deferred() {
  let resolve;
  let reject;
  const promise = new Promise((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, resolve, reject };
}

function makeApi({ members = [staff], invitations = [invite], mutation = {} } = {}) {
  return {
    staff: {
      list: jest.fn().mockResolvedValue(members),
      updateRole: jest.fn().mockResolvedValue({ ...staff, role: "FARM_MANAGER" }),
      updateStatus: jest.fn().mockResolvedValue({ ...staff, status: "INACTIVE" }),
      ...mutation.staff,
    },
    invitations: {
      list: jest.fn().mockResolvedValue(invitations),
      revoke: jest.fn().mockResolvedValue({ ...invite, status: "REVOKED" }),
      reissue: jest.fn().mockResolvedValue({ ...invite, id: "invite-reissued" }),
      ...mutation.invitations,
    },
  };
}

const themedNode = (node) => <ThemeProvider persistPreference={false}>{node}</ThemeProvider>;
const themed = (node) => render(themedNode(node));

async function openAndConfirm(screen, label) {
  await waitFor(() => expect(screen.getByText(label)).toBeTruthy());
  fireEvent.press(screen.getByText(label));
  await act(async () => {
    fireEvent.press(screen.getByText("Confirm"));
    await Promise.resolve();
  });
}

function nearestAccessibilityRole(node) {
  let current = node;
  while (current) {
    if (current.props?.accessibilityRole) return current.props.accessibilityRole;
    current = current.parent;
  }
  return null;
}

beforeEach(() => {
  staffApi.list.mockReset().mockResolvedValue([staff]);
  invitationsApi.list.mockReset().mockResolvedValue([invite]);
  mockAuth = { status: "authenticated", user: { id: "owner-user" } };
  mockFarm = {
    activeFarm: farmA,
    membership: { role: "FARM_OWNER", status: "ACTIVE" },
    permissions: ["staff.view"],
    status: "ready",
    refreshFarms: jest.fn().mockResolvedValue({ selected: true }),
    can: jest.fn((permission) => permission === "staff.view"),
  };
});

describe("staff and invitation baseline behavior", () => {
  test("default services fetch once across loading, success, and parent rerenders", async () => {
    const screen = themed(<StaffScreen />);

    await waitFor(() => expect(screen.getByText("Worker One")).toBeTruthy());
    expect(screen.getByText("invitee@example.com")).toBeTruthy();
    expect(screen.getByText("PENDING", { exact: false })).toBeTruthy();
    expect(staffApi.list).toHaveBeenCalledTimes(1);
    expect(invitationsApi.list).toHaveBeenCalledTimes(1);

    screen.rerender(themedNode(<StaffScreen />));
    await act(async () => { await Promise.resolve(); });

    expect(staffApi.list).toHaveBeenCalledTimes(1);
    expect(invitationsApi.list).toHaveBeenCalledTimes(1);
  });

  test("coalesces duplicate retry presses while the same farm request is in flight", async () => {
    const pending = deferred();
    const api = makeApi();
    api.staff.list
      .mockRejectedValueOnce(new ApiError("temporary", { status: 503 }))
      .mockImplementationOnce(() => pending.promise);
    const screen = themed(<StaffScreen api={api} />);

    await waitFor(() => expect(screen.getByText("Retry")).toBeTruthy());
    const retry = screen.getByText("Retry");
    fireEvent.press(retry);
    fireEvent.press(retry);

    expect(api.staff.list).toHaveBeenCalledTimes(2);
    expect(api.invitations.list).toHaveBeenCalledTimes(2);
    screen.unmount();
  });

  test("renders verified members and owner-only invitations", async () => {
    const api = makeApi();
    const onInvite = jest.fn();
    const screen = themed(<StaffScreen onInvite={onInvite} api={api} />);
    await waitFor(() => expect(screen.getByText("Worker One")).toBeTruthy());
    expect(screen.getByText("invitee@example.com")).toBeTruthy();
    fireEvent.press(screen.getByText("Invite staff"));
    expect(onInvite).toHaveBeenCalledTimes(1);
  });

  test("handles list failure without exposing server detail", async () => {
    const api = makeApi();
    api.staff.list.mockRejectedValue(new ApiError("secret backend detail", { status: 403 }));
    const screen = themed(<StaffScreen api={api} />);
    await waitFor(() => expect(screen.getByText("Staff unavailable")).toBeTruthy());
    expect(screen.queryByText("secret backend detail")).toBeNull();
  });

  test("denies unknown permissions without fetching staff", async () => {
    mockFarm.can = jest.fn(() => false);
    const api = makeApi();
    const screen = themed(<StaffScreen api={api} />);
    expect(screen.getByText("Access denied")).toBeTruthy();
    await act(async () => {});
    expect(api.staff.list).not.toHaveBeenCalled();
  });

  test("handles a temporarily absent active farm without dereferencing it", () => {
    mockFarm = { ...mockFarm, activeFarm: null, status: "selection-required" };
    const screen = themed(<StaffScreen api={makeApi()} />);
    expect(screen.getByText("Choose a farm")).toBeTruthy();
  });

  test("invite form sends only an owner-authorized supported payload", async () => {
    const api = { create: jest.fn().mockResolvedValue(invite) };
    const screen = themed(<InviteStaffScreen onBack={jest.fn()} api={api} />);
    fireEvent.changeText(screen.getByTestId("invite-email"), " Invitee@Example.com ");
    fireEvent.press(screen.getByText("VETERINARIAN"));
    fireEvent.press(screen.getByTestId("invite-submit"));
    await waitFor(() => expect(api.create).toHaveBeenCalledWith("farm-a", {
      email: "invitee@example.com",
      role: "VETERINARIAN",
    }));
    expect(screen.getByTestId("invite-email").props.value).toBe("");
    expect(screen.getByText(/Invitation created/)).toBeTruthy();
  });

  test("invite form distinguishes creation from failed email delivery", async () => {
    const api = {
      create: jest.fn().mockResolvedValue({
        ...invite,
        delivery_status: "FAILED",
      }),
    };
    const screen = themed(<InviteStaffScreen api={api} />);
    fireEvent.changeText(screen.getByTestId("invite-email"), "invitee@example.com");
    fireEvent.press(screen.getByTestId("invite-submit"));

    await waitFor(() => expect(screen.getByText(/email delivery failed/i)).toBeTruthy());
    expect(screen.queryByText(/handed to the configured email service/i)).toBeNull();
  });

  test("invite validation and backend failures are announced as errors", async () => {
    const api = {
      create: jest.fn().mockRejectedValue(
        new ApiError("sensitive backend detail", { status: 409 }),
      ),
    };
    const screen = themed(<InviteStaffScreen api={api} />);

    fireEvent.press(screen.getByTestId("invite-submit"));
    const validationMessage = screen.getByText("Enter a valid invitee email address.");
    expect(nearestAccessibilityRole(validationMessage)).toBe("alert");

    fireEvent.changeText(screen.getByTestId("invite-email"), "worker@example.com");
    fireEvent.press(screen.getByTestId("invite-submit"));
    await waitFor(() => expect(api.create).toHaveBeenCalledTimes(1));
    const backendMessage = screen.getByText(
      "This action conflicts with the current farm state. Refresh and try again.",
    );
    expect(nearestAccessibilityRole(backendMessage)).toBe("alert");
    expect(screen.queryByText("sensitive backend detail")).toBeNull();
  });

  test.each([
    ["WORKER", "owner-user"],
    ["FARM_OWNER", "different-user"],
  ])("direct invite route is denied for membership %s and user %s", (membershipRole, userId) => {
    mockFarm = { ...mockFarm, membership: { role: membershipRole, status: "ACTIVE" } };
    mockAuth = { status: "authenticated", user: { id: userId } };
    const api = { create: jest.fn() };
    const screen = themed(<InviteStaffScreen api={api} />);
    expect(screen.getByText("Access denied")).toBeTruthy();
    expect(screen.queryByTestId("invite-submit")).toBeNull();
    expect(api.create).not.toHaveBeenCalled();
  });

  test("acceptance prefills a secure invitation deep-link token", () => {
    const secret = "a".repeat(32);
    const screen = themed(<AcceptInvitationScreen initialToken={secret} api={{ accept: jest.fn() }} />);
    expect(screen.getByTestId("accept-invitation-token").props.value).toBe(secret);
  });

  test("acceptance refreshes farm context, clears the token, and never logs it", async () => {
    const accepted = {
      farm_id: "farm-a",
      farm_name: "North Farm",
      membership_id: "member-new",
      role: "WORKER",
      membership_status: "ACTIVE",
      accepted_at: "2026-10-17T00:00:00Z",
    };
    const secret = "a".repeat(32);
    const log = jest.spyOn(console, "log").mockImplementation(() => {});
    const onAccepted = jest.fn();
    const screen = themed(<AcceptInvitationScreen onAccepted={onAccepted} api={{ accept: jest.fn().mockResolvedValue(accepted) }} />);
    fireEvent.changeText(screen.getByTestId("accept-invitation-token"), secret);
    fireEvent.press(screen.getByTestId("accept-invitation-submit"));
    await waitFor(() => expect(mockFarm.refreshFarms).toHaveBeenCalledTimes(1));
    expect(onAccepted).toHaveBeenCalledWith(accepted);
    expect(screen.getByTestId("accept-invitation-token").props.value).toBe("");
    expect(log.mock.calls.flat().join(" ")).not.toContain(secret);
    log.mockRestore();
  });

  test.each([400, 409, 422, 429, 503])("acceptance status %s is safely normalized", async (status) => {
    const screen = themed(<AcceptInvitationScreen api={{ accept: jest.fn().mockRejectedValue(new ApiError("sensitive", { status })) }} />);
    fireEvent.changeText(screen.getByTestId("accept-invitation-token"), "a".repeat(32));
    fireEvent.press(screen.getByTestId("accept-invitation-submit"));
    await waitFor(() => expect(screen.queryByText("sensitive")).toBeNull());
  });
});

describe("successful owner mutations", () => {
  test("reissues an eligible invitation through the reviewed method and refreshes authoritative data", async () => {
    const secret = "server-only-reissue-token";
    const log = jest.spyOn(console, "log").mockImplementation(() => {});
    const api = makeApi({ mutation: { invitations: { reissue: jest.fn().mockResolvedValue({ ...invite, id: "invite-reissued", invitation_token: secret }) } } });
    const screen = themed(<StaffScreen api={api} />);
    await openAndConfirm(screen, "Reissue");
    await waitFor(() => expect(api.invitations.reissue).toHaveBeenCalledWith(
      "farm-a",
      "invite-a",
      expect.objectContaining({ signal: expect.any(Object) }),
    ));
    await waitFor(() => expect(api.invitations.list).toHaveBeenCalledTimes(2));
    expect(mockFarm.refreshFarms).toHaveBeenCalledTimes(1);
    expect(screen.queryByText(secret)).toBeNull();
    expect(log.mock.calls.flat().join(" ")).not.toContain(secret);
    log.mockRestore();
  });

  test("revokes a pending invitation only after confirmation and refreshes", async () => {
    const api = makeApi();
    const screen = themed(<StaffScreen api={api} />);
    await openAndConfirm(screen, "Revoke");
    await waitFor(() => expect(api.invitations.revoke).toHaveBeenCalledWith(
      "farm-a",
      "invite-a",
      expect.objectContaining({ signal: expect.any(Object) }),
    ));
    await waitFor(() => expect(api.invitations.list).toHaveBeenCalledTimes(2));
  });

  test.each([
    ["Set Manager", "FARM_MANAGER"],
    ["Set Worker", "WORKER"],
    ["Set Veterinarian", "VETERINARIAN"],
  ])("updates predefined role with supported value %s", async (label, role) => {
    const currentRole = role === "WORKER" ? "VETERINARIAN" : "WORKER";
    const member = { ...staff, role: currentRole };
    const api = makeApi({
      members: [member],
      mutation: { staff: { updateRole: jest.fn().mockResolvedValue({ ...member, role }) } },
    });
    const screen = themed(<StaffScreen api={api} />);
    await openAndConfirm(screen, label);
    await waitFor(() => expect(api.staff.updateRole).toHaveBeenCalledWith(
      "farm-a",
      "member-a",
      role,
      expect.objectContaining({ signal: expect.any(Object) }),
    ));
  });

  test.each([
    ["Activate", inactiveStaff, "ACTIVE"],
    ["Deactivate", staff, "INACTIVE"],
  ])("%s uses the reviewed membership status and refreshes", async (label, member, status) => {
    const api = makeApi({
      members: [member],
      mutation: { staff: { updateStatus: jest.fn().mockResolvedValue({ ...member, status }) } },
    });
    const screen = themed(<StaffScreen api={api} />);
    await openAndConfirm(screen, label);
    await waitFor(() => expect(api.staff.updateStatus).toHaveBeenCalledWith(
      "farm-a",
      "member-a",
      status,
      expect.objectContaining({ signal: expect.any(Object) }),
    ));
    expect(mockFarm.refreshFarms).toHaveBeenCalledTimes(1);
  });

  test("cancellation makes no request", async () => {
    const api = makeApi();
    const screen = themed(<StaffScreen api={api} />);
    await waitFor(() => expect(screen.getByText("Revoke")).toBeTruthy());
    fireEvent.press(screen.getByText("Revoke"));
    fireEvent.press(screen.getByText("Cancel"));
    expect(api.invitations.revoke).not.toHaveBeenCalled();
  });

  test("owner and authoritative owner-id rows never expose member mutation controls", async () => {
    const disguisedOwner = { ...staff, membership_id: "owner-by-id", user_id: "owner-user", role: "WORKER" };
    const api = makeApi({ members: [ownerStaff, disguisedOwner] });
    const screen = themed(<StaffScreen api={api} />);
    await waitFor(() => expect(screen.getByText("Farm Owner")).toBeTruthy());
    expect(screen.queryByText("Deactivate")).toBeNull();
    expect(screen.queryByText("Activate")).toBeNull();
    expect(screen.queryByText("Set Manager")).toBeNull();
  });

  test("accepted and rejected invitations cannot be reissued or revoked", async () => {
    const api = makeApi({ invitations: [
      { ...invite, id: "accepted", status: "ACCEPTED" },
      { ...invite, id: "rejected", status: "REJECTED" },
    ] });
    const screen = themed(<StaffScreen api={api} />);
    await waitFor(() => expect(screen.getByText("ACCEPTED", { exact: false })).toBeTruthy());
    expect(screen.queryByText("Reissue")).toBeNull();
    expect(screen.queryByText("Revoke")).toBeNull();
  });

  test("an expired invitation cannot be revoked but remains eligible for backend-validated reissue", async () => {
    const api = makeApi({ invitations: [{ ...invite, status: "EXPIRED" }] });
    const screen = themed(<StaffScreen api={api} />);
    await waitFor(() => expect(screen.getByText("Reissue")).toBeTruthy());
    expect(screen.queryByText("Revoke")).toBeNull();
  });

  test("FARM_OWNER and SYSTEM_ADMIN can never be selected from the role UI", async () => {
    const screen = themed(<StaffScreen api={makeApi()} />);
    await waitFor(() => expect(screen.getByText("Set Manager")).toBeTruthy());
    expect(screen.queryByText("Set Owner")).toBeNull();
    expect(screen.queryByText("Set System Admin")).toBeNull();
  });
});

const mutationCases = [
  { name: "revoke", label: "Revoke", branch: "invitations", method: "revoke", invitation: true, members: [staff] },
  { name: "reissue", label: "Reissue", branch: "invitations", method: "reissue", invitation: true, members: [staff] },
  { name: "role update", label: "Set Manager", branch: "staff", method: "updateRole", invitation: false, members: [staff] },
  { name: "activate", label: "Activate", branch: "staff", method: "updateStatus", invitation: false, members: [inactiveStaff] },
  { name: "deactivate", label: "Deactivate", branch: "staff", method: "updateStatus", invitation: false, members: [staff] },
];

const errorCases = [
  { name: "401", options: { status: 401 }, expected: "Your session has expired" },
  { name: "403", options: { status: 403 }, expected: "You do not have permission" },
  { name: "404", options: { status: 404 }, expected: null },
  { name: "409", options: { status: 409 }, expected: "conflicts with the current farm state" },
  { name: "422", options: { status: 422 }, expected: "could not be completed" },
  { name: "429", options: { status: 429 }, expected: "Too many requests" },
  { name: "503", options: { status: 503 }, expected: "server could not complete" },
  { name: "network", options: { category: "network", code: "NETWORK_ERROR" }, expected: "could not confirm" },
  { name: "timeout", options: { category: "network", code: "TIMEOUT" }, expected: "could not confirm" },
];

describe.each(mutationCases)("$name mutation error matrix", (mutationCase) => {
  test.each(errorCases)("normalizes $name without false success", async (errorCase) => {
    const failure = new ApiError("sensitive server message", errorCase.options);
    const mutation = { [mutationCase.branch]: { [mutationCase.method]: jest.fn().mockRejectedValue(failure) } };
    const api = makeApi({ members: mutationCase.members, mutation });
    const screen = themed(<StaffScreen api={api} />);
    await openAndConfirm(screen, mutationCase.label);
    const expected = errorCase.name === "404"
      ? (mutationCase.invitation ? "invitation is unavailable" : "staff member is unavailable")
      : errorCase.expected;
    await waitFor(() => expect(screen.getByText(expected, { exact: false })).toBeTruthy());
    expect(screen.queryByText("sensitive server message")).toBeNull();
    expect(api[mutationCase.branch][mutationCase.method]).toHaveBeenCalledTimes(1);
    expect(api.staff.list).toHaveBeenCalledTimes(1);
    expect(mockFarm.refreshFarms).not.toHaveBeenCalled();
  });
});

describe("deterministic mutation and loading concurrency", () => {
  test.each(mutationCases)("farm switch invalidates a pending $name", async (mutationCase) => {
    const pending = deferred();
    const mutation = { [mutationCase.branch]: { [mutationCase.method]: jest.fn(() => pending.promise) } };
    const api = makeApi({ members: mutationCase.members, mutation });
    const screen = themed(<StaffScreen api={api} />);
    await openAndConfirm(screen, mutationCase.label);
    expect(api[mutationCase.branch][mutationCase.method]).toHaveBeenCalledTimes(1);

    mockFarm = { ...mockFarm, activeFarm: farmB };
    api.staff.list.mockResolvedValue([{ ...staff, membership_id: "member-b", name: "Farm B Worker" }]);
    api.invitations.list.mockResolvedValue([]);
    screen.rerender(themedNode(<StaffScreen api={api} />));
    await waitFor(() => expect(screen.getByText("Farm B Worker")).toBeTruthy());

    await act(async () => {
      if (mutationCase.branch === "invitations") pending.resolve({ ...invite, status: mutationCase.method === "revoke" ? "REVOKED" : "PENDING" });
      else pending.resolve({ ...mutationCase.members[0] });
      await pending.promise;
    });
    expect(screen.queryByText("Action unavailable")).toBeNull();
    expect(mockFarm.refreshFarms).not.toHaveBeenCalled();
  });

  test.each(mutationCases)("logout invalidates a pending $name", async (mutationCase) => {
    const pending = deferred();
    const mutation = { [mutationCase.branch]: { [mutationCase.method]: jest.fn(() => pending.promise) } };
    const api = makeApi({ members: mutationCase.members, mutation });
    const screen = themed(<StaffScreen api={api} />);
    await openAndConfirm(screen, mutationCase.label);

    mockAuth = { status: "unauthenticated", user: null };
    screen.rerender(themedNode(<StaffScreen api={api} />));
    await act(async () => {
      pending.reject(new ApiError("stale secret", { status: 503 }));
      try { await pending.promise; } catch {}
    });
    expect(screen.queryByText("stale secret")).toBeNull();
    expect(screen.queryByText("Action unavailable")).toBeNull();
    expect(mockFarm.refreshFarms).not.toHaveBeenCalled();
  });

  test.each(mutationCases)("duplicate confirmation submits one $name request", async (mutationCase) => {
    const pending = deferred();
    const mutation = { [mutationCase.branch]: { [mutationCase.method]: jest.fn(() => pending.promise) } };
    const api = makeApi({ members: mutationCase.members, mutation });
    const screen = themed(<StaffScreen api={api} />);
    await waitFor(() => expect(screen.getByText(mutationCase.label)).toBeTruthy());
    fireEvent.press(screen.getByText(mutationCase.label));
    const confirm = screen.getByText("Confirm");
    fireEvent.press(confirm);
    fireEvent.press(confirm);
    expect(api[mutationCase.branch][mutationCase.method]).toHaveBeenCalledTimes(1);
    screen.unmount();
  });

  test("an older Farm A list cannot overwrite a newer Farm B list", async () => {
    const farmAList = deferred();
    const api = makeApi();
    api.staff.list.mockImplementation((farmId) => farmId === "farm-a"
      ? farmAList.promise
      : Promise.resolve([{ ...staff, membership_id: "member-b", name: "Farm B Worker" }]));
    api.invitations.list.mockImplementation((farmId) => Promise.resolve(farmId === "farm-a" ? [invite] : []));
    const screen = themed(<StaffScreen api={api} />);

    mockFarm = { ...mockFarm, activeFarm: farmB };
    screen.rerender(themedNode(<StaffScreen api={api} />));
    await waitFor(() => expect(screen.getByText("Farm B Worker")).toBeTruthy());
    await act(async () => {
      farmAList.resolve([{ ...staff, name: "Stale Farm A Worker" }]);
      await farmAList.promise;
    });
    expect(screen.queryByText("Stale Farm A Worker")).toBeNull();
    expect(screen.getByText("Farm B Worker")).toBeTruthy();
  });

  test("permission removal during a mutation prevents stale feedback and refresh", async () => {
    const pending = deferred();
    const api = makeApi({ mutation: { invitations: { reissue: jest.fn(() => pending.promise) } } });
    const screen = themed(<StaffScreen api={api} />);
    await openAndConfirm(screen, "Reissue");
    mockFarm = { ...mockFarm, can: jest.fn(() => false), permissions: [] };
    screen.rerender(themedNode(<StaffScreen api={api} />));
    expect(screen.getByText("Access denied")).toBeTruthy();
    await act(async () => {
      pending.resolve({ ...invite, id: "replacement" });
      await pending.promise;
    });
    expect(mockFarm.refreshFarms).not.toHaveBeenCalled();
  });

  test("unmount aborts a pending mutation without a state update", async () => {
    const pending = deferred();
    const api = makeApi({ mutation: { invitations: { reissue: jest.fn(() => pending.promise) } } });
    const screen = themed(<StaffScreen api={api} />);
    await openAndConfirm(screen, "Reissue");
    const signal = api.invitations.reissue.mock.calls[0][2].signal;
    screen.unmount();
    expect(signal.aborted).toBe(true);
    await act(async () => {
      pending.resolve({ ...invite, id: "replacement" });
      await pending.promise;
    });
    expect(mockFarm.refreshFarms).not.toHaveBeenCalled();
  });

  test("successful mutation followed by refresh failure remains recoverable", async () => {
    const api = makeApi();
    api.staff.list.mockResolvedValueOnce([staff]).mockRejectedValueOnce(new ApiError("refresh secret", { status: 503 }));
    const screen = themed(<StaffScreen api={api} />);
    await openAndConfirm(screen, "Reissue");
    await waitFor(() => expect(screen.getByText("Staff unavailable")).toBeTruthy());
    expect(screen.queryByText("refresh secret")).toBeNull();
    expect(screen.getByText("Retry")).toBeTruthy();
  });

  test("invalid mutation response never reports success and requires refresh", async () => {
    const api = makeApi({ mutation: { invitations: { reissue: jest.fn().mockResolvedValue({ id: "invalid" }) } } });
    const screen = themed(<StaffScreen api={api} />);
    await openAndConfirm(screen, "Reissue");
    await waitFor(() => expect(screen.getByText("Action unavailable")).toBeTruthy());
    expect(api.invitations.list).toHaveBeenCalledTimes(1);
    expect(mockFarm.refreshFarms).not.toHaveBeenCalled();
  });
});
