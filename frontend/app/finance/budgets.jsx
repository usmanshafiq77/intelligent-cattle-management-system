import { useRouter } from "expo-router";
import { BudgetsScreen } from "../../src/features/finance/screens/FinanceScreens";
export default function Route(){const router=useRouter();return <BudgetsScreen onBack={()=>router.back()}/>;}
