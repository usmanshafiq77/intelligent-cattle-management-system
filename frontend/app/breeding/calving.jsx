import { useRouter } from "expo-router";
import { CalvingManagementScreen } from "../../src/features/breeding/screens/BreedingScreens";
export default function Route() { const router = useRouter(); return <CalvingManagementScreen onBack={() => router.back()} onNavigate={(route) => router.push(route)} />; }
