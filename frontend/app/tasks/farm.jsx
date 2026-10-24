import { useRouter } from "expo-router";
import { FarmTasksScreen } from "../../src/features/work/screens/WorkScreens";
export default function Route(){const router=useRouter();return <FarmTasksScreen onOpen={(id)=>router.push(`/tasks/${id}`)}/>;}
