import { useRouter } from "expo-router";
import { VaccinationAdministrationScreen } from "../../src/features/health/screens/HealthScreens";
export default function Route() { const router = useRouter(); return <VaccinationAdministrationScreen onBack={() => router.back()} />; }
