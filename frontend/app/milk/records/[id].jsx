import { useLocalSearchParams, useRouter } from "expo-router";
import { MilkRecordDetailsScreen } from "../../../src/features/milk/screens/MilkScreens";
export default function Route() { const router = useRouter(); const { id } = useLocalSearchParams(); return <MilkRecordDetailsScreen sessionId={Array.isArray(id) ? id[0] : id} onBack={() => router.replace("/milk/records")} />; }
