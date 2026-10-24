import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";

import { useAppTheme } from "../../../theme/ThemeProvider";

export function RoleNavigation({ items, activeKey = "dashboard", desktop, onNavigate }) {
  const { theme, radius, spacing, typography } = useAppTheme();
  const links = [
    { key: "dashboard", title: "Overview", href: "/dashboard" },
    ...items,
    { key: "profile", title: "Profile", href: "/profile" },
  ];
  const content = links.map((item) => {
    const selected = item.key === activeKey;
    return (
      <Pressable
        key={item.key}
        accessibilityRole="link"
        accessibilityState={{ selected }}
        accessibilityLabel={`${item.title}${item.comingSoon ? ", coming soon" : ""}`}
        onPress={() => onNavigate(item.href)}
        style={({ pressed }) => [
          styles.link,
          desktop ? styles.desktopLink : styles.mobileLink,
          {
            backgroundColor: selected ? theme.colors.primary : theme.colors.surface,
            borderColor: selected ? theme.colors.primary : theme.colors.border,
            borderRadius: radius.md,
            paddingHorizontal: spacing.md,
            opacity: pressed ? 0.76 : 1,
          },
        ]}
      >
        <Text numberOfLines={1} style={{ color: selected ? theme.colors.onPrimary : theme.colors.text, fontSize: typography.sizes.small, fontWeight: typography.weights.bold }}>
          {item.title}
        </Text>
        {item.comingSoon && desktop ? <Text style={{ color: selected ? theme.colors.onPrimary : theme.colors.textSecondary, fontSize: typography.sizes.caption }}>Coming soon</Text> : null}
      </Pressable>
    );
  });

  if (desktop) {
    return (
      <View testID="desktop-navigation" accessibilityLabel="Primary navigation" style={[styles.desktop, { backgroundColor: theme.colors.surface, borderColor: theme.colors.border, padding: spacing.md }]}>
        {content}
      </View>
    );
  }

  return (
    <View testID="mobile-navigation" style={[styles.mobileShell, { backgroundColor: theme.colors.surface, borderColor: theme.colors.border }]}>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={[styles.mobileContent, { padding: spacing.sm }]}>
        {content}
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  desktop: { width: 244, borderRightWidth: 1, gap: 8 },
  link: { minHeight: 48, borderWidth: 1, justifyContent: "center" },
  desktopLink: { width: "100%" },
  mobileLink: { minWidth: 104 },
  mobileShell: { borderTopWidth: 1 },
  mobileContent: { gap: 8 },
});
