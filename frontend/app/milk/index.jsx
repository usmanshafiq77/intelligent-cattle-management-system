import { useRouter } from "expo-router";
import { MilkDashboardScreen } from "../../src/features/milk/screens/MilkScreens";
export default function Route() { const router = useRouter(); return <MilkDashboardScreen onBack={() => router.replace("/dashboard")} onNavigate={(href) => router.push(href)} />; }
