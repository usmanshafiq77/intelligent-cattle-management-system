import { useEffect, useState } from "react";
import { useLocalSearchParams, useRouter } from "expo-router";

import { VerificationScreen } from "../../src/features/auth/screens/VerificationScreen";
import { ROUTES } from "../../src/navigation/routes";

export default function VerifyEmailRoute() {
  const router = useRouter();
  const params = useLocalSearchParams();
  const rawToken = Array.isArray(params.token) ? params.token[0] : params.token;
  const [initialToken] = useState(typeof rawToken === "string" ? rawToken : "");

  useEffect(() => {
    if (rawToken) router.setParams({ token: undefined });
  }, [rawToken, router]);

  const onBack = () => (router.canGoBack() ? router.back() : router.replace(ROUTES.login));
  return <VerificationScreen initialToken={initialToken} onBack={onBack} />;
}
