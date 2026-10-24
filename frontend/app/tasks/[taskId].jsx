import { useLocalSearchParams,useRouter } from "expo-router";
import { TaskDetailScreen } from "../../src/features/work/screens/WorkScreens";
export default function Route(){const {taskId}=useLocalSearchParams();const router=useRouter();return <TaskDetailScreen taskId={taskId} onEdit={()=>router.push(`/tasks/${taskId}/edit`)}/>;}
