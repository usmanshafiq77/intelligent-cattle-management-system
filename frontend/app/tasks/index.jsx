import { useRouter } from "expo-router";
import { TasksDashboardScreen } from "../../src/features/work/screens/WorkScreens";
export default function Route(){const router=useRouter();return <TasksDashboardScreen onNavigate={(path)=>router.push(path)}/>;}
