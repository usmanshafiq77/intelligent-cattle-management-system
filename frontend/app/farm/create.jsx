import { useRouter } from "expo-router";

import { FarmCreateScreen } from "../../src/features/farms/screens/FarmCreateScreen";
import { ROUTES } from "../../src/navigation/routes";

export default function FarmCreateRoute() {
  const router = useRouter();
  return <FarmCreateScreen onBack={() => router.replace(ROUTES.dashboard)} onCreated={() => router.replace(ROUTES.dashboard)} />;
}
