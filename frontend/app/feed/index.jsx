import { useRouter } from "expo-router";

import { FeedDashboardScreen } from "../../src/features/feed/screens/FeedScreens";

export default function FeedDashboardRoute() {
  const router = useRouter();
  return <FeedDashboardScreen onBack={() => router.replace("/dashboard")} onNavigate={(route) => router.push(route)} />;
}
