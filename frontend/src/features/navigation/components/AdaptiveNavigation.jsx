import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Animated,
  BackHandler,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  useWindowDimensions,
  View,
} from "react-native";
import { LinearGradient } from "expo-linear-gradient";
import { usePathname, useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { BrandMark } from "../../../components/brand/BrandMark";
import { useAppTheme } from "../../../theme/ThemeProvider";
import { useAuth } from "../../auth/context/AuthProvider";
import { FarmSelector } from "../../farms/components/FarmSelector";
import { useFarm } from "../../farms/context/FarmProvider";
import { appNavigationItems, platformNavigationItems } from "../../permissions/navigationConfig";
import { NavigationShellContext, useNavigationShell } from "./NavigationShellContext";

const PUBLIC_PATHS = ["/", "/auth/login", "/auth/signup", "/auth/forgot-password", "/auth/verify-email", "/reset-password", "/dev/design-system"];
const MOBILE_DRAWER_COLORS = Object.freeze({
  panel: "#0A1219",
  panelRaised: "#121E28",
  text: "#F4F7FA",
  muted: "#A8B3BD",
  border: "rgba(255,255,255,0.11)",
  active: "rgba(255,255,255,0.12)",
  icon: "#D7E0E7",
  danger: "#FF7C88",
  dangerSurface: "rgba(255,82,99,0.12)",
});
const DRAWER_ICONS = Object.freeze({
  dashboard: "⌂",
  profile: "●",
  farm: "◇",
  staff: "♙",
  cattle: "♉",
  health: "+",
  milk: "◉",
  feed: "♨",
  breeding: "♥",
  finance: "$",
  marketplace: "▦",
  tasks: "✓",
  vaccinations: "+",
  "marketplace-moderation": "◆",
  "platform-backups": "B",
});

function userInitials(name) {
  return String(name || "ICMS").split(/\s+/).filter(Boolean).slice(0, 2).map((part) => part[0]).join("").toUpperCase() || "IC";
}

function routeTitle(pathname) {
  if (pathname === "/dashboard") return "Dashboard";
  if (pathname.startsWith("/vaccinations")) return "Vaccinations";
  if (pathname.startsWith("/health")) return "Health & Veterinary";
  if (pathname.startsWith("/cattle")) return "Cattle Management";
  if (pathname.startsWith("/feed")) return "Feed & Nutrition";
  if (pathname.startsWith("/breeding")) return "Breeding & Genetics";
  if (pathname.startsWith("/finance")) return "Finance & Resources";
  if (pathname.startsWith("/marketplace")) return "Marketplace";
  if (pathname.startsWith("/tasks") || pathname.startsWith("/notifications")) return "Tasks & Notifications";
  if (pathname.startsWith("/farm/staff")) return "Staff Management";
  if (pathname.startsWith("/farm")) return "Farm Management";
  if (pathname === "/profile") return "Profile";
  if (pathname.startsWith("/settings")) return "Settings";
  if (pathname.startsWith("/admin/backups")) return "Backup & Recovery";
  if (pathname.startsWith("/invitations")) return "Farm Invitation";
  return "ICMS";
}

export function AdaptiveNavigationProvider({ children }) {
  const auth = useAuth();
  const farm = useFarm();
  const router = useRouter();
  const pathname = usePathname() || "/";
  const { width } = useWindowDimensions();
  const { layout } = useAppTheme();
  const [drawerOpen, setDrawerOpen] = useState(false);
  const desktop = width >= layout.breakpoints.desktop;
  const enabled = auth.status === "authenticated" && !PUBLIC_PATHS.includes(pathname);

  useEffect(() => { if (desktop || !enabled) setDrawerOpen(false); }, [desktop, enabled, pathname]);
  useEffect(() => {
    if (!drawerOpen || Platform.OS === "web") return undefined;
    const subscription = BackHandler.addEventListener("hardwareBackPress", () => { setDrawerOpen(false); return true; });
    return () => subscription.remove();
  }, [drawerOpen]);

  const navigate = useCallback((href) => { setDrawerOpen(false); router.push(href); }, [router]);
  const value = useMemo(() => ({
    enabled,
    Shell: AdaptiveAppShell,
    desktop,
    drawerOpen,
    openDrawer: () => setDrawerOpen(true),
    closeDrawer: () => setDrawerOpen(false),
    navigate,
    pathname,
    title: routeTitle(pathname),
    auth,
    farm,
  }), [auth, desktop, drawerOpen, enabled, farm, navigate, pathname]);

  return <NavigationShellContext.Provider value={value}>{children}</NavigationShellContext.Provider>;
}

function DrawerItem({ item, current, onPress, mobile = false }) {
  const { theme, radius, spacing, typography } = useAppTheme();
  const selected = item.href === "/dashboard" ? current === item.href : current === item.href || current.startsWith(`${item.href}/`);
  const foreground = mobile ? (selected ? MOBILE_DRAWER_COLORS.text : MOBILE_DRAWER_COLORS.muted) : (selected ? theme.colors.onPrimary : theme.colors.text);
  return (
    <Pressable
      accessibilityRole="link"
      accessibilityState={{ selected }}
      accessibilityLabel={item.title}
      onPress={onPress}
      style={({ pressed }) => [
        styles.drawerItem,
        mobile && styles.mobileDrawerItem,
        {
          minHeight: 48,
          borderRadius: mobile ? 12 : radius.md,
          paddingHorizontal: spacing.md,
          backgroundColor: selected ? (mobile ? MOBILE_DRAWER_COLORS.active : theme.colors.primary) : "transparent",
          opacity: pressed ? 0.72 : 1,
        },
        mobile && selected ? { borderLeftColor: theme.colors.secondary } : null,
      ]}
    >
      {mobile ? <View accessibilityElementsHidden importantForAccessibility="no-hide-descendants" style={[styles.mobileMenuIcon, { borderColor: selected ? theme.colors.secondary : MOBILE_DRAWER_COLORS.border, backgroundColor: selected ? "rgba(255,255,255,0.08)" : "transparent" }]}><Text style={{ color: selected ? theme.colors.secondary : MOBILE_DRAWER_COLORS.icon, fontSize: 16, fontWeight: "700" }}>{DRAWER_ICONS[item.key] || "•"}</Text></View> : null}
      <Text style={{ color: foreground, fontSize: typography.sizes.small, fontWeight: selected ? typography.weights.bold : typography.weights.medium, flexShrink: 1 }}>{item.title}</Text>
    </Pressable>
  );
}

function MobileDrawerHeader({ user, farmName, onClose, topInset }) {
  const { theme, spacing, typography } = useAppTheme();
  return (
    <View testID="mobile-drawer-profile" style={[styles.mobileDrawerHero, { paddingTop: Math.max(topInset, spacing.md) }]}>
      <LinearGradient colors={[theme.colors.primaryDark, "#1A3443", MOBILE_DRAWER_COLORS.panel]} start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }} style={StyleSheet.absoluteFillObject} />
      <View style={styles.heroGlowLarge} />
      <View style={styles.heroGlowSmall} />
      <Pressable testID="drawer-close" accessibilityRole="button" accessibilityLabel="Close navigation menu" onPress={onClose} style={styles.mobileCloseButton}><Text style={{ color: MOBILE_DRAWER_COLORS.text, fontSize: 26, lineHeight: 28 }}>{String.fromCharCode(215)}</Text></Pressable>
      <View style={styles.mobileProfileRow}>
        <LinearGradient colors={[theme.colors.secondary, theme.colors.primary]} style={styles.mobileAvatar}><Text style={{ color: theme.colors.onPrimary, fontSize: typography.sizes.subtitle, fontWeight: typography.weights.extrabold }}>{userInitials(user?.full_name)}</Text></LinearGradient>
        <View style={styles.mobileProfileText}>
          <Text numberOfLines={1} style={{ color: MOBILE_DRAWER_COLORS.text, fontSize: typography.sizes.subtitle, fontWeight: typography.weights.bold }}>{user?.full_name || "ICMS User"}</Text>
          <Text numberOfLines={1} style={{ color: MOBILE_DRAWER_COLORS.muted, fontSize: typography.sizes.caption, marginTop: 2 }}>{user?.email || "Authenticated account"}</Text>
          {farmName ? <Text numberOfLines={1} style={{ color: theme.colors.secondary, fontSize: typography.sizes.caption, marginTop: 4 }}>{farmName}</Text> : null}
        </View>
      </View>
    </View>
  );
}

