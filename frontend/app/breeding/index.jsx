import { useRouter } from "expo-router";
import { BreedingDashboardScreen } from "../../src/features/breeding/screens/BreedingScreens";
export default function Route() { const router = useRouter(); return <BreedingDashboardScreen onBack={() => router.back()} onNavigate={(route) => router.push(route)} />; }
