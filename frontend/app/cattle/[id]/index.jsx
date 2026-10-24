import { useLocalSearchParams, useRouter } from "expo-router";

import { CattleDetailScreen } from "../../../src/features/cattle/screens/CattleDetailScreen";
import { ROUTES } from "../../../src/navigation/routes";

export default function CattleDetailRoute() {
  const router = useRouter();
  const { id } = useLocalSearchParams();
  const cattleId = Array.isArray(id) ? id[0] : id;
  return <CattleDetailScreen cattleId={cattleId} onBack={() => router.replace(ROUTES.cattle)} onEdit={(animalId) => router.push(ROUTES.editCattle(animalId))} />;
}
