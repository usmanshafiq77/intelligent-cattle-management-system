import { useRouter } from "expo-router";
import { VaccinationDashboardScreen } from "../../src/features/health/screens/HealthScreens";
export default function Route() { const router = useRouter(); return <VaccinationDashboardScreen onBack={() => router.back()} onNavigate={(path) => router.push(path)} />; }
