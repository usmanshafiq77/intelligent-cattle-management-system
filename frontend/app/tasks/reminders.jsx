import { useRouter } from "expo-router";
import { ReminderListScreen } from "../../src/features/work/screens/WorkScreens";
export default function Route(){const router=useRouter();return <ReminderListScreen onOpen={(id)=>router.push(`/tasks/${id}`)}/>;}
