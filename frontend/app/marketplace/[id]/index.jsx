import { useLocalSearchParams, useRouter } from "expo-router";
import { ListingDetailScreen } from "../../../src/features/marketplace/screens/MarketplaceScreens";
export default function Route(){const{id}=useLocalSearchParams(),router=useRouter();return <ListingDetailScreen listingId={id} onBack={()=>router.back()} onInquiry={inquiryId=>router.push(`/marketplace/inquiry/${inquiryId}`)} onReport={()=>router.push(`/marketplace/${id}/report`)}/>;}
