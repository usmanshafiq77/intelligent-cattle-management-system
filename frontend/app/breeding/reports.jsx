import { useRouter } from "expo-router";
import { BreedingReportsScreen } from "../../src/features/breeding/screens/BreedingScreens";
export default function Route() { const router = useRouter(); return <BreedingReportsScreen onBack={() => router.back()} onNavigate={(route) => router.push(route)} />; }
