import { useLocalSearchParams } from "expo-router";
import { NotificationDetailScreen } from "../../src/features/work/screens/WorkScreens";
export default function Route(){const {notificationId}=useLocalSearchParams();return <NotificationDetailScreen notificationId={notificationId}/>;}
