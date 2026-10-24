import { useEffect, useState } from "react";
import { useLocalSearchParams, useRouter } from "expo-router";
import { AcceptInvitationScreen } from "../../src/features/staff/screens/AcceptInvitationScreen";
import { ROUTES } from "../../src/navigation/routes";

export default function AcceptInvitationRoute() {
  const router = useRouter();
  const params = useLocalSearchParams();
  const rawToken = Array.isArray(params.token) ? params.token[0] : params.token;
  const [initialToken] = useState(typeof rawToken === "string" ? rawToken : "");

  useEffect(() => {
    if (rawToken) router.setParams({ token: undefined });
  }, [rawToken, router]);

  return <AcceptInvitationScreen initialToken={initialToken} onAccepted={() => router.replace(ROUTES.dashboard)} />;
}
