import { useRouter } from "expo-router";
import { DailyMilkEntryScreen } from "../../src/features/milk/screens/MilkScreens";
export default function Route() { const router = useRouter(); return <DailyMilkEntryScreen onBack={() => router.replace("/milk")} />; }
