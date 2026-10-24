import { useRouter } from "expo-router";
import { LedgerScreen } from "../../src/features/finance/screens/FinanceScreens";
export default function Route(){const router=useRouter();return <LedgerScreen kind="expense" onBack={()=>router.back()}/>;}
