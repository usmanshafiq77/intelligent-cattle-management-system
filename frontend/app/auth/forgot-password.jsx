import { useRouter } from "expo-router";

import { ForgotPasswordScreen } from "../../src/features/auth/screens/ForgotPasswordScreen";
import { ROUTES } from "../../src/navigation/routes";

export default function ForgotPasswordRoute() {
  const router = useRouter();
  const goBack = () => (router.canGoBack() ? router.back() : router.replace(ROUTES.login));
  return <ForgotPasswordScreen onBack={goBack} onLogIn={() => router.replace(ROUTES.login)} />;
}
