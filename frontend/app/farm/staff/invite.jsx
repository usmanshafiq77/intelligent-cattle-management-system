import { useRouter } from "expo-router";
import { InviteStaffScreen } from "../../../src/features/staff/screens/InviteStaffScreen";
import { ROUTES } from "../../../src/navigation/routes";
export default function InviteStaffRoute() { const router = useRouter(); return <InviteStaffScreen onBack={() => router.replace(ROUTES.staff)} />; }
