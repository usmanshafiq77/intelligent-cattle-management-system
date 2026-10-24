import { useRouter } from "expo-router";
import { StaffScreen } from "../../src/features/staff/screens/StaffScreen";
import { ROUTES } from "../../src/navigation/routes";
export default function StaffRoute() { const router = useRouter(); return <StaffScreen onInvite={() => router.push(ROUTES.inviteStaff)} />; }
