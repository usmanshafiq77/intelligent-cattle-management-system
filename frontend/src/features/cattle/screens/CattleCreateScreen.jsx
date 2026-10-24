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

export function CattleCreateScreen({ onBack, onCreated, api = cattleApi }) {
  const farm = useFarm();
  return <RequireFarm><RequirePermission permission="cattle.create"><CreateContent farm={farm} onBack={onBack} onCreated={onCreated} api={api} /></RequirePermission></RequireFarm>;
}

function CreateContent({ farm, onBack, onCreated, api }) {
  const auth = useOptionalAuth();
  const [values, setValues] = useState(() => initialFormValues());
  const [errors, setErrors] = useState({});
  const [breeds, setBreeds] = useState([]);
  const [breedError, setBreedError] = useState(null);
  const [feedback, setFeedback] = useState(null);
  const [pending, setPending] = useState(false);
  const mutation = useRef({ operation: 0, controller: null, locked: false });
  const farmId = farm.activeFarm.id;

  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    setBreedError(null);
    api.listBreeds({ limit: 200 }, { signal: controller.signal }).then((response) => {
      if (active) setBreeds(requireBreedList(response));
    }).catch((error) => {
      if (active && !error?.isCancelled) setBreedError(cattleErrorMessage(error));
    });
    return () => { active = false; controller.abort(); };
  }, [api]);

  useEffect(() => () => {
    mutation.current.operation += 1;
    mutation.current.controller?.abort();
  }, [farmId, auth?.status, auth?.user?.id]);

  const change = (field, value) => {
    setValues((current) => ({ ...current, [field]: value }));
    setErrors((current) => ({ ...current, [field]: undefined }));
  };

  const submit = async () => {
    if (mutation.current.locked) return;
    const nextErrors = validateCattleForm(values);
    setErrors(nextErrors);
    if (Object.keys(nextErrors).length) return;
    const controller = new AbortController();
    const operation = mutation.current.operation + 1;
    mutation.current = { operation, controller, locked: true };
    setPending(true);
    setFeedback(null);
    try {
      const response = await api.create(farmId, cattlePayload(values), { signal: controller.signal });
      const created = requireCattle(response, farmId);
      if (mutation.current.operation !== operation || farm.activeFarm?.id !== farmId || auth?.status !== "authenticated") return;
      let animal = created;
      try {
        animal = requireCattle(await api.get(farmId, created.id, { signal: controller.signal }), farmId);
      } catch (refreshError) {
        if (refreshError?.isCancelled || controller.signal.aborted) return;
      }
      if (mutation.current.operation !== operation || farm.activeFarm?.id !== farmId || auth?.status !== "authenticated") return;
      mutation.current.locked = false;
      setPending(false);
      onCreated?.(animal);
    } catch (error) {
      if (mutation.current.operation !== operation || error?.isCancelled || controller.signal.aborted) return;
      mutation.current.locked = false;
      setPending(false);
      setFeedback(cattleErrorMessage(error, { mutation: true }));
      if (error?.fieldErrors) setErrors((current) => ({ ...current, ...Object.fromEntries(Object.entries(error.fieldErrors).map(([key, messages]) => [key, messages[0]])) }));
    }
  };

  return (
    <CattlePage title="Register cattle" subtitle={`Add a verified animal profile to ${farm.activeFarm.name}.`} onBack={onBack}>
      {breedError ? <FeedbackState type="error" title="Breed catalog unavailable" message={breedError} actionLabel="Continue without breed" onAction={() => setBreedError(null)} compact /> : null}
      <AppCard>
        <CattleForm values={values} errors={errors} breeds={breeds} onChange={change} onSubmit={submit} onCancel={onBack} pending={pending} feedback={feedback} />
      </AppCard>
    </CattlePage>
  );
}
