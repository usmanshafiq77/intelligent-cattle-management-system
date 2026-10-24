import { useRouter } from "expo-router";
import { BreedingEventsScreen } from "../../src/features/breeding/screens/BreedingScreens";
export default function Route() { const router = useRouter(); return <BreedingEventsScreen onBack={() => router.back()} onNavigate={(route) => router.push(route)} />; }
