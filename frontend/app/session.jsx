import { Redirect } from "expo-router";
import { ROUTES } from "../src/navigation/routes";

export default function SessionRoute() {
  return <Redirect href={ROUTES.dashboard} />;
}
