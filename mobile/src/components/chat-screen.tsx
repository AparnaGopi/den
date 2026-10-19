import { useRouter } from 'expo-router';
import { useEffect, type PropsWithChildren } from 'react';
import { ScrollView, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Button } from '@/components/ui/button';
import { Loading, discoveryStyles as s } from '@/components/discovery-ui';
import { useAuth } from '@/context/auth-context';

export function ChatScreen({ title, children }: PropsWithChildren<{ title: string }>) {
  const router = useRouter();
  const { user, status } = useAuth();
  useEffect(() => { if (status === 'unauthenticated') router.replace('/'); }, [router, status]);
  if (status === 'loading') return <Loading />;
  if (status !== 'authenticated') return null;
  return <SafeAreaView style={s.safeArea}><ScrollView keyboardShouldPersistTaps="handled" contentContainerStyle={s.content}>
    <View style={s.row}><Button label="Your Den" variant="secondary" onPress={() => router.replace(user?.role === 'vendor' ? '/vendor-home' : '/home')} /><Button label="Messages" variant="secondary" onPress={() => router.push('/messages')} /></View>
    <Text style={s.title}>{title}</Text>{children}
  </ScrollView></SafeAreaView>;
}
