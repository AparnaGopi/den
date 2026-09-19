import { Link, useRouter } from 'expo-router';
import { useEffect, useState } from 'react';
import { KeyboardAvoidingView, Platform, SafeAreaView, ScrollView, StyleSheet, Text, View } from 'react-native';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Colors, Fonts, Spacing } from '@/constants/theme';
import { useAuth } from '@/context/auth-context';

export default function RegisterScreen() {
  const router = useRouter();
  const { user, status, error, register, clearError } = useAuth();
  const [form, setForm] = useState({ email: '', firstName: '', lastName: '', password: '', confirmPassword: '' });
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState('');

  useEffect(() => {
    if (status === 'authenticated') router.replace(user?.role === 'vendor' ? '/vendor-home' : '/home');
  }, [router, status, user?.role]);

  function update(key: keyof typeof form, value: string) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  async function submit() {
    clearError();
    setFormError('');
    if (!form.email.trim() || !form.firstName.trim() || !form.lastName.trim() || !form.password || !form.confirmPassword) {
      setFormError('Complete every field to create your account.');
      return;
    }
    if (form.password.length < 8) {
      setFormError('Your password must be at least 8 characters.');
      return;
    }
    if (form.password !== form.confirmPassword) {
      setFormError('Passwords do not match.');
      return;
    }
    setSubmitting(true);
    try {
      await register({
        email: form.email,
        first_name: form.firstName.trim(),
        last_name: form.lastName.trim(),
        password: form.password,
        password_confirm: form.confirmPassword,
      });
      router.replace('/home');
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
          <View style={styles.heading}><Text style={styles.eyebrow}>JOIN DEN</Text><Text style={styles.title}>Make yourself at home.</Text><Text style={styles.subtitle}>A private place for your next gathering to take shape.</Text></View>
          <View style={styles.form}>
            <Input label="First name" autoCapitalize="words" onChangeText={(value) => update('firstName', value)} value={form.firstName} />
            <Input label="Last name" autoCapitalize="words" onChangeText={(value) => update('lastName', value)} value={form.lastName} />
            <Input label="Email" autoCapitalize="none" autoComplete="email" keyboardType="email-address" onChangeText={(value) => update('email', value)} value={form.email} />
            <Input label="Password" onChangeText={(value) => update('password', value)} secureTextEntry value={form.password} />
            <Input label="Confirm password" onChangeText={(value) => update('confirmPassword', value)} secureTextEntry value={form.confirmPassword} />
            {formError || error ? <Text style={styles.error}>{formError || error}</Text> : null}
            <Button label="Create account" loading={submitting} onPress={submit} />
          </View>
          <Text style={styles.switchText}>Already have an account? <Link href="/login" style={styles.link}>Log in</Link></Text>
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
  title: { color: Colors.light.ink, fontFamily: Fonts.serif, fontSize: 42, lineHeight: 46 },
  subtitle: { color: Colors.light.muted, fontFamily: Fonts.sans, fontSize: 16, lineHeight: 24 },
  form: { gap: Spacing.three, marginTop: Spacing.three },
  error: { color: Colors.light.error, fontFamily: Fonts.sans, fontSize: 14, lineHeight: 20 },
  switchText: { color: Colors.light.muted, fontFamily: Fonts.sans, fontSize: 14, textAlign: 'center' },
  link: { color: Colors.light.ink, fontWeight: '700' },
});
