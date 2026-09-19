import { useRouter } from 'expo-router';
import { useEffect, type PropsWithChildren } from 'react';
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Button } from '@/components/ui/button';
import { Colors, Fonts, Spacing } from '@/constants/theme';
import { useAuth } from '@/context/auth-context';

export function DiscoveryScreen({ title, children }: PropsWithChildren<{ title: string }>) {
  const router = useRouter();
  const { status, user } = useAuth();
  useEffect(() => {
    if (status === 'unauthenticated') router.replace('/');
    if (status === 'authenticated' && user?.role === 'vendor') router.replace('/vendor-home');
  }, [router, status, user?.role]);
  if (status === 'loading') return <Loading />;
  if (status !== 'authenticated' || user?.role !== 'customer') return null;
  return <SafeAreaView style={discoveryStyles.safeArea}>
    <ScrollView keyboardShouldPersistTaps="handled" contentContainerStyle={discoveryStyles.content}>
      <View style={discoveryStyles.row}>
        <Pressable accessibilityRole="button" onPress={() => router.replace('/home')}><Text style={discoveryStyles.link}>Your Den</Text></Pressable>
        <Pressable accessibilityRole="button" onPress={() => router.push('/profile')}><Text style={discoveryStyles.link}>Profile</Text></Pressable>
      </View>
      <Text style={discoveryStyles.eyebrow}>ROOM FOR A GOOD GATHERING</Text>
      <Text style={discoveryStyles.title}>{title}</Text>
      {children}
    </ScrollView>
  </SafeAreaView>;
}
export function Loading() {
  return <View style={discoveryStyles.loading}><ActivityIndicator accessibilityLabel="Loading" color={Colors.light.terracotta} /></View>;
}
export function ErrorNotice({ message, retry }: { message: string; retry?: () => void }) {
  return <View style={discoveryStyles.card}><Text accessibilityRole="alert" style={discoveryStyles.error}>{message}</Text>{retry && <Button label="Try again" variant="secondary" onPress={retry} />}</View>;
}
export function ChoiceChip({ label, selected, onPress, disabled = false }: { label: string; selected: boolean; onPress: () => void; disabled?: boolean }) {
  return <Pressable accessibilityRole="button" accessibilityState={{ selected, disabled }} disabled={disabled} onPress={onPress} style={[discoveryStyles.chip, selected && discoveryStyles.selectedChip, disabled && { opacity: 0.5 }]}>
    <Text style={[discoveryStyles.chipLabel, selected && discoveryStyles.selectedLabel]}>{label}</Text>
  </Pressable>;
}
export const discoveryStyles = StyleSheet.create({
  safeArea: { flex: 1, backgroundColor: Colors.light.background },
  content: { padding: Spacing.four, gap: Spacing.three, maxWidth: 800, width: '100%', alignSelf: 'center', paddingBottom: Spacing.six },
  row: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: Spacing.two },
  link: { color: Colors.light.terracotta, fontFamily: Fonts.sans, fontSize: 15, fontWeight: '700', paddingVertical: 8 },
  eyebrow: { color: Colors.light.terracotta, fontFamily: Fonts.sans, fontSize: 11, fontWeight: '700', letterSpacing: 1.5, marginTop: Spacing.three },
  title: { color: Colors.light.ink, fontFamily: Fonts.serif, fontSize: 36, lineHeight: 42 },
  heading: { color: Colors.light.ink, fontFamily: Fonts.serif, fontSize: 24 },
  body: { color: Colors.light.muted, fontFamily: Fonts.sans, fontSize: 15, lineHeight: 23 },
  card: { backgroundColor: Colors.light.surface, borderColor: Colors.light.line, borderWidth: 1, borderRadius: 18, padding: Spacing.three, gap: Spacing.two },
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: Spacing.two },
  chip: { paddingHorizontal: 16, paddingVertical: 12, borderRadius: 24, borderColor: Colors.light.line, borderWidth: 1, backgroundColor: Colors.light.surface },
  selectedChip: { backgroundColor: Colors.light.ink, borderColor: Colors.light.ink },
  chipLabel: { color: Colors.light.ink, fontFamily: Fonts.sans, fontSize: 14 },
  selectedLabel: { color: Colors.light.surface },
  error: { color: Colors.light.error, fontFamily: Fonts.sans, fontSize: 14, lineHeight: 21 },
  loading: { padding: Spacing.five, alignItems: 'center', justifyContent: 'center', backgroundColor: Colors.light.background },
  badge: { color: Colors.light.terracotta, fontFamily: Fonts.sans, fontSize: 12, fontWeight: '700' },
});
