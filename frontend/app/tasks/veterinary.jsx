import { useRouter } from "expo-router";
import { VeterinaryTasksScreen } from "../../src/features/work/screens/WorkScreens";
export default function Route(){const router=useRouter();return <VeterinaryTasksScreen onOpen={(id)=>router.push(`/tasks/${id}`)}/>;}
