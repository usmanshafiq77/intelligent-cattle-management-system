import { useCallback, useEffect, useRef, useState } from "react";

import { cattleApi } from "../../../api/cattle";
import { requireCattleList, requireCattleSummary } from "../cattleContracts";

export function useCattleCollection({ farmId, enabled, query = {}, api = cattleApi } = {}) {
  const operation = useRef(0);
  const controller = useRef(null);
  const mounted = useRef(true);
  const [state, setState] = useState({ status: "idle", animals: [], total: 0, complete: false, error: null });

  const load = useCallback(async () => {
    controller.current?.abort();
    const requestController = new AbortController();
    controller.current = requestController;
    const current = ++operation.current;
    if (!enabled || !farmId) {
      setState({ status: "idle", animals: [], total: 0, complete: false, error: null });
      return { skipped: true };
    }
    setState({ status: "loading", animals: [], total: 0, complete: false, error: null });
    try {
      const { limit = 50, offset = 0, sort, ...filters } = query;
      const [listResponse, summaryResponse] = await Promise.all([
        api.list(farmId, { ...filters, sort, limit, offset }, { signal: requestController.signal }),
        api.summary(farmId, filters, { signal: requestController.signal }),
      ]);
      const animals = requireCattleList(listResponse, farmId);
      const summary = requireCattleSummary(summaryResponse);
      if (!mounted.current || operation.current !== current || requestController.signal.aborted) return { cancelled: true };
      const complete = offset + animals.length >= summary.total;
      setState({ status: "ready", animals, total: summary.total, complete, error: null });
      return { animals, total: summary.total, complete };
    } catch (error) {
      if (!mounted.current || operation.current !== current || requestController.signal.aborted || error?.isCancelled) return { cancelled: true };
      setState({ status: "error", animals: [], total: 0, complete: false, error });
      return { error };
    }
  }, [api, enabled, farmId, query]);

  useEffect(() => {
    mounted.current = true;
    void load();
    return () => {
      mounted.current = false;
      controller.current?.abort();
      operation.current += 1;
    };
  }, [load]);

  return { ...state, refresh: load };
}
