import { Link, useRouter } from 'expo-router';
import { useEffect } from 'react';
import { Pressable, SafeAreaView, StyleSheet, Text, View } from 'react-native';

import { Button } from '@/components/ui/button';
import { Colors, Fonts, Spacing } from '@/constants/theme';
import { useAuth } from '@/context/auth-context';

export default function WelcomeScreen() {
  const router = useRouter();
  const { status, user } = useAuth();

  useEffect(() => {
    if (status === 'authenticated') router.replace(user?.role === 'vendor' ? '/vendor-home' : '/home');
  }, [router, status, user?.role]);

  if (status === 'loading') return <View style={styles.loading} />;

  return (
    <SafeAreaView style={styles.safeArea}>
      <View style={styles.content}>
        <Text style={styles.wordmark}>den<Text style={styles.dot}>.</Text></Text>
        <View style={styles.copy}>
          <Text style={styles.eyebrow}>EVENTS, GATHERED</Text>
          <Text style={styles.title}>Make room for the good stuff.</Text>
          <Text style={styles.subtitle}>Plan beautiful moments with less noise and more intention.</Text>
        </View>
        <View style={styles.actions}>
          <Button label="Create an account" onPress={() => router.push('/register')} />
          <Link href="/login" asChild>
            <Pressable style={styles.loginLink}><Text style={styles.loginText}>I already have an account</Text></Pressable>
          </Link>
        </View>
      </View>
      <Text style={styles.footer}>A calmer way to gather.</Text>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: { backgroundColor: Colors.light.background, flex: 1 },
  content: { flex: 1, justifyContent: 'space-between', padding: Spacing.four },
  wordmark: { color: Colors.light.ink, fontFamily: Fonts.serif, fontSize: 42, fontWeight: '700', letterSpacing: -3 },
  dot: { color: Colors.light.terracotta },
  copy: { gap: Spacing.three, maxWidth: 360 },
  eyebrow: { color: Colors.light.terracotta, fontFamily: Fonts.sans, fontSize: 12, fontWeight: '700', letterSpacing: 2 },
  title: { color: Colors.light.ink, fontFamily: Fonts.serif, fontSize: 48, lineHeight: 50 },
  subtitle: { color: Colors.light.muted, fontFamily: Fonts.sans, fontSize: 17, lineHeight: 26 },
  actions: { gap: Spacing.two },
  loginLink: { alignItems: 'center', minHeight: 48, justifyContent: 'center' },
  loginText: { color: Colors.light.ink, fontFamily: Fonts.sans, fontSize: 14, fontWeight: '700' },
  footer: { color: Colors.light.muted, fontFamily: Fonts.sans, fontSize: 13, padding: Spacing.four },
  loading: { backgroundColor: Colors.light.background, flex: 1 },
});
