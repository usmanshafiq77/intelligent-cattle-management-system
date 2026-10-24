import { useRouter } from "expo-router";
import { VeterinaryVisitsScreen } from "../../src/features/health/screens/HealthScreens";
export default function Route() { const router = useRouter(); return <VeterinaryVisitsScreen onBack={() => router.back()} />; }
