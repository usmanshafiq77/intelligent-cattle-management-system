import { useCallback, useEffect, useRef, useState } from "react";

import { cattleApi } from "../../../api/cattle";
import { requireCattleSummary } from "../cattleContracts";

const initialState = Object.freeze({ status: "idle", summary: null, error: null });

export function useCattleSummary({ farmId, enabled, api = cattleApi } = {}) {
  const generation = useRef(0);
  const controller = useRef(null);
  const mounted = useRef(true);
  const [state, setState] = useState(initialState);

  const load = useCallback(async () => {
    controller.current?.abort();
    const requestController = new AbortController();
    controller.current = requestController;
    const current = ++generation.current;
    if (!enabled || !farmId) {
      setState(initialState);
      return { skipped: true };
    }
    setState({ status: "loading", summary: null, error: null });
    try {
      const summary = requireCattleSummary(await api.summary(farmId, undefined, { signal: requestController.signal }));
      if (!mounted.current || generation.current !== current || requestController.signal.aborted) return { cancelled: true };
      setState({ status: "ready", summary, error: null });
      return { summary };
    } catch (error) {
      if (!mounted.current || generation.current !== current || requestController.signal.aborted || error?.isCancelled) return { cancelled: true };
      setState({ status: "error", summary: null, error });
      return { error };
    }
  }, [api, enabled, farmId]);

  useEffect(() => {
    mounted.current = true;
    void load();
    return () => {
      mounted.current = false;
      controller.current?.abort();
      generation.current += 1;
    };
  }, [load]);

  return { ...state, refresh: load };
}
