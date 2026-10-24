import { useRouter } from "expo-router";
import { VaccinationListScreen } from "../../src/features/health/screens/HealthScreens";
export default function Route() { const router = useRouter(); return <VaccinationListScreen mode="overdue" onBack={() => router.back()} />; }
