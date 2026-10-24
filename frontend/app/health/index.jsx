import { useRouter } from "expo-router";
import { HealthDashboardScreen } from "../../src/features/health/screens/HealthScreens";
export default function Route() { const router = useRouter(); return <HealthDashboardScreen onBack={() => router.replace("/dashboard")} onNavigate={(path) => router.push(path)} />; }
