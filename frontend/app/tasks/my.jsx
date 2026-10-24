import { useRouter } from "expo-router";
import { MyTasksScreen } from "../../src/features/work/screens/WorkScreens";
export default function Route(){const router=useRouter();return <MyTasksScreen onOpen={(id)=>router.push(`/tasks/${id}`)}/>;}
