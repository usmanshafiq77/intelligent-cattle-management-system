import { StyleSheet } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

export function Screen({ children, style }) {
  return <SafeAreaView style={[styles.screen, style]}>{children}</SafeAreaView>;
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: '#f4f7f5',
  },
});
