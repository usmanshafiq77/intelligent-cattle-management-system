import { useLocalSearchParams, useRouter } from "expo-router";
import { ListingEditorScreen } from "../../../src/features/marketplace/screens/MarketplaceScreens";
export default function Route(){const{id}=useLocalSearchParams(),router=useRouter();return <ListingEditorScreen listingId={id} onBack={()=>router.back()} onSaved={()=>router.replace("/marketplace/my-listings")}/>;}
