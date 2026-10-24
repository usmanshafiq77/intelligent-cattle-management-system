import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";

import { farmsApi } from "../../../api/farms";
import { permissionsApi } from "../../../api/permissions";
import { useAuth } from "../../auth/context/AuthProvider";
import { requireEffectivePermissions, requireFarmList, requireFarmResponse } from "../farmContracts";

const FarmContext = createContext(null);

const defaultApi = Object.freeze({
  listFarms: (options) => farmsApi.list(options),
  createFarm: (payload, options) => farmsApi.create(payload, options),
  getEffectivePermissions: (farmId, options) => permissionsApi.getEffective(farmId, options),
});

function farmIssue(error) {
  if (error?.status === 403 || error?.status === 404) {
    return { kind: "access", message: "Your access to this farm could not be confirmed. Refresh your farm list." };
  }
  if (error?.status === 429) {
    return { kind: "rate-limit", message: "Farm access checks are temporarily rate limited. Please wait and retry." };
  }
  if (error?.status === 503 || error?.category === "network" || error?.code === "TIMEOUT") {
    return { kind: "unavailable", message: "Farm access could not be verified right now. Your session has not been signed out." };
  }
  return { kind: "error", message: "Farm access could not be verified safely. Please retry." };
}

const initialState = Object.freeze({
  status: "idle",
  farms: [],
  activeFarm: null,
  membership: null,
  permissions: [],
  issue: null,
});

