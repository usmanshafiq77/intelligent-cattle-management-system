import { useRouter } from "expo-router";

import { DesignSystemScreen } from "../../src/features/home/screens/WelcomeScreen";
import { DevelopmentOnlyRoute } from "../../src/navigation/DevelopmentOnlyRoute";
import { ROUTES } from "../../src/navigation/routes";

export default function DesignSystemRoute() {
  const router = useRouter();
  return (
    <DevelopmentOnlyRoute onReturnHome={() => router.replace(ROUTES.home)}>
      <DesignSystemScreen />
    </DevelopmentOnlyRoute>
  );
}
