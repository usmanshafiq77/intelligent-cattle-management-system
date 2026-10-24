import { useLocalSearchParams, useRouter } from "expo-router";

import { CattleEditScreen } from "../../../src/features/cattle/screens/CattleEditScreen";
import { ROUTES } from "../../../src/navigation/routes";

export default function CattleEditRoute() {
  const router = useRouter();
  const { id } = useLocalSearchParams();
  const cattleId = Array.isArray(id) ? id[0] : id;
  return <CattleEditScreen cattleId={cattleId} onBack={() => router.back()} onUpdated={(animal) => router.replace(ROUTES.cattleDetail(animal.id))} />;
}
