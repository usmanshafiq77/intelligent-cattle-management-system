import { useRouter } from "expo-router";
import { MilkCorrectionsScreen } from "../../src/features/milk/screens/MilkScreens";
export default function Route() { const router = useRouter(); return <MilkCorrectionsScreen onBack={() => router.replace("/milk")} />; }
