import { useRouter } from "expo-router";
import { FeedPurchasesScreen } from "../../src/features/feed/screens/FeedScreens";

export default function FeedPurchasesRoute() {
  const router = useRouter();
  return <FeedPurchasesScreen onBack={() => router.replace("/feed")} />;
}
