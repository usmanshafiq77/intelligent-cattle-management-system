import { useRouter } from "expo-router";
import { SellerListingsScreen } from "../../src/features/marketplace/screens/MarketplaceScreens";
export default function Route(){const router=useRouter();return <SellerListingsScreen onBack={()=>router.back()} onEdit={id=>router.push(`/marketplace/${id}/edit`)} onSale={id=>router.push(`/marketplace/${id}/sale`)}/>;}
