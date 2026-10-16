import { useCallback, useEffect, useRef, useState } from "react";

export function useAuthSubmission() {
  const mounted = useRef(true);
  const submittingRef = useRef(false);
  const controllerRef = useRef(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => () => {
    mounted.current = false;
    controllerRef.current?.abort();
  }, []);

  const run = useCallback(async (operation) => {
    if (submittingRef.current) return { skipped: true };
    submittingRef.current = true;
    setSubmitting(true);
    const controller = new AbortController();
    controllerRef.current = controller;
    try {
      const value = await operation(controller.signal);
      return mounted.current ? { value } : { cancelled: true };
    } catch (error) {
      return mounted.current ? { error } : { cancelled: true };
    } finally {
      controllerRef.current = null;
      submittingRef.current = false;
      if (mounted.current) setSubmitting(false);
    }
  }, []);

  return { submitting, run };
}
