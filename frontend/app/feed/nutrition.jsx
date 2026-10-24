import { useRouter } from "expo-router";
import { NutritionPlansScreen } from "../../src/features/feed/screens/FeedScreens";

export default function NutritionPlansRoute() {
  const router = useRouter();
  return <NutritionPlansScreen onBack={() => router.replace("/feed")} />;
}
