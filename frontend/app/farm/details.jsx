import { useRouter } from "expo-router";

import { FarmDetailsScreen } from "../../src/features/farms/screens/FarmDetailsScreen";
import { ROUTES } from "../../src/navigation/routes";

export default function FarmDetailsRoute() {
  const router = useRouter();
  return <FarmDetailsScreen onBack={() => router.replace(ROUTES.dashboard)} />;
}
