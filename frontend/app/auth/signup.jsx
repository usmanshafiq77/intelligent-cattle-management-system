import { useRouter } from "expo-router";

import { SignupScreen } from "../../src/features/auth/screens/SignupScreen";
import { ROUTES } from "../../src/navigation/routes";

export default function SignupRoute() {
  const router = useRouter();
  const goBack = () => (router.canGoBack() ? router.back() : router.replace(ROUTES.home));
  return (
    <SignupScreen
      onBack={goBack}
      onLogIn={() => router.replace(ROUTES.login)}
    />
  );
}
