import { KeyboardAvoidingView, Platform, StyleSheet } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useNavigationShell } from '../../features/navigation/components/NavigationShellContext';

export function Screen({ children, style, safeEdges = ["top", "right", "bottom", "left"], avoidKeyboard = true }) {
  const shell = useNavigationShell();
  const content = avoidKeyboard ? <KeyboardAvoidingView style={styles.screen} behavior={Platform.OS === "ios" ? "padding" : undefined}>{children}</KeyboardAvoidingView> : children;
  if (shell.enabled && shell.Shell) { const Shell = shell.Shell; return <Shell><SafeAreaView edges={[]} style={[styles.screen, style]}>{content}</SafeAreaView></Shell>; }
  return <SafeAreaView edges={safeEdges} style={[styles.screen, style]}>{content}</SafeAreaView>;
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: '#f4f7f5',
  },
});
