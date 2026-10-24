import { useRouter } from "expo-router";
import { BreedingCalendarScreen } from "../../src/features/breeding/screens/BreedingScreens";
export default function Route() { const router = useRouter(); return <BreedingCalendarScreen onBack={() => router.back()} onNavigate={(route) => router.push(route)} />; }
