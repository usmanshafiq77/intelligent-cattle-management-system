import { useRouter } from "expo-router";
import { ReproductiveTreatmentScreen } from "../../src/features/breeding/screens/BreedingScreens";
export default function Route() { const router = useRouter(); return <ReproductiveTreatmentScreen onBack={() => router.back()} onNavigate={(route) => router.push(route)} />; }
