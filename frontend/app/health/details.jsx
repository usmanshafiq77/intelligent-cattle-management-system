import { useRouter } from "expo-router";
import { HealthRecordDetailScreen } from "../../src/features/health/screens/HealthScreens";
export default function Route() { const router = useRouter(); return <HealthRecordDetailScreen onBack={() => router.back()} />; }
