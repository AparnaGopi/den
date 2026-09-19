import { Link, useRouter } from 'expo-router';
import { useEffect, useState } from 'react';
import { KeyboardAvoidingView, Platform, SafeAreaView, ScrollView, StyleSheet, Text, View } from 'react-native';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Colors, Fonts, Spacing } from '@/constants/theme';
import { useAuth } from '@/context/auth-context';

export default function LoginScreen() {
  const router = useRouter();
  const { user, status, error, login, clearError } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState('');

  useEffect(() => {
    if (status === 'authenticated') router.replace(user?.role === 'vendor' ? '/vendor-home' : '/home');
  }, [router, status, user?.role]);

  async function submit() {
    clearError();
    setFormError('');
    if (!email.trim() || !password) {
      setFormError('Enter your email and password to continue.');
      return;
    }
    setSubmitting(true);
    try {
      await login(email, password);
    } catch {
      // The provider exposes the readable API error below the form.
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <SafeAreaView style={styles.safeArea}>
      <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : undefined} style={styles.keyboard}>
        <ScrollView contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
          <Link href="/" style={styles.back}>Back to welcome</Link>
          <View style={styles.heading}><Text style={styles.eyebrow}>WELCOME BACK</Text><Text style={styles.title}>Good to see you.</Text><Text style={styles.subtitle}>Sign in to pick up where you left off.</Text></View>
          <View style={styles.form}>
            <Input label="Email" autoCapitalize="none" autoComplete="email" keyboardType="email-address" onChangeText={setEmail} value={email} />
            <Input label="Password" onChangeText={setPassword} secureTextEntry value={password} />
            {formError || error ? <Text style={styles.error}>{formError || error}</Text> : null}
            <Button label="Log in" loading={submitting} onPress={submit} />
          </View>
          <Text style={styles.switchText}>New to Den? <Link href="/register" style={styles.link}>Create an account</Link></Text>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: { backgroundColor: Colors.light.background, flex: 1 },
  keyboard: { flex: 1 },
  content: { gap: Spacing.four, padding: Spacing.four, paddingTop: Spacing.two },
  back: { color: Colors.light.muted, fontFamily: Fonts.sans, fontSize: 14 },
  heading: { gap: Spacing.two, marginTop: Spacing.five },
  eyebrow: { color: Colors.light.terracotta, fontFamily: Fonts.sans, fontSize: 12, fontWeight: '700', letterSpacing: 2 },
  title: { color: Colors.light.ink, fontFamily: Fonts.serif, fontSize: 44, lineHeight: 48 },
  subtitle: { color: Colors.light.muted, fontFamily: Fonts.sans, fontSize: 16, lineHeight: 24 },
  form: { gap: Spacing.three, marginTop: Spacing.three },
  error: { color: Colors.light.error, fontFamily: Fonts.sans, fontSize: 14, lineHeight: 20 },
  switchText: { color: Colors.light.muted, fontFamily: Fonts.sans, fontSize: 14, textAlign: 'center' },
  link: { color: Colors.light.ink, fontWeight: '700' },
});
