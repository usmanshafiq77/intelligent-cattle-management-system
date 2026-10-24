import { useRouter } from "expo-router";
import { VaccinationListScreen } from "../../src/features/health/screens/HealthScreens";
export default function Route() { const router = useRouter(); return <VaccinationListScreen mode="history" onBack={() => router.back()} />; }
