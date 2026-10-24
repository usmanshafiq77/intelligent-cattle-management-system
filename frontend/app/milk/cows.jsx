import { useRouter } from "expo-router";
import { CowMilkHistoryScreen } from "../../src/features/milk/screens/MilkScreens";
export default function Route() { const router = useRouter(); return <CowMilkHistoryScreen onBack={() => router.replace("/milk")} />; }