function DrawerContent({ onNavigate, onClose, desktop }) {
  const shell = useNavigationShell();
  const { theme, spacing, typography } = useAppTheme();
  const insets = useSafeAreaInsets();
  const items = [
    { key: "dashboard", title: "Dashboard", href: "/dashboard" },
    { key: "profile", title: "Profile & Security", href: "/profile" },
    ...appNavigationItems(shell.farm.can),
    ...platformNavigationItems(shell.auth.user).filter((item) => !item.comingSoon),
  ];
  const drawerBackground = desktop ? theme.colors.surface : MOBILE_DRAWER_COLORS.panel;

  return (
    <View testID="navigation-drawer-content" style={[styles.drawer, desktop ? styles.desktopDrawer : styles.mobileDrawerContent, { backgroundColor: drawerBackground, borderColor: desktop ? theme.colors.border : MOBILE_DRAWER_COLORS.border, paddingTop: desktop ? spacing.lg : 0 }]}>
      {desktop ? <View style={[styles.drawerHeading, { paddingHorizontal: spacing.lg }]}><BrandMark size={38} showWordmark /></View> : <MobileDrawerHeader user={shell.auth.user} farmName={shell.farm.activeFarm?.name} onClose={onClose} topInset={0} />}
      <ScrollView testID="navigation-drawer-scroll" style={styles.drawerScroll} contentContainerStyle={[styles.drawerScrollContent, { padding: spacing.md, paddingBottom: spacing.lg }]} showsVerticalScrollIndicator indicatorStyle={desktop ? "default" : "white"} nestedScrollEnabled keyboardShouldPersistTaps="handled" contentInsetAdjustmentBehavior="never">
        {shell.farm.farms?.length ? <View style={[styles.farmSwitchSection, !desktop && styles.mobileFarmSwitchSection]}><Text numberOfLines={1} style={{ color: desktop ? theme.colors.textSecondary : MOBILE_DRAWER_COLORS.muted, fontSize: typography.sizes.caption, marginBottom: spacing.sm }}>Active farm</Text><FarmSelector farms={shell.farm.farms} activeFarmId={shell.farm.activeFarm?.id} disabled={shell.farm.isLoading} onSelect={(id) => { void shell.farm.selectFarm(id); if (!desktop) onClose(); }} /></View> : null}
        <View testID="navigation-drawer-items" style={{ gap: spacing.xs }}>{items.map((item) => <DrawerItem key={item.key} item={item} current={shell.pathname} mobile={!desktop} onPress={() => onNavigate(item.href)} />)}</View>
        <Pressable accessibilityRole="button" accessibilityLabel="Log out" onPress={() => { onClose(); void shell.auth.logout().catch(() => {}); }} style={({ pressed }) => [styles.drawerItem, !desktop && styles.mobileLogout, { minHeight: 48, paddingHorizontal: spacing.md, opacity: pressed ? 0.72 : 1 }]}>
          {!desktop ? <View accessibilityElementsHidden importantForAccessibility="no-hide-descendants" style={[styles.mobileMenuIcon, { borderColor: "rgba(255,124,136,0.35)" }]}><Text style={{ color: MOBILE_DRAWER_COLORS.danger, fontSize: 17, fontWeight: "700" }}>↪</Text></View> : null}
          <Text style={{ color: desktop ? theme.colors.error : MOBILE_DRAWER_COLORS.danger, fontWeight: typography.weights.bold }}>Log out</Text>
        </Pressable>
      </ScrollView>
    </View>
  );
}

