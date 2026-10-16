import { useRouter } from "expo-router";

import { NotFoundScreen } from "../src/features/navigation/screens/NotFoundScreen";
import { ROUTES } from "../src/navigation/routes";

export default function NotFoundRoute() {
  const router = useRouter();
  return <NotFoundScreen onReturnHome={() => router.replace(ROUTES.home)} />;
}
