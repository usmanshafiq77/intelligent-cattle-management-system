import { useRouter } from "expo-router";

import { NotFoundScreen } from "../src/features/navigation/screens/NotFoundScreen";
import { useAuth } from "../src/features/auth/context/AuthProvider";
import { ROUTES } from "../src/navigation/routes";

export default function NotFoundRoute() {
  const router = useRouter();
  const auth = useAuth();
  const destination = auth.isAuthenticated ? ROUTES.dashboard : ROUTES.home;
  return <NotFoundScreen onReturnHome={() => router.replace(destination)} />;
}
