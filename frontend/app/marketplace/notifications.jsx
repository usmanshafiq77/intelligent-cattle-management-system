import { useRouter } from "expo-router";
import { NotificationsScreen } from "../../src/features/marketplace/screens/MarketplaceScreens";
export default function Route(){const router=useRouter();return <NotificationsScreen onBack={()=>router.back()}/>;}
