import { useLocalSearchParams, useRouter } from "expo-router";
import { InquiryThreadScreen } from "../../../src/features/marketplace/screens/MarketplaceScreens";
export default function Route(){const{id}=useLocalSearchParams(),router=useRouter();return <InquiryThreadScreen inquiryId={id} onBack={()=>router.back()}/>;}
