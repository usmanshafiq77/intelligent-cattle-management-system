import { useRouter } from "expo-router";

import { CattleListScreen } from "../../src/features/cattle/screens/CattleListScreen";
import { ROUTES } from "../../src/navigation/routes";

export default function CattleListRoute() {
  const router = useRouter();
  return <CattleListScreen onBack={() => router.replace(ROUTES.dashboard)} onCreate={() => router.push(ROUTES.registerCattle)} onOpen={(id) => router.push(ROUTES.cattleDetail(id))} />;
}
