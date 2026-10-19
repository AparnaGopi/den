import { useFocusEffect, useRouter } from 'expo-router';
import { useCallback, useState } from 'react';
import { Text } from 'react-native';
import { ChatScreen } from '@/components/chat-screen';
import { ErrorNotice, Loading, discoveryStyles as s } from '@/components/discovery-ui';
import { Button } from '@/components/ui/button';
import { useAuth } from '@/context/auth-context';
import type { ChatPlan } from '@/types/chat';
import { requestError } from '@/types/events';

export default function ChatPlanScreen() {
  const router = useRouter();
  const { user, status, authenticatedRequest } = useAuth();
  const [plan, setPlan] = useState<ChatPlan | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const load = useCallback(async () => { try { setPlan(await authenticatedRequest<ChatPlan>('/vendor/chat-plan/')); setError(null); } catch (cause) { setError(requestError(cause)); } }, [authenticatedRequest]);
  useFocusEffect(useCallback(() => { if (status === 'authenticated') { if (user?.role !== 'vendor') router.replace('/messages'); else void load(); } }, [load, router, status, user?.role]));
  async function request() { setBusy(true); try { setPlan(await authenticatedRequest<ChatPlan>('/vendor/chat-plan/', { method: 'POST', body: '{}' })); setError(null); } catch (cause) { setError(requestError(cause)); } finally { setBusy(false); } }
  return <ChatScreen title="Your chat access">
    <Text style={s.body}>Your first three client chats are free. Continue chatting with those clients without using another free chat.</Text>
    {error && <ErrorNotice message={error} retry={() => void load()} />}{!plan && !error && <Loading />}
    {plan && <><Text style={s.heading}>{plan.free_clients_remaining} free client chats left</Text>
      {plan.active ? <Text style={s.body}>Subscription active until {plan.active_until ? new Date(plan.active_until).toLocaleDateString() : ''}.</Text> : <><Text style={s.body}>A subscription unlocks more clients. Paid subscriptions are not open yet.</Text>{plan.requested ? <Text style={s.body}>Your interest is registered. You have not been charged.</Text> : <Button label="Notify me when subscriptions open" loading={busy} onPress={() => void request()} />}</>}
    </>}
  </ChatScreen>;
}
