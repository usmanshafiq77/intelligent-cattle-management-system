import { useEffect, useRef, useState } from "react";

import { cattleApi } from "../../../api/cattle";
import { AppCard } from "../../../components/ui/AppCard";
import { FeedbackState } from "../../../components/ui/FeedbackState";
import { useOptionalAuth } from "../../auth/context/AuthProvider";
import { useFarm } from "../../farms/context/FarmProvider";
import { RequireFarm, RequirePermission } from "../../permissions/guards";
import { cattlePayload, initialFormValues, requireBreedList, requireCattle, validateCattleForm } from "../cattleContracts";
import { cattleErrorMessage } from "../cattleErrors";
import { CattleForm } from "../components/CattleForm";
import { CattlePage } from "../components/CattlePage";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

export function CattleEditScreen({ cattleId, onBack, onUpdated, api = cattleApi }) {
  const farm = useFarm();
  return <RequireFarm><RequirePermission permission="cattle.update"><EditContent cattleId={cattleId} farm={farm} onBack={onBack} onUpdated={onUpdated} api={api} /></RequirePermission></RequireFarm>;
}

function EditContent({ cattleId, farm, onBack, onUpdated, api }) {
  const auth = useOptionalAuth();
  const [state, setState] = useState({ status: "loading", animal: null, breeds: [], error: null });
  const [values, setValues] = useState(null);
  const [errors, setErrors] = useState({});
  const [feedback, setFeedback] = useState(null);
  const mutation = useRef({ operation: 0, controller: null, locked: false });
  const farmId = farm.activeFarm.id;

  useEffect(() => () => {
    mutation.current.controller?.abort();
    mutation.current.operation += 1;
    mutation.current.locked = false;
  }, [auth?.status, auth?.user?.id]);

  useEffect(() => {
    const controller = new AbortController();
    const operation = ++mutation.current.operation;
    if (!UUID.test(String(cattleId || ""))) {
      setState({ status: "invalid", animal: null, breeds: [], error: null });
      return () => controller.abort();
    }
    setState({ status: "loading", animal: null, breeds: [], error: null });
    Promise.all([api.get(farmId, cattleId, { signal: controller.signal }), api.listBreeds({ limit: 200 }, { signal: controller.signal })]).then(([animalResponse, breedResponse]) => {
      if (mutation.current.operation !== operation || controller.signal.aborted) return;
      const animal = requireCattle(animalResponse, farmId);
      const breeds = requireBreedList(breedResponse);
      setState({ status: "ready", animal, breeds, error: null });
      setValues(initialFormValues(animal));
    }).catch((error) => {
      if (mutation.current.operation === operation && !error?.isCancelled) setState({ status: "error", animal: null, breeds: [], error });
    });
    return () => { controller.abort(); mutation.current.operation += 1; mutation.current.locked = false; };
  }, [api, cattleId, farmId]);

  const change = (field, value) => { setValues((current) => ({ ...current, [field]: value })); setErrors((current) => ({ ...current, [field]: undefined })); };
  const submit = async () => {
    if (mutation.current.locked) return;
    const nextErrors = validateCattleForm(values, { editing: true });
    setErrors(nextErrors);
    if (Object.keys(nextErrors).length) return;
    const controller = new AbortController();
    const operation = mutation.current.operation + 1;
    mutation.current = { operation, controller, locked: true };
    setState((current) => ({ ...current, status: "saving" }));
    setFeedback(null);
    try {
      const saved = requireCattle(await api.update(farmId, cattleId, cattlePayload(values, { editing: true }), { signal: controller.signal }), farmId);
      if (mutation.current.operation !== operation || farm.activeFarm?.id !== farmId || auth?.status !== "authenticated") return;
      let authoritative = saved;
      let refreshFailed = false;
      try { authoritative = requireCattle(await api.get(farmId, cattleId, { signal: controller.signal }), farmId); } catch (refreshError) { if (!refreshError?.isCancelled) refreshFailed = true; }
      if (mutation.current.operation !== operation || controller.signal.aborted || farm.activeFarm?.id !== farmId) return;
      mutation.current.locked = false;
      setState((current) => ({ ...current, status: "ready", animal: authoritative }));
      if (refreshFailed) setFeedback("Changes were saved, but the refreshed profile could not be loaded. Open the profile to verify current values.");
      onUpdated?.(authoritative, { refreshFailed });
    } catch (error) {
      if (mutation.current.operation !== operation || error?.isCancelled || controller.signal.aborted) return;
      mutation.current.locked = false;
      setState((current) => ({ ...current, status: "ready" }));
      setFeedback(cattleErrorMessage(error, { mutation: true }));
      if (error?.fieldErrors) setErrors((current) => ({ ...current, ...Object.fromEntries(Object.entries(error.fieldErrors).map(([key, messages]) => [key, messages[0]])) }));
    }
  };

  if (state.status === "invalid") return <CattlePage title="Invalid cattle link" onBack={onBack}><FeedbackState type="error" title="Invalid cattle ID" message="Choose a verified cattle record from the directory." /></CattlePage>;
  if (state.status === "loading") return <CattlePage title="Edit cattle" onBack={onBack}><FeedbackState type="loading" title="Loading editable profile" showSkeleton /></CattlePage>;
  if (state.status === "error") return <CattlePage title="Edit unavailable" onBack={onBack}><FeedbackState type="error" title="Could not load cattle" message={cattleErrorMessage(state.error)} /></CattlePage>;
  return <CattlePage title={`Edit ${state.animal.name || state.animal.tag_number}`} subtitle="Species and sex are immutable. Other supported profile fields can be updated." onBack={onBack}><AppCard><CattleForm editing values={values} errors={errors} breeds={state.breeds} onChange={change} onSubmit={submit} onCancel={onBack} pending={state.status === "saving"} feedback={feedback} /></AppCard></CattlePage>;
}
