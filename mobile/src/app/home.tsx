import { useFocusEffect, useRouter } from 'expo-router';
import { useCallback, useState } from 'react';
import { Text, View } from 'react-native';

import { DiscoveryScreen, ErrorNotice, Loading, discoveryStyles as styles } from '@/components/discovery-ui';
import { Button } from '@/components/ui/button';
import { useAuth } from '@/context/auth-context';
import { eventTitle, formatEventDate, requestError, torontoDateIso, type EventRequest, type Page } from '@/types/events';

export default function HomeScreen() {
  const router = useRouter();
  const { user, status, authenticatedRequest } = useAuth();
  useFocusEffect(useCallback(() => { if (status === 'authenticated' && user?.role === 'vendor') router.replace('/vendor-home'); }, [router, status, user?.role]));
  const [events, setEvents] = useState<EventRequest[]>([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(false);

  const load = useCallback(async (pageNumber = 1) => {
    setLoading(true); setError(null);
    try {
      const response = await authenticatedRequest<Page<EventRequest>>(`/events/?page=${pageNumber}`);
      setEvents((previous) => pageNumber === 1 ? response.results : [...previous, ...response.results]);
      setPage(pageNumber); setHasMore(Boolean(response.next));
    } catch (loadError) { setError(requestError(loadError)); }
    finally { setLoading(false); }
  }, [authenticatedRequest]);
  useFocusEffect(useCallback(() => {
    if (status === 'authenticated' && user?.role === 'customer') void load();
  }, [load, status, user?.role]));

  async function startEvent() {
    setCreating(true); setError(null);
    try {
      const event = await authenticatedRequest<EventRequest>('/events/', { method: 'POST', body: '{}' });
      router.push({ pathname: '/plan-event', params: { id: event.id } });
    } catch (createError) { setError(requestError(createError)); }
    finally { setCreating(false); }
  }
  const today = torontoDateIso();
  const drafts = events.filter((event) => event.status === 'DRAFT');
  const upcoming = events.filter((event) => event.status === 'READY' && event.event_date && event.event_date >= today);
  const past = events.filter((event) => event.status === 'READY' && event.event_date && event.event_date < today);

  function eventCard(event: EventRequest) {
    return <View key={event.id} style={styles.card}>
      <Text style={styles.badge}>{event.status === 'DRAFT' ? `Draft | ${event.completed_step}/6 steps saved` : 'Ready to discover'}</Text>
      <Text style={styles.heading}>{eventTitle(event)}</Text>
      <Text style={styles.body}>{formatEventDate(event.event_date)} | {event.city || 'Location to come'}</Text>
      {event.status === 'DRAFT' ? <Button label="Continue planning" variant="secondary" onPress={() => router.push({ pathname: '/plan-event', params: { id: event.id } })} /> : <Button label="Find matching vendors" variant="secondary" onPress={() => router.push({ pathname: '/event-matches', params: { id: event.id } })} />}
    </View>;
  }
  return <DiscoveryScreen title={`Hello, ${user?.first_name || 'there'}.`}>
    <Text style={styles.body}>Your next good gathering starts here.</Text>
    <Button label="Plan an event" loading={creating} onPress={() => void startEvent()} />
    {error && <ErrorNotice message={error} retry={() => void load()} />}
    {loading && <Loading />}
    {!loading && !error && events.length === 0 && <View style={styles.card}><Text style={styles.heading}>A little room to begin</Text><Text style={styles.body}>Tell us what you have in mind. We will save your answers as you go.</Text></View>}
    {drafts.length > 0 && <><Text style={styles.heading}>Pick up where you left off</Text>{drafts.map(eventCard)}</>}
    {upcoming.length > 0 && <><Text style={styles.heading}>Upcoming events</Text>{upcoming.map(eventCard)}</>}
    {past.length > 0 && <><Text style={styles.heading}>Past events</Text>{past.map((event) => <View key={event.id} style={styles.card}><Text style={styles.heading}>{eventTitle(event)}</Text><Text style={styles.body}>{formatEventDate(event.event_date)} | {event.city}</Text><Button label="Archive event" variant="secondary" onPress={() => { void authenticatedRequest(`/events/${event.id}/archive/`, { method: 'POST' }).then(() => load()).catch((archiveError: unknown) => setError(requestError(archiveError))); }} /></View>)}</>}
    {hasMore && <Button label="Load more events" variant="secondary" loading={loading} onPress={() => void load(page + 1)} />}
  </DiscoveryScreen>;
}
