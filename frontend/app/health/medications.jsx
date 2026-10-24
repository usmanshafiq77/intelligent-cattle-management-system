import { useRouter } from "expo-router";
import { MedicationAdministrationScreen } from "../../src/features/health/screens/HealthScreens";
export default function Route() { const router = useRouter(); return <MedicationAdministrationScreen onBack={() => router.back()} />; }
