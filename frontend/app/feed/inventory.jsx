import { useRouter } from "expo-router";
import { FeedInventoryScreen } from "../../src/features/feed/screens/FeedScreens";

export default function FeedInventoryRoute() {
  const router = useRouter();
  return <FeedInventoryScreen onBack={() => router.replace("/feed")} />;
}