export function AdaptiveAppShell({ children }) {
  const shell = useNavigationShell();
  const insets = useSafeAreaInsets();
  const { height: windowHeight } = useWindowDimensions();
  const { theme, spacing, typography } = useAppTheme();
  const translate = useRef(new Animated.Value(-320)).current;
  const [shellHeight, setShellHeight] = useState(0);
  const boundedShellHeight = shellHeight > 0 ? Math.min(shellHeight, windowHeight) : windowHeight;
  const drawerViewportTop = Math.min(insets.top, boundedShellHeight);
  const drawerViewportHeight = Math.max(0, boundedShellHeight - drawerViewportTop - insets.bottom);

  useEffect(() => { Animated.timing(translate, { toValue: shell.drawerOpen ? 0 : -320, duration: 180, useNativeDriver: Platform.OS !== "web" }).start(); }, [shell.drawerOpen, translate]);
  if (!shell.enabled) return children;

  return (
    <View testID="adaptive-app-shell" onLayout={(event) => { const nextHeight = event.nativeEvent.layout.height; if (nextHeight > 0 && nextHeight !== shellHeight) setShellHeight(nextHeight); }} style={[styles.shell, { backgroundColor: theme.colors.background }]}>
      <View testID="safe-area-header" style={[styles.header, { backgroundColor: theme.colors.primaryDark, paddingTop: Math.max(insets.top, spacing.sm), paddingHorizontal: spacing.md, paddingBottom: spacing.sm }]}>
        {!shell.desktop ? <Pressable testID="hamburger-button" accessibilityRole="button" accessibilityLabel="Open navigation menu" onPress={shell.openDrawer} style={[styles.iconButton, { borderColor: theme.colors.onPrimary }]}><View style={styles.hamburger}><View style={[styles.hamburgerLine, { backgroundColor: theme.colors.onPrimary }]} /><View style={[styles.hamburgerLine, { backgroundColor: theme.colors.onPrimary }]} /><View style={[styles.hamburgerLine, { backgroundColor: theme.colors.onPrimary }]} /></View></Pressable> : <BrandMark size={36} />}
        <View style={styles.headerTitle}><Text numberOfLines={1} accessibilityRole="header" style={{ color: theme.colors.onPrimary, fontSize: typography.sizes.subtitle, fontWeight: typography.weights.bold }}>{shell.title}</Text>{shell.farm.activeFarm?.name ? <Text numberOfLines={1} style={{ color: theme.colors.onPrimary, opacity: 0.82, fontSize: typography.sizes.caption }}>{shell.farm.activeFarm.name}</Text> : null}</View>
        <Pressable accessibilityRole="button" accessibilityLabel="Open profile" onPress={() => shell.navigate("/profile")} style={[styles.profileButton, { borderColor: theme.colors.onPrimary }]}><Text style={{ color: theme.colors.onPrimary, fontWeight: typography.weights.bold }}>{shell.auth.user?.full_name?.trim()?.[0]?.toUpperCase() || "U"}</Text></Pressable>
      </View>
      <View style={styles.body}>{shell.desktop ? <DrawerContent desktop onNavigate={shell.navigate} onClose={shell.closeDrawer} /> : null}<View testID="app-shell-content" style={[styles.content, { paddingBottom: insets.bottom }]}>{children}</View></View>
      {!shell.desktop && shell.drawerOpen ? <View testID="mobile-drawer-overlay" pointerEvents="box-none" style={[styles.overlayLayer, { top: drawerViewportTop, height: drawerViewportHeight }]}><Pressable testID="drawer-backdrop" accessibilityLabel="Close navigation menu" onPress={shell.closeDrawer} style={styles.backdrop} /><Animated.View testID="mobile-navigation-drawer" style={[styles.mobileDrawer, { height: drawerViewportHeight, maxHeight: drawerViewportHeight, backgroundColor: MOBILE_DRAWER_COLORS.panel, transform: [{ translateX: translate }] }]}><DrawerContent onNavigate={shell.navigate} onClose={shell.closeDrawer} /></Animated.View></View> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  shell: { flex: 1, minWidth: 0 },
  header: { minHeight: 60, flexDirection: "row", alignItems: "center", gap: 12 },
  headerTitle: { flex: 1, minWidth: 0 },
  body: { flex: 1, flexDirection: "row", minHeight: 0 },
  content: { flex: 1, minWidth: 0, minHeight: 0 },
  drawer: { flex: 1, minHeight: 0, borderRightWidth: 1 },
  desktopDrawer: { flex: 0, width: 280, maxWidth: "86%" },
  mobileDrawerContent: { width: "100%", maxWidth: "100%" },
  mobileDrawer: { width: 300, maxWidth: "86%", minHeight: 0, overflow: "hidden", zIndex: 1, elevation: 31, borderTopRightRadius: 24, borderBottomRightRadius: 24 },
  drawerHeading: { minHeight: 52, flexShrink: 0, flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: 12 },
  drawerItem: { justifyContent: "center" },
  mobileDrawerItem: { flexDirection: "row", alignItems: "center", gap: 12, borderLeftWidth: 3, borderLeftColor: "transparent" },
  mobileMenuIcon: { width: 28, height: 28, borderWidth: 1, borderRadius: 9, alignItems: "center", justifyContent: "center" },
  mobileDrawerHero: { minHeight: 154, paddingHorizontal: 18, paddingBottom: 18, justifyContent: "flex-end", overflow: "hidden", borderBottomWidth: 1, borderBottomColor: MOBILE_DRAWER_COLORS.border },
  mobileCloseButton: { position: "absolute", right: 10, top: 10, width: 48, height: 48, alignItems: "center", justifyContent: "center", zIndex: 2 },
  mobileProfileRow: { flexDirection: "row", alignItems: "center", gap: 12, paddingRight: 34 },
  mobileAvatar: { width: 54, height: 54, borderRadius: 27, alignItems: "center", justifyContent: "center", borderWidth: 2, borderColor: "rgba(255,255,255,0.5)" },
  mobileProfileText: { flex: 1, minWidth: 0 },
  heroGlowLarge: { position: "absolute", width: 160, height: 160, borderRadius: 80, right: -54, top: -78, backgroundColor: "rgba(255,255,255,0.08)" },
  heroGlowSmall: { position: "absolute", width: 74, height: 74, borderRadius: 37, left: 78, top: -26, backgroundColor: "rgba(255,255,255,0.06)" },
  farmSwitchSection: { paddingHorizontal: 4, marginBottom: 12 },
  mobileFarmSwitchSection: { backgroundColor: MOBILE_DRAWER_COLORS.panelRaised, borderColor: MOBILE_DRAWER_COLORS.border, borderWidth: 1, borderRadius: 14, padding: 10 },
  mobileLogout: { marginTop: "auto", flexDirection: "row", alignItems: "center", gap: 12, borderRadius: 12, backgroundColor: MOBILE_DRAWER_COLORS.dangerSurface },
  drawerScroll: { flex: 1, minHeight: 0 },
  drawerScrollContent: { flexGrow: 1 },
  iconButton: { width: 48, height: 48, borderWidth: 1, borderRadius: 14, alignItems: "center", justifyContent: "center" },
  hamburger: { width: 22, gap: 4 },
  hamburgerLine: { height: 2, width: "100%", borderRadius: 2 },
  profileButton: { width: 44, height: 44, borderRadius: 22, borderWidth: 1, alignItems: "center", justifyContent: "center" },
  backdrop: { ...StyleSheet.absoluteFillObject, zIndex: 0, backgroundColor: "rgba(2,6,10,0.70)" },
  overlayLayer: { position: "absolute", left: 0, right: 0, zIndex: 1000, elevation: 30, flexDirection: "row", overflow: "hidden" },
});
