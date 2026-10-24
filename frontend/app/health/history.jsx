import { useRouter } from "expo-router";
import { HealthHistoryScreen } from "../../src/features/health/screens/HealthScreens";
export default function Route() { const router = useRouter(); return <HealthHistoryScreen onBack={() => router.back()} />; }
