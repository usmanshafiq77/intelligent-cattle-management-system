import { useLocalSearchParams, useRouter } from "expo-router";
import { ReportListingScreen } from "../../../src/features/marketplace/screens/MarketplaceScreens";
export default function Route(){const{id}=useLocalSearchParams(),router=useRouter();return <ReportListingScreen listingId={id} onBack={()=>router.back()}/>;}
