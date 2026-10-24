import { useRouter } from "expo-router";
import { MilkReportsScreen } from "../../src/features/milk/screens/MilkScreens";
export default function Route() { const router = useRouter(); return <MilkReportsScreen onBack={() => router.replace("/milk")} />; }
