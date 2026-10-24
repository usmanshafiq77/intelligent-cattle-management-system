import { useEffect, useState } from "react";
import { useLocalSearchParams, useRouter } from "expo-router";

import { ResetPasswordScreen } from "../src/features/auth/screens/ResetPasswordScreen";
import { ROUTES } from "../src/navigation/routes";

export default function ResetPasswordRoute() {
  const router = useRouter();
  const params = useLocalSearchParams();
  const rawToken = Array.isArray(params.token) ? params.token[0] : params.token;
  const [token] = useState(typeof rawToken === "string" ? rawToken : "");

  useEffect(() => {
    if (rawToken) router.setParams({ token: undefined });
  }, [rawToken, router]);

  const goBack = () => (router.canGoBack() ? router.back() : router.replace(ROUTES.login));
  return (
    <ResetPasswordScreen
      token={token}
      onBack={goBack}
      onLogIn={() => router.replace(ROUTES.login)}
      onRequestNewLink={() => router.replace(ROUTES.forgotPassword)}
    />
  );
}
