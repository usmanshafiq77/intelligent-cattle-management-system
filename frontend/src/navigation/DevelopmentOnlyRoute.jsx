import { NotFoundScreen } from "../features/navigation/screens/NotFoundScreen";

export function isDevelopmentRouteEnabled(devFlag = typeof __DEV__ !== "undefined" ? __DEV__ : false) {
  return devFlag === true;
}

export function DevelopmentOnlyRoute({ children, enabled = isDevelopmentRouteEnabled(), onReturnHome }) {
  if (!enabled) return <NotFoundScreen onReturnHome={onReturnHome} />;
  return children;
}
