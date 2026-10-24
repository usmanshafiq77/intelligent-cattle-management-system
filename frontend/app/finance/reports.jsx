import { useRouter } from "expo-router";
import { ReportsScreen } from "../../src/features/finance/screens/FinanceScreens";
export default function Route(){const router=useRouter();return <ReportsScreen onBack={()=>router.back()}/>;}
