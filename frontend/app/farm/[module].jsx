import { useLocalSearchParams, useRouter } from "expo-router";

import { FarmModuleScreen } from "../../src/features/navigation/screens/FarmModuleScreen";
import { ROUTES } from "../../src/navigation/routes";

export default function FarmModuleRoute() {
  const router = useRouter();
  const params = useLocalSearchParams();
  const moduleKey = Array.isArray(params.module) ? params.module[0] : params.module;
  return <FarmModuleScreen moduleKey={moduleKey} onBack={() => router.replace(ROUTES.dashboard)} />;
}
