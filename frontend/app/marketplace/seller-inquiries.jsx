import { useRouter } from "expo-router";
import { InquiriesScreen } from "../../src/features/marketplace/screens/MarketplaceScreens";
export default function Route(){const router=useRouter();return <InquiriesScreen seller onBack={()=>router.back()} onOpen={id=>router.push(`/marketplace/inquiry/${id}`)}/>;}
