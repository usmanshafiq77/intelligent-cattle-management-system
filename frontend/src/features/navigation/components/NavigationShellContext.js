import { createContext, useContext } from "react";

export const NavigationShellContext = createContext({ enabled: false, Shell: null });

export function useNavigationShell() {
  return useContext(NavigationShellContext);
}
