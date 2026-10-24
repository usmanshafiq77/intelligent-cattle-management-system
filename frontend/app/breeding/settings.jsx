import { useRouter } from "expo-router";
import { BreedingSettingsScreen } from "../../src/features/breeding/screens/BreedingScreens";
export default function Route() { const router = useRouter(); return <BreedingSettingsScreen onBack={() => router.back()} onNavigate={(route) => router.push(route)} />; }
