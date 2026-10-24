import { useRouter } from "expo-router";
import { HealthAuditScreen } from "../../src/features/health/screens/HealthScreens";
export default function Route() { const router = useRouter(); return <HealthAuditScreen onBack={() => router.back()} />; }
