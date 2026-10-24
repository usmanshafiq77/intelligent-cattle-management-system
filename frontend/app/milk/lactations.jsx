import { useRouter } from "expo-router";
import { LactationRecordsScreen } from "../../src/features/milk/screens/MilkScreens";
export default function Route() { const router = useRouter(); return <LactationRecordsScreen onBack={() => router.replace("/milk")} />; }
