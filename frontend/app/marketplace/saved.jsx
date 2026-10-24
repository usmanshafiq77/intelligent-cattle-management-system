import { useRouter } from "expo-router";
import { SavedListingsScreen } from "../../src/features/marketplace/screens/MarketplaceScreens";
export default function Route(){const router=useRouter();return <SavedListingsScreen onBack={()=>router.back()} onOpen={id=>router.push(`/marketplace/${id}`)}/>;}
