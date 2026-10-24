import { useRouter } from "expo-router";
import { DailyFeedingRecordsScreen } from "../../src/features/feed/screens/FeedScreens";

export default function DailyFeedingRecordsRoute() {
  const router = useRouter();
  return <DailyFeedingRecordsScreen onBack={() => router.replace("/feed")} />;
}
