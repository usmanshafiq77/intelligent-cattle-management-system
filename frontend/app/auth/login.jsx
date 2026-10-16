import { useRouter } from "expo-router";

import { LoginScreen } from "../../src/features/auth/screens/LoginScreen";
import { ROUTES } from "../../src/navigation/routes";

export default function LoginRoute() {
  const router = useRouter();
  const goBack = () => (router.canGoBack() ? router.back() : router.replace(ROUTES.home));
  return (
    <LoginScreen
      onBack={goBack}
      onCreateAccount={() => router.replace(ROUTES.signup)}
    />
  );
}
