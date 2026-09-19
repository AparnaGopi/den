import { useRouter } from 'expo-router';
import { useEffect } from 'react';
import { ActivityIndicator, Pressable, SafeAreaView, StyleSheet, Text, View } from 'react-native';

import { Button } from '@/components/ui/button';
import { Colors, Fonts, Spacing } from '@/constants/theme';
import { useAuth } from '@/context/auth-context';

export default function ProfileScreen() {
  const router = useRouter();
  const { user, status, logout } = useAuth();

  useEffect(() => {
    if (status === 'unauthenticated') router.replace('/');
  }, [router, status]);

  if (status === 'loading') return <View style={styles.loading}><ActivityIndicator color={Colors.light.terracotta} /></View>;
  if (status !== 'authenticated' || !user) return null;

  async function signOut() {
    await logout();
    router.replace('/');
  }

  return (
    <SafeAreaView style={styles.safeArea}>
      <View style={styles.content}>
        <Pressable onPress={() => router.replace('/home')}><Text style={styles.back}>Back to home</Text></Pressable>
        <Text style={styles.title}>Your profile</Text>
        <View style={styles.details}>
          <Detail label="First name" value={user.first_name} />
          <Detail label="Last name" value={user.last_name} />
          <Detail label="Email" value={user.email} />
          <Detail label="Account" value="Customer" />
        </View>
        <View style={styles.footer}><Button label="Log out" variant="secondary" onPress={signOut} /></View>
      </View>
    </SafeAreaView>
  );
}

function Detail({ label, value }: { label: string; value: string }) {
  return <View style={styles.detail}><Text style={styles.label}>{label}</Text><Text style={styles.value}>{value}</Text></View>;
}

const styles = StyleSheet.create({
  safeArea: { backgroundColor: Colors.light.background, flex: 1 },
  content: { flex: 1, gap: Spacing.four, padding: Spacing.four },
  back: { color: Colors.light.muted, fontFamily: Fonts.sans, fontSize: 14 },
  title: { color: Colors.light.ink, fontFamily: Fonts.serif, fontSize: 46, lineHeight: 50, marginTop: Spacing.five },
  details: { backgroundColor: Colors.light.surface, borderColor: Colors.light.line, borderRadius: 16, borderWidth: 1, marginTop: Spacing.two, paddingHorizontal: Spacing.three },
  detail: { borderBottomColor: Colors.light.line, borderBottomWidth: 1, gap: Spacing.one, paddingVertical: Spacing.three },
  label: { color: Colors.light.muted, fontFamily: Fonts.sans, fontSize: 12, fontWeight: '700', letterSpacing: 1, textTransform: 'uppercase' },
  value: { color: Colors.light.ink, fontFamily: Fonts.sans, fontSize: 16 },
  footer: { marginTop: 'auto' },
  loading: { alignItems: 'center', backgroundColor: Colors.light.background, flex: 1, justifyContent: 'center' },
});
