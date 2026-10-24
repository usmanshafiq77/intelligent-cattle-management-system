import { useRouter } from "expo-router";
import { HeatCycleScreen } from "../../src/features/breeding/screens/BreedingScreens";
export default function Route() { const router = useRouter(); return <HeatCycleScreen onBack={() => router.back()} onNavigate={(route) => router.push(route)} />; }
