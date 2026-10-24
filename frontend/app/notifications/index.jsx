import { useRouter } from "expo-router";
import { NotificationInboxScreen } from "../../src/features/work/screens/WorkScreens";
export default function Route(){const router=useRouter();return <NotificationInboxScreen onOpen={(id)=>router.push(`/notifications/${id}`)}/>;}
