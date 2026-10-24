import { useCallback, useEffect, useRef, useState } from "react";
import { ScrollView, Text, View } from "react-native";

import { invitationsApi } from "../../../api/invitations";
import { staffApi } from "../../../api/staff";
import { AppButton } from "../../../components/ui/AppButton";
import { AppCard } from "../../../components/ui/AppCard";
import { ConfirmationDialog } from "../../../components/ui/ConfirmationDialog";
import { FeedbackState } from "../../../components/ui/FeedbackState";
import { StatusBadge } from "../../../components/ui/StatusBadge";
import { useAppTheme } from "../../../theme/ThemeProvider";
import { useOptionalAuth } from "../../auth/context/AuthProvider";
import { useFarm } from "../../farms/context/FarmProvider";
import { RequireFarm, RequirePermission } from "../../permissions/guards";
import { roleLabel } from "../../permissions/permissionCatalog";
import {
  requireInvitationList,
  requireInvitationResponse,
  requireStaffList,
  requireStaffResponse,
} from "../staffContracts";
import { staffErrorMessage } from "../staffErrors";

const initialState = Object.freeze({ loading: true, staff: [], invitations: [], error: null });
const defaultApi = Object.freeze({ staff: staffApi, invitations: invitationsApi });

function isAmbiguous(error) {
  return error?.code === "TIMEOUT" || error?.category === "network";
}

