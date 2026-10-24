import { useRouter } from "expo-router";

import { ProfileScreen } from "../src/features/auth/screens/ProfileScreen";
import { ROUTES } from "../src/navigation/routes";

export default function ProfileRoute() {
  const router = useRouter();
  return <ProfileScreen onVerify={() => router.push(ROUTES.verifyEmail)} />;
}
