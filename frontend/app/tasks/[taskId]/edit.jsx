import { useLocalSearchParams,useRouter } from "expo-router";
import { EditTaskScreen } from "../../../src/features/work/screens/WorkScreens";
export default function Route(){const {taskId}=useLocalSearchParams();const router=useRouter();return <EditTaskScreen taskId={taskId} onDone={(id)=>router.replace(`/tasks/${id}`)}/>;}
