import { useRouter } from "expo-router";
import { PaymentsScreen } from "../../src/features/finance/screens/FinanceScreens";
export default function Route(){const router=useRouter();return <PaymentsScreen onBack={()=>router.back()}/>;}
