import { useRouter } from "expo-router";
import { SellerDashboardScreen } from "../../src/features/marketplace/screens/MarketplaceScreens";
export default function Route(){const router=useRouter();return <SellerDashboardScreen onBack={()=>router.back()} onNavigate={href=>router.push(href)}/>;}
