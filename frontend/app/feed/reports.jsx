import { useRouter } from "expo-router";
import { FeedReportsScreen } from "../../src/features/feed/screens/FeedScreens";

export default function FeedReportsRoute() {
  const router = useRouter();
  return <FeedReportsScreen onBack={() => router.replace("/feed")} />;
}
