import { useRouter } from "expo-router";
import { HealthReportsScreen } from "../../src/features/health/screens/HealthScreens";
export default function Route() { const router = useRouter(); return <HealthReportsScreen onBack={() => router.back()} />; }
