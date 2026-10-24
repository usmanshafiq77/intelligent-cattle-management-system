import { useRouter } from "expo-router";
import { CreateTaskScreen } from "../../src/features/work/screens/WorkScreens";
export default function Route(){const router=useRouter();return <CreateTaskScreen onDone={(id)=>router.replace(`/tasks/${id}`)}/>;}
