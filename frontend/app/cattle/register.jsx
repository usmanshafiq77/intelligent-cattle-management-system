import { useRouter } from "expo-router";

import { CattleCreateScreen } from "../../src/features/cattle/screens/CattleCreateScreen";
import { ROUTES } from "../../src/navigation/routes";

export default function CattleRegisterRoute() {
  const router = useRouter();
  return <CattleCreateScreen onBack={() => router.replace(ROUTES.cattle)} onCreated={(animal) => router.replace(ROUTES.cattleDetail(animal.id))} />;
}