export function StaffScreen({ onInvite, api = defaultApi }) {
  const farm = useFarm();
  const auth = useOptionalAuth();
  const { theme, spacing, typography, layout } = useAppTheme();
  const farmId = farm.activeFarm?.id ?? null;
  const canView = farm.status === "ready" && farm.can("staff.view");
  const authoritativeOwner = farm.membership?.role === "FARM_OWNER"
    && (!auth || farm.activeFarm?.owner_id === auth.user?.id);

  const [state, setState] = useState(initialState);
  const [action, setAction] = useState(null);
  const [actionError, setActionError] = useState(null);
  const [pendingAction, setPendingAction] = useState(false);

  const mountedRef = useRef(false);
  const farmIdRef = useRef(farmId);
  const authStatusRef = useRef(auth?.status ?? "authenticated");
  const loadGenerationRef = useRef(0);
  const mutationGenerationRef = useRef(0);
  const loadControllerRef = useRef(null);
  const loadPendingRef = useRef(null);
  const mutationControllerRef = useRef(null);
  const mutationPendingRef = useRef(false);

  farmIdRef.current = farmId;
  authStatusRef.current = auth?.status ?? "authenticated";

  const isCurrent = useCallback((requestFarmId, generation, type) => (
    mountedRef.current
    && farmIdRef.current === requestFarmId
    && authStatusRef.current === "authenticated"
    && (type === "load" ? loadGenerationRef.current : mutationGenerationRef.current) === generation
  ), []);

  const load = useCallback(({ showLoading = true } = {}) => {
    const requestFarmId = farmIdRef.current;
    if (!requestFarmId || !canView || authStatusRef.current !== "authenticated") {
      return Promise.resolve({ skipped: true });
    }

    const pending = loadPendingRef.current;
    if (pending?.farmId === requestFarmId && !pending.controller.signal.aborted) {
      return pending.promise;
    }

    loadControllerRef.current?.abort();
    const controller = new AbortController();
    loadControllerRef.current = controller;
    const generation = ++loadGenerationRef.current;
    if (showLoading) setState(initialState);

    const promise = (async () => {
      try {
        const [staff, invitations] = await Promise.all([
          api.staff.list(requestFarmId, undefined, { signal: controller.signal }),
          authoritativeOwner
            ? api.invitations.list(requestFarmId, undefined, { signal: controller.signal })
            : Promise.resolve([]),
        ]);
        const next = {
          loading: false,
          staff: requireStaffList(staff),
          invitations: requireInvitationList(invitations, requestFarmId),
          error: null,
        };
        if (!controller.signal.aborted && isCurrent(requestFarmId, generation, "load")) setState(next);
        return { refreshed: true };
      } catch (error) {
        if (controller.signal.aborted || !isCurrent(requestFarmId, generation, "load")) return { cancelled: true };
        setState({ loading: false, staff: [], invitations: [], error });
        return { error };
      } finally {
        if (loadPendingRef.current?.generation === generation) loadPendingRef.current = null;
        if (loadControllerRef.current === controller) loadControllerRef.current = null;
      }
    })();
    loadPendingRef.current = { farmId: requestFarmId, controller, generation, promise };
    return promise;
  }, [api, authoritativeOwner, canView, isCurrent]);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      loadControllerRef.current?.abort();
      loadPendingRef.current = null;
      mutationControllerRef.current?.abort();
      loadGenerationRef.current += 1;
      mutationGenerationRef.current += 1;
      mutationPendingRef.current = false;
    };
  }, []);

  useEffect(() => {
    loadGenerationRef.current += 1;
    mutationGenerationRef.current += 1;
    loadControllerRef.current?.abort();
    loadPendingRef.current = null;
    mutationControllerRef.current?.abort();
    mutationPendingRef.current = false;
    setAction(null);
    setActionError(null);
    setPendingAction(false);
    if (farmId && authStatusRef.current === "authenticated") void load();
    else setState(initialState);
  }, [farmId, auth?.status, load]);

  const openAction = (kind, item, value) => {
    if (!farmId || !authoritativeOwner || mutationPendingRef.current) return;
    setAction({ kind, item, value, farmId });
    setActionError(null);
  };

  const confirmAction = async () => {
    if (!action || mutationPendingRef.current || action.farmId !== farmIdRef.current) return;

    mutationPendingRef.current = true;
    setPendingAction(true);
    setActionError(null);
    const controller = new AbortController();
    mutationControllerRef.current = controller;
    const generation = ++mutationGenerationRef.current;
    const requestFarmId = action.farmId;
    const { kind, item, value } = action;

    try {
      let response;
      if (kind === "revoke") response = await api.invitations.revoke(requestFarmId, item.id, { signal: controller.signal });
      if (kind === "reissue") response = await api.invitations.reissue(requestFarmId, item.id, { signal: controller.signal });
      if (kind === "role") response = await api.staff.updateRole(requestFarmId, item.membership_id, value, { signal: controller.signal });
      if (kind === "status") response = await api.staff.updateStatus(requestFarmId, item.membership_id, value, { signal: controller.signal });

      if (kind === "revoke" || kind === "reissue") requireInvitationResponse(response, requestFarmId);
      else requireStaffResponse(response);
      if (!isCurrent(requestFarmId, generation, "mutation") || controller.signal.aborted) return;

      setAction(null);
      await load({ showLoading: false });
      if (isCurrent(requestFarmId, generation, "mutation")) void farm.refreshFarms();
    } catch (error) {
      if (controller.signal.aborted || !isCurrent(requestFarmId, generation, "mutation")) return;
      setActionError(staffErrorMessage(error, {
        invitation: kind === "revoke" || kind === "reissue",
        ambiguous: isAmbiguous(error),
      }));
      setAction(null);
    } finally {
      if (isCurrent(requestFarmId, generation, "mutation")) {
        mutationPendingRef.current = false;
        setPendingAction(false);
      }
    }
  };

  const canManageMember = (member) => authoritativeOwner
    && member.role !== "FARM_OWNER"
    && member.user_id !== farm.activeFarm?.owner_id;

  return (
    <RequireFarm>
      <RequirePermission permission="staff.view">
        <ScrollView contentContainerStyle={{ width: "100%", alignSelf: "center", maxWidth: layout.contentMaxWidth, padding: spacing.xl, gap: spacing.lg }}>
          <Text accessibilityRole="header" style={{ color: theme.colors.text, fontSize: typography.sizes.heading, fontWeight: typography.weights.extrabold }}>Staff & invitations</Text>
          <Text style={{ color: theme.colors.textSecondary }}>{farm.activeFarm?.name} · access shown only from verified farm context.</Text>
          {authoritativeOwner ? <AppButton title="Invite staff" onPress={onInvite} /> : null}
          {state.loading ? (
            <FeedbackState type="loading" title="Loading staff" message="Retrieving authorized farm membership data." showSkeleton />
          ) : state.error ? (
            <FeedbackState type="error" title="Staff unavailable" message={staffErrorMessage(state.error)} actionLabel="Retry" onAction={() => { void load(); }} />
          ) : (
            <>
              <Text style={{ color: theme.colors.text, fontWeight: typography.weights.bold }}>Members</Text>
              {actionError ? <FeedbackState type="error" title="Action unavailable" message={actionError} /> : null}
              {state.staff.length ? state.staff.map((member) => (
                <AppCard key={member.membership_id}>
                  <Text style={{ color: theme.colors.text, fontWeight: typography.weights.bold }}>{member.name}</Text>
                  <Text style={{ color: theme.colors.textSecondary }}>{member.email}</Text>
                  <StatusBadge status={member.status === "ACTIVE" ? "success" : "warning"} label={`${roleLabel(member.role)} · ${member.status}`} />
                  {canManageMember(member) ? (
                    <View style={{ flexDirection: "row", flexWrap: "wrap", gap: spacing.sm }}>
                      {[
                        ["Set Manager", "FARM_MANAGER"],
                        ["Set Worker", "WORKER"],
                        ["Set Veterinarian", "VETERINARIAN"],
                      ].map(([label, role]) => (
                        <AppButton key={role} title={label} size="small" variant="outline" fullWidth={false} disabled={member.role === role} onPress={() => openAction("role", member, role)} />
                      ))}
                      <AppButton title={member.status === "ACTIVE" ? "Deactivate" : "Activate"} size="small" variant="outline" fullWidth={false} onPress={() => openAction("status", member, member.status === "ACTIVE" ? "INACTIVE" : "ACTIVE")} />
                    </View>
                  ) : null}
                </AppCard>
              )) : <FeedbackState title="No staff members" message="No accessible members were returned by the server." />}
              {authoritativeOwner ? (
                <>
                  <Text style={{ color: theme.colors.text, fontWeight: typography.weights.bold }}>Invitations</Text>
                  {state.invitations.length ? state.invitations.map((invitation) => (
                    <AppCard key={invitation.id}>
                      <Text style={{ color: theme.colors.text, fontWeight: typography.weights.bold }}>{invitation.email}</Text>
                      <StatusBadge status={invitation.status === "PENDING" ? "info" : "neutral"} label={`${roleLabel(invitation.role)} · ${invitation.status}`} />
                      {invitation.status !== "ACCEPTED" && invitation.status !== "REJECTED" ? (
                        <View style={{ flexDirection: "row", gap: spacing.sm }}>
                          <AppButton title="Reissue" size="small" variant="outline" fullWidth={false} onPress={() => openAction("reissue", invitation)} />
                          {invitation.status === "PENDING" ? <AppButton title="Revoke" size="small" variant="danger" fullWidth={false} onPress={() => openAction("revoke", invitation)} /> : null}
                        </View>
                      ) : null}
                    </AppCard>
                  )) : <FeedbackState title="No invitations" message="No invitations have been returned for this farm." />}
                </>
              ) : null}
            </>
          )}
          <ConfirmationDialog
            visible={Boolean(action)}
            title={action?.kind === "revoke" ? "Revoke invitation" : "Confirm staff change"}
            message={action?.kind === "revoke" ? "This pending invitation will no longer be usable." : "The server will verify this owner-authorized change."}
            confirmLabel="Confirm"
            destructive={action?.kind === "revoke" || action?.kind === "status"}
            pending={pendingAction}
            onCancel={() => { if (!mutationPendingRef.current) setAction(null); }}
            onConfirm={confirmAction}
          />
        </ScrollView>
      </RequirePermission>
    </RequireFarm>
  );
}
