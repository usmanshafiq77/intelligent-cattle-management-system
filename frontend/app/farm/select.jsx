import { useRouter } from "expo-router";

import { FarmSelectionScreen } from "../../src/features/farms/screens/FarmSelectionScreen";
import { ROUTES } from "../../src/navigation/routes";

export default function FarmSelectRoute() {
  const router = useRouter();
  return <FarmSelectionScreen onBack={() => router.replace(ROUTES.dashboard)} onCreate={() => router.push(ROUTES.createFarm)} />;
}
