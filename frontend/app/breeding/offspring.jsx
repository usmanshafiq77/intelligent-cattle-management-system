import { useRouter } from "expo-router";
import { OffspringRegistrationScreen } from "../../src/features/breeding/screens/BreedingScreens";
export default function Route() { const router = useRouter(); return <OffspringRegistrationScreen onBack={() => router.back()} onNavigate={(route) => router.push(route)} />; }
