import { useRouter } from "expo-router";
import { MilkAvailabilityScreen } from "../../src/features/milk/screens/MilkScreens";
export default function Route() { const router = useRouter(); return <MilkAvailabilityScreen onBack={() => router.replace("/milk")} />; }