export function FarmProvider({ children, api = defaultApi }) {
  const auth = useAuth();
  const mounted = useRef(false);
  const operation = useRef(0);
  const requestController = useRef(null);
  const stateRef = useRef(initialState);
  const [state, setState] = useState(initialState);

  const replaceState = useCallback((nextState) => {
    stateRef.current = nextState;
    setState(nextState);
  }, []);

  const updateIfCurrent = useCallback((currentOperation, nextState) => {
    if (mounted.current && operation.current === currentOperation) replaceState(nextState);
  }, [replaceState]);

  const beginRequest = useCallback(() => {
    requestController.current?.abort();
    const controller = new AbortController();
    requestController.current = controller;
    return { controller, currentOperation: ++operation.current };
  }, []);

  const activateVerifiedFarm = useCallback(async (farm, farms, request) => {
    updateIfCurrent(request.currentOperation, {
      status: "loading-permissions",
      farms,
      activeFarm: null,
      membership: null,
      permissions: [],
      issue: null,
    });

    try {
      const response = await api.getEffectivePermissions(farm.id, { signal: request.controller.signal });
      const verified = requireEffectivePermissions(response, farm.id);
      updateIfCurrent(request.currentOperation, {
        status: "ready",
        farms,
        activeFarm: farm,
        membership: {
          id: verified.membershipId,
          role: verified.role,
          status: "ACTIVE",
          customRoleIds: verified.customRoleIds,
        },
        permissions: verified.permissions,
        issue: null,
      });
      return { selected: true, farm };
    } catch (error) {
      if (error?.isCancelled || request.controller.signal.aborted) return { cancelled: true };
      updateIfCurrent(request.currentOperation, {
        status: "permission-unavailable",
        farms,
        activeFarm: null,
        membership: null,
        permissions: [],
        issue: farmIssue(error),
      });
      return { selected: false, error };
    }
  }, [api, updateIfCurrent]);

  const loadFarms = useCallback(async () => {
    if (auth.status !== "authenticated") return { skipped: true };
    const request = beginRequest();
    const previousFarmId = stateRef.current.activeFarm?.id;
    updateIfCurrent(request.currentOperation, {
      ...initialState,
      status: "loading",
    });

    try {
      const farms = requireFarmList(await api.listFarms({ signal: request.controller.signal }));
      if (operation.current !== request.currentOperation || !mounted.current) return { cancelled: true };
      if (!farms.length) {
        updateIfCurrent(request.currentOperation, { ...initialState, status: "no-farms", farms });
        return { farms };
      }

      const previousFarm = farms.find((farm) => farm.id === previousFarmId);
      if (previousFarm) return activateVerifiedFarm(previousFarm, farms, request);
      if (farms.length === 1) return activateVerifiedFarm(farms[0], farms, request);

      updateIfCurrent(request.currentOperation, {
        ...initialState,
        status: "selection-required",
        farms,
      });
      return { farms };
    } catch (error) {
      if (error?.isCancelled || request.controller.signal.aborted) return { cancelled: true };
      updateIfCurrent(request.currentOperation, {
        ...initialState,
        status: "unavailable",
        issue: farmIssue(error),
      });
      return { error };
    }
  }, [activateVerifiedFarm, api, auth.status, beginRequest, updateIfCurrent]);

  const selectFarm = useCallback(async (farmId) => {
    const farm = stateRef.current.farms.find((candidate) => candidate.id === farmId);
    if (!farm) {
      replaceState({
        ...stateRef.current,
        status: "selection-required",
        activeFarm: null,
        membership: null,
        permissions: [],
        issue: { kind: "invalid-selection", message: "Select a farm from your verified accessible farm list." },
      });
      return { selected: false };
    }
    return activateVerifiedFarm(farm, stateRef.current.farms, beginRequest());
  }, [activateVerifiedFarm, beginRequest, replaceState]);

  const createFarm = useCallback(async (payload) => {
    if (auth.status !== "authenticated") return { created: false, error: new Error("Authentication is required to create a farm.") };
    const previousFarms = stateRef.current.farms;
    const request = beginRequest();
    updateIfCurrent(request.currentOperation, {
      status: "creating",
      farms: previousFarms,
      activeFarm: null,
      membership: null,
      permissions: [],
      issue: null,
    });

    let created = null;
    let creationResponseReceived = false;
    try {
      const response = await api.createFarm(payload, { signal: request.controller.signal });
      creationResponseReceived = true;
      created = requireFarmResponse(response);
      const farms = requireFarmList(await api.listFarms({ signal: request.controller.signal }));
      const verifiedFarm = farms.find((farm) => farm.id === created.id);
      if (!verifiedFarm) throw new Error("The newly created farm was not returned by the active-membership list.");
      const activation = await activateVerifiedFarm(verifiedFarm, farms, request);
      return { created: true, farm: verifiedFarm, ...activation };
    } catch (error) {
      if (error?.isCancelled || request.controller.signal.aborted) return { cancelled: true };
      updateIfCurrent(request.currentOperation, {
        status: previousFarms.length ? "selection-required" : "no-farms",
        farms: previousFarms,
        activeFarm: null,
        membership: null,
        permissions: [],
        issue: farmIssue(error),
      });
      return { created: Boolean(created), farm: created, error, ambiguous: creationResponseReceived || error?.code === "TIMEOUT" || error?.category === "network" };
    }
  }, [activateVerifiedFarm, api, auth.status, beginRequest, updateIfCurrent]);

  useEffect(() => {
    mounted.current = true;
    if (auth.status === "authenticated") void loadFarms();
    else {
      requestController.current?.abort();
      operation.current += 1;
      replaceState(initialState);
    }
    return () => {
      mounted.current = false;
      requestController.current?.abort();
      operation.current += 1;
    };
  }, [auth.status, auth.user?.id, loadFarms, replaceState]);

  const permissionSet = useMemo(() => new Set(state.permissions), [state.permissions]);
  const value = useMemo(() => ({
    ...state,
    isLoading: state.status === "loading" || state.status === "loading-permissions",
    hasActiveFarm: state.status === "ready" && Boolean(state.activeFarm),
    can: (permission) => typeof permission === "string" && permissionSet.has(permission),
    selectFarm,
    createFarm,
    refreshFarms: loadFarms,
  }), [createFarm, loadFarms, permissionSet, selectFarm, state]);

  return <FarmContext.Provider value={value}>{children}</FarmContext.Provider>;
}

export function useFarm() {
  const context = useContext(FarmContext);
  if (!context) throw new Error("useFarm must be used inside FarmProvider.");
  return context;
}
