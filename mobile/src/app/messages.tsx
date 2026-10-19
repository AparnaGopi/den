import { useFocusEffect, useRouter } from 'expo-router';
import { useCallback, useState } from 'react';
import { Text, View } from 'react-native';
import { ChatScreen } from '@/components/chat-screen';
import { ErrorNotice, Loading, discoveryStyles as s } from '@/components/discovery-ui';
import { Button } from '@/components/ui/button';
import { useAuth } from '@/context/auth-context';
import type { Conversation } from '@/types/chat';
import { requestError } from '@/types/events';

export default function MessagesScreen() {
  const router = useRouter();
  const { status, user, authenticatedRequest } = useAuth();
  const [chats, setChats] = useState<Conversation[] | null>(null);
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const load = useCallback(async (number = 1) => {
    try {
      const data = await authenticatedRequest<{ results: Conversation[]; next: string | null }>(`/messages/?page=${number}`);
      setChats((current) => number === 1 ? data.results : [...(current || []), ...data.results]);
      setPage(number); setHasMore(Boolean(data.next)); setError(null);
    } catch (cause) { setError(requestError(cause)); }
  }, [authenticatedRequest]);
  useFocusEffect(useCallback(() => { if (status === 'authenticated') void load(); }, [load, status]));
  return <ChatScreen title="Messages">
    <Text style={s.body}>{user?.role === 'vendor' ? 'Customer enquiries arrive here.' : 'Messages from your vendors, together in one place.'}</Text>
    <Button label="Refresh messages" variant="secondary" onPress={() => void load()} />
    {user?.role === 'vendor' && <Button label="Your chat allowance" variant="secondary" onPress={() => router.push('/chat-plan')} />}
    {error && <ErrorNotice message={error} retry={() => void load()} />}
    {!chats && !error && <Loading />}
    {chats?.length === 0 && <Text style={s.body}>No messages yet.</Text>}
    {chats?.map((chat) => <View key={chat.id} style={s.card}><Text style={s.heading}>{chat.title}</Text>
      {chat.unread_count > 0 && <Text style={s.badge}>{chat.unread_count} unread</Text>}
      <Text style={s.body}>{chat.event ? `${chat.event.event_type} · ${chat.event.city}` : 'General enquiry'}</Text>
      <Button label="Open conversation" variant="secondary" onPress={() => router.push({ pathname: '/conversation', params: { id: chat.id } })} />
    </View>)}
    {hasMore && <Button label="Load more" variant="secondary" onPress={() => void load(page + 1)} />}
  </ChatScreen>;
}
