import { useRouter } from "expo-router";

import { AuthComingSoonScreen } from "../../src/features/auth/screens/AuthComingSoonScreen";
import { ROUTES } from "../../src/navigation/routes";

export default function SignupRoute() {
  const router = useRouter();
  const goBack = () => (router.canGoBack() ? router.back() : router.replace(ROUTES.home));
  return <AuthComingSoonScreen journey="signup" onBack={goBack} />;
}
