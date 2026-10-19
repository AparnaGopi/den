import { useFocusEffect, useLocalSearchParams, useRouter } from 'expo-router';
import { useCallback, useRef, useState } from 'react';
import { AppState, Text, View } from 'react-native';
import { ChatScreen } from '@/components/chat-screen';
import { ErrorNotice, Loading, discoveryStyles as s } from '@/components/discovery-ui';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { useAuth } from '@/context/auth-context';
import { ApiError } from '@/lib/api';
import type { Thread } from '@/types/chat';
import { requestError } from '@/types/events';

export default function ConversationScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();
  const { status, authenticatedRequest } = useAuth();
  const [thread, setThread] = useState<Thread | null>(null);
  const [body, setBody] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const sequence = useRef(0);
  const load = useCallback(async () => {
    if (!id) return;
    const requestId = ++sequence.current;
    try { const data = await authenticatedRequest<Thread>(`/messages/${id}/`); if (requestId === sequence.current) { setThread(data); setError(null); } }
    catch (cause) { if (requestId === sequence.current) setError(requestError(cause)); }
  }, [authenticatedRequest, id]);
  useFocusEffect(useCallback(() => {
    if (status !== 'authenticated') return;
    void load();
    const timer = setInterval(() => { if (AppState.currentState === 'active') void load(); }, 10000);
    return () => { clearInterval(timer); sequence.current += 1; };
  }, [load, status]));
  async function send() {
    if (!body.trim() || busy) return;
    setBusy(true); setError(null);
    try { await authenticatedRequest(`/messages/${id}/`, { method: 'POST', body: JSON.stringify({ body }) }); setBody(''); await load(); }
    catch (cause) { setError(requestError(cause)); if (cause instanceof ApiError && cause.status === 402) router.push('/chat-plan'); }
    finally { setBusy(false); }
  }
  async function older() {
    if (!thread?.next_before || busy) return;
    setBusy(true);
    try { const data = await authenticatedRequest<Thread>(`/messages/${id}/?before=${thread.next_before}`); setThread({ ...thread, messages: [...data.messages, ...thread.messages], next_before: data.next_before }); }
    catch (cause) { setError(requestError(cause)); } finally { setBusy(false); }
  }
  return <ChatScreen title={thread?.conversation.title || 'Conversation'}>
    {error && <ErrorNotice message={error} retry={() => void load()} />}
    {!thread && !error && <Loading />}
    {thread?.conversation.event && <View style={s.card}><Text style={s.heading}>Shared event</Text><Text style={s.body}>{thread.conversation.event.event_type} · {thread.conversation.event.date} · {thread.conversation.event.city}</Text><Text style={s.body}>{thread.conversation.event.guests} guests · Budget ${thread.conversation.event.budget_min}–${thread.conversation.event.budget_max}</Text><Text style={s.body}>{thread.conversation.event.notes}</Text></View>}
    {thread?.next_before && <Button label="Earlier messages" variant="secondary" disabled={busy} onPress={() => void older()} />}
    {thread?.messages.map((message) => <View key={message.id} style={[s.card, { alignSelf: message.mine ? 'flex-end' : 'flex-start', maxWidth: '95%', minWidth: '45%' }]}><Text style={s.badge}>{message.mine ? 'You' : thread.conversation.title}</Text><Text style={s.body}>{message.body}</Text><Text style={s.body}>{new Date(message.created_at).toLocaleString()}</Text></View>)}
    {thread?.conversation.can_reply ? <><Input label="Your message" value={body} onChangeText={setBody} multiline maxLength={4000} editable={!busy} /><Button label="Send message" loading={busy} disabled={!body.trim()} onPress={() => void send()} /></> : thread && <Button label="View subscription options to reply" onPress={() => router.push('/chat-plan')} />}
  </ChatScreen>;
}
