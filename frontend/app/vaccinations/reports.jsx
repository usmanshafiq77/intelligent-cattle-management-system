import { useRouter } from "expo-router";
import { VaccinationReportsScreen } from "../../src/features/health/screens/HealthScreens";
export default function Route() { const router = useRouter(); return <VaccinationReportsScreen onBack={() => router.back()} />; }
