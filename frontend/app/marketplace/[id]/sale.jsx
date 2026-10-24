import { useLocalSearchParams, useRouter } from "expo-router";
import { ConfirmSaleScreen } from "../../../src/features/marketplace/screens/MarketplaceScreens";
export default function Route(){const{id}=useLocalSearchParams(),router=useRouter();return <ConfirmSaleScreen listingId={id} onBack={()=>router.back()}/>;}
