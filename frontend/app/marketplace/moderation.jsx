import { useRouter } from "expo-router";
import { ModerationScreen } from "../../src/features/marketplace/screens/MarketplaceScreens";
export default function Route(){const router=useRouter();return <ModerationScreen onBack={()=>router.back()}/>;}
