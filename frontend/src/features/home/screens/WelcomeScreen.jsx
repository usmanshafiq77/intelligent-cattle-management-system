import { StyleSheet, Text, View } from 'react-native';

import { Screen } from '../../../components/ui/Screen';

export function WelcomeScreen() {
  return (
    <Screen style={styles.screen}>
      <View style={styles.card}>
        <Text style={styles.eyebrow}>INTELLIGENT CATTLE MANAGEMENT</Text>
        <Text style={styles.title}>ICMS Mobile</Text>
        <Text style={styles.description}>
          React Native foundation is ready. Authentication and domain workflows
          will be connected in the next approved substeps.
        </Text>
        <View style={styles.badge}>
          <Text style={styles.badgeText}>Step 19.1</Text>
        </View>
      </View>
    </Screen>
  );
}

const styles = StyleSheet.create({
  screen: {
    alignItems: 'center',
    justifyContent: 'center',
    padding: 24,
  },
  card: {
    width: '100%',
    maxWidth: 520,
    borderRadius: 20,
    backgroundColor: '#ffffff',
    padding: 28,
    shadowColor: '#0c2d20',
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.12,
    shadowRadius: 18,
    elevation: 5,
  },
  eyebrow: {
    color: '#39765a',
    fontSize: 12,
    fontWeight: '700',
    letterSpacing: 1.2,
  },
  title: {
    color: '#153d2c',
    fontSize: 34,
    fontWeight: '700',
    marginTop: 10,
  },
  description: {
    color: '#52625b',
    fontSize: 16,
    lineHeight: 24,
    marginTop: 12,
  },
  badge: {
    alignSelf: 'flex-start',
    backgroundColor: '#dff1e8',
    borderRadius: 999,
    marginTop: 24,
    paddingHorizontal: 14,
    paddingVertical: 7,
  },
  badgeText: {
    color: '#174d36',
    fontSize: 13,
    fontWeight: '700',
  },
});
