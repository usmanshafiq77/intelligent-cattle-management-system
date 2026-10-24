import { useRouter } from "expo-router";
import { MilkAnalyticsScreen } from "../../src/features/milk/screens/MilkScreens";
export default function Route() { const router = useRouter(); return <MilkAnalyticsScreen onBack={() => router.replace("/milk")} />; }
