import { useRouter } from "expo-router";
import { DiagnosisScreen } from "../../src/features/health/screens/HealthScreens";
export default function Route() { const router = useRouter(); return <DiagnosisScreen onBack={() => router.back()} />; }
