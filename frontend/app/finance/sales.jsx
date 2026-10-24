import { useRouter } from "expo-router";
import { SalesScreen } from "../../src/features/finance/screens/FinanceScreens";
export default function Route(){const router=useRouter();return <SalesScreen onBack={()=>router.back()}/>;}
