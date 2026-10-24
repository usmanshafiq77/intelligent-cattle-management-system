import { useRouter } from "expo-router";
import { MarketplaceReportsScreen } from "../../src/features/marketplace/screens/MarketplaceScreens";
export default function Route(){const router=useRouter();return <MarketplaceReportsScreen onBack={()=>router.back()}/>;}
