import { useRouter } from "expo-router";
import { ListingEditorScreen } from "../../src/features/marketplace/screens/MarketplaceScreens";
export default function Route(){const router=useRouter();return <ListingEditorScreen onBack={()=>router.back()} onSaved={()=>router.replace("/marketplace/my-listings")}/>;}
