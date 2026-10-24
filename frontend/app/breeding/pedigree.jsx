import { useRouter } from "expo-router";
import { PedigreeScreen } from "../../src/features/breeding/screens/BreedingScreens";
export default function Route() { const router = useRouter(); return <PedigreeScreen onBack={() => router.back()} onNavigate={(route) => router.push(route)} />; }
