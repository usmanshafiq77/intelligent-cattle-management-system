import { useRouter } from "expo-router";
import { VaccinationScheduleScreen } from "../../src/features/health/screens/HealthScreens";
export default function Route() { const router = useRouter(); return <VaccinationScheduleScreen onBack={() => router.back()} />; }
