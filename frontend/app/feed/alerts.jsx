import { useRouter } from "expo-router";
import { LowStockAlertsScreen } from "../../src/features/feed/screens/FeedScreens";

export default function LowStockAlertsRoute() {
  const router = useRouter();
  return <LowStockAlertsScreen onBack={() => router.replace("/feed")} />;
}
