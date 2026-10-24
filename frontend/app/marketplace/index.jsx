import { useRouter } from "expo-router";
import { MarketplaceHomeScreen } from "../../src/features/marketplace/screens/MarketplaceScreens";
export default function Route(){const router=useRouter();return <MarketplaceHomeScreen onBack={()=>router.replace("/dashboard")} onNavigate={href=>router.push(href)} onOpen={id=>router.push(`/marketplace/${id}`)}/>;}
