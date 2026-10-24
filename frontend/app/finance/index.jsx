import { useRouter } from "expo-router";
import { FinanceDashboardScreen } from "../../src/features/finance/screens/FinanceScreens";
export default function Route(){const router=useRouter();return <FinanceDashboardScreen onBack={()=>router.replace("/dashboard")} onNavigate={href=>router.push(href)}/>;}
