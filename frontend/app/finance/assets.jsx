import { useRouter } from "expo-router";
import { AssetsScreen } from "../../src/features/finance/screens/FinanceScreens";
export default function Route(){const router=useRouter();return <AssetsScreen onBack={()=>router.back()}/>;}
