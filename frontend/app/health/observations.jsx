import { useRouter } from "expo-router";
import { ObservationScreen } from "../../src/features/health/screens/HealthScreens";
export default function Route() { const router = useRouter(); return <ObservationScreen onBack={() => router.back()} />; }
