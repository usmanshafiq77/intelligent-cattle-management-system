import { useRouter } from "expo-router";
import { MilkRecordsScreen } from "../../../src/features/milk/screens/MilkScreens";
export default function Route() { const router = useRouter(); return <MilkRecordsScreen onBack={() => router.replace("/milk")} onOpen={(id) => router.push(`/milk/records/${id}`)} />; }
