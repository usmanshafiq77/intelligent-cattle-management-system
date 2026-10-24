import { useRouter } from "expo-router";

import { DashboardScreen } from "../src/features/navigation/screens/DashboardScreen";

export default function DashboardRoute() {
  const router = useRouter();
  return <DashboardScreen onNavigate={(href) => router.push(href)} />;
}
