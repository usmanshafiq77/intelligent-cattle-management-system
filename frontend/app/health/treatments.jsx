import { useRouter } from "expo-router";
import { TreatmentScreen } from "../../src/features/health/screens/HealthScreens";
export default function Route() { const router = useRouter(); return <TreatmentScreen onBack={() => router.back()} />; }
