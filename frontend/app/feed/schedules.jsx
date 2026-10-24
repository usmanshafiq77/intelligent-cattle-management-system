import { useRouter } from "expo-router";
import { FeedingScheduleScreen } from "../../src/features/feed/screens/FeedScreens";

export default function FeedingScheduleRoute() {
  const router = useRouter();
  return <FeedingScheduleScreen onBack={() => router.replace("/feed")} />;
}
