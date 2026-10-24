import { useRouter } from "expo-router";
import { PregnancyTrackingScreen } from "../../src/features/breeding/screens/BreedingScreens";
export default function Route() { const router = useRouter(); return <PregnancyTrackingScreen onBack={() => router.back()} onNavigate={(route) => router.push(route)} />; }
