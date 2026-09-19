import { useFocusEffect, useLocalSearchParams, useRouter } from 'expo-router';
import { useCallback, useState } from 'react';
import { StyleSheet, Text, View } from 'react-native';

import { ChoiceChip, DiscoveryScreen, ErrorNotice, Loading, discoveryStyles as styles } from '@/components/discovery-ui';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Colors } from '@/constants/theme';
import { useAuth } from '@/context/auth-context';
import { eventTitle, eventTypes, helpTypes, requestError, type Category, type EventRequest, type EventType, type HelpType, type VenueType } from '@/types/events';

type PlannerForm = {
  event_type: EventType | ''; custom_event_type: string; event_date: string; city: string; postal_code: string;
  guest_count: string; budget_min: string; budget_max: string; help_types: HelpType[]; required_categories: number[];
  theme: string; colours: string; venue_type: VenueType; notes: string;
};
const prompts = [
  'What are we celebrating?',
  'When and where will everyone gather?',
  'How many people, and what budget feels comfortable?',
  'What kind of help would make this easier?',
  'Which services or supplies do you need?',
  'Tell us about the atmosphere you have in mind.',
];
function formFor(event: EventRequest): PlannerForm {
  return {
    event_type: event.event_type, custom_event_type: event.custom_event_type, event_date: event.event_date || '',
    city: event.city, postal_code: event.postal_code, guest_count: String(event.guest_count ?? ''),
    budget_min: event.budget_min ?? '', budget_max: event.budget_max ?? '', help_types: event.help_types,
    required_categories: event.required_categories, theme: event.theme, colours: event.colours.join(', '),
    venue_type: event.venue_type, notes: event.notes,
  };
}
function payloadFor(form: PlannerForm, step: number) {
  switch (step) {
    case 0: return { event_type: form.event_type, custom_event_type: form.event_type === 'OTHER' ? form.custom_event_type : '' };
    case 1: return { event_date: form.event_date || null, city: form.city.trim(), postal_code: form.postal_code.trim() };
    case 2:
      if (form.guest_count && !/^\d+$/.test(form.guest_count)) throw new Error('Guest count must be a whole number.');
      return { guest_count: form.guest_count ? Number(form.guest_count) : null, budget_min: form.budget_min || null, budget_max: form.budget_max || null };
    case 3: return { help_types: form.help_types };
    case 4: return { required_categories: form.required_categories };
    default: return { theme: form.theme, colours: form.colours.split(',').map((colour) => colour.trim()).filter(Boolean), venue_type: form.venue_type, notes: form.notes };
  }
}

export default function PlanEventScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();
  const { status, authenticatedRequest } = useAuth();
  const [event, setEvent] = useState<EventRequest | null>(null);
  const [form, setForm] = useState<PlannerForm | null>(null);
  const [categories, setCategories] = useState<Category[]>([]);
  const [step, setStep] = useState(0);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const load = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      if (!id || !/^\d+$/.test(id)) throw new Error('Choose an event from Your Den to continue.');
      const [saved, activeCategories] = await Promise.all([
        authenticatedRequest<EventRequest>(`/events/${id}/`), authenticatedRequest<Category[]>('/categories/'),
      ]);
      if (saved.status === 'ARCHIVED') throw new Error('This event has been archived. Start a new event from Your Den.');
      setEvent(saved); setForm(formFor(saved)); setCategories(activeCategories);
      setStep(saved.status === 'READY' ? 0 : Math.min(saved.completed_step, 5));
    } catch (loadError) { setError(requestError(loadError)); }
    finally { setLoading(false); }
  }, [authenticatedRequest, id]);
  useFocusEffect(useCallback(() => { if (status === 'authenticated') void load(); }, [load, status]));

  function update<K extends keyof PlannerForm>(key: K, value: PlannerForm[K]) {
    setForm((previous) => previous ? { ...previous, [key]: value } : previous);
  }
  async function save(exit = false) {
    if (!form || !event) return;
    setSaving(true); setError(null);
    try {
      const payload = payloadFor(form, step);
      const saved = await authenticatedRequest<EventRequest>(exit ? `/events/${id}/` : `/events/${id}/steps/${step + 1}/`, {
        method: 'PATCH', body: JSON.stringify(payload),
      });
      setEvent(saved);
      if (exit) { router.replace('/home'); return; }
      if (step < 5) { setStep(step + 1); return; }
      await authenticatedRequest<EventRequest>(`/events/${id}/complete/`, { method: 'POST' });
      router.replace({ pathname: '/event-matches', params: { id } });
    } catch (saveError) { setError(requestError(saveError)); }
    finally { setSaving(false); }
  }
  function summary(index: number) {
    if (!event) return '';
    switch (index) {
      case 0: return eventTitle(event);
      case 1: return `${event.event_date} · ${event.city}${event.postal_code ? ` · ${event.postal_code}` : ''}`;
      case 2: return `${event.guest_count} guests · $${event.budget_min}–$${event.budget_max}`;
      case 3: return event.help_types.map((value) => helpTypes.find((help) => help.value === value)?.label).join(', ');
      case 4: return event.required_categories.map((value) => categories.find((category) => category.id === value)?.name || 'Category no longer available').join(', ');
      default: return event.theme || 'Open to ideas';
    }
  }
  const ready = !loading && form && event;
  return <DiscoveryScreen title="Let’s plan your event.">
    {loading && <Loading />}
    {error && <ErrorNotice message={error} retry={!event ? () => void load() : undefined} />}
    {ready && <>
      <View accessibilityRole="progressbar" accessibilityValue={{ min: 0, max: 6, now: step + 1 }} style={local.progress}><View style={[local.progressFill, { width: `${(step + 1) / 6 * 100}%` }]} /></View>
      <Text style={styles.badge}>Step {step + 1} of 6 · {event.completed_step} steps saved</Text>
      <Text style={styles.body}>A few thoughtful questions. Your answers are saved after each step.</Text>
      {prompts.slice(0, step).map((prompt, index) => <View key={prompt} style={local.exchange}>
        <View style={local.message}><Text style={styles.badge}>DEN</Text><Text style={styles.body}>{prompt}</Text></View>
        <View style={local.answer}><Text style={styles.body}>{summary(index)}</Text></View>
      </View>)}
      <View style={local.message}><Text style={styles.badge}>DEN</Text><Text style={styles.heading}>{prompts[step]}</Text></View>
      <View style={styles.card}>
        {step === 0 && <>
          <View style={styles.chips}>{eventTypes.map((type) => <ChoiceChip key={type.value} label={type.label} selected={form.event_type === type.value} disabled={saving} onPress={() => update('event_type', type.value)} />)}</View>
          {form.event_type === 'OTHER' && <Input label="Your event type" value={form.custom_event_type} editable={!saving} onChangeText={(text) => update('custom_event_type', text)} maxLength={100} />}
        </>}
        {step === 1 && <>
          <Input label="Event date (YYYY-MM-DD)" placeholder="2026-12-20" value={form.event_date} editable={!saving} onChangeText={(text) => update('event_date', text)} autoCapitalize="none" maxLength={10} />
          <Input label="City" value={form.city} editable={!saving} onChangeText={(text) => update('city', text)} maxLength={100} />
          <Input label="Postal code (optional)" value={form.postal_code} editable={!saving} onChangeText={(text) => update('postal_code', text)} autoCapitalize="characters" maxLength={20} />
          <Text style={styles.body}>City is enough for discovery. Keep exact addresses out of this planner.</Text>
        </>}
        {step === 2 && <>
          <Input label="Number of guests" keyboardType="number-pad" value={form.guest_count} editable={!saving} onChangeText={(text) => update('guest_count', text)} />
          <Input label="Minimum event budget ($)" keyboardType="decimal-pad" value={form.budget_min} editable={!saving} onChangeText={(text) => update('budget_min', text)} />
          <Input label="Maximum event budget ($)" keyboardType="decimal-pad" value={form.budget_max} editable={!saving} onChangeText={(text) => update('budget_max', text)} />
          <Text style={styles.body}>Published vendor prices are only a starting point. This is your overall event budget.</Text>
        </>}
        {step === 3 && <><Text style={styles.body}>Choose all that apply.</Text><View style={styles.chips}>{helpTypes.map((help) => <ChoiceChip key={help.value} label={help.label} disabled={saving} selected={form.help_types.includes(help.value)} onPress={() => update('help_types', form.help_types.includes(help.value) ? form.help_types.filter((value) => value !== help.value) : [...form.help_types, help.value])} />)}</View></>}
        {step === 4 && <>
          <Text style={styles.body}>Choose at least one category.</Text>
          <View style={styles.chips}>{categories.map((category) => <ChoiceChip key={category.id} label={category.name} disabled={saving} selected={form.required_categories.includes(category.id)} onPress={() => update('required_categories', form.required_categories.includes(category.id) ? form.required_categories.filter((value) => value !== category.id) : [...form.required_categories, category.id])} />)}</View>
          {!categories.length && <Text style={styles.body}>No categories are available yet. Your draft is saved; check back soon.</Text>}
        </>}
        {step === 5 && <>
          <Input label="Theme (optional)" value={form.theme} editable={!saving} onChangeText={(text) => update('theme', text)} maxLength={200} />
          <Input label="Colours (optional, separated by commas)" value={form.colours} editable={!saving} onChangeText={(text) => update('colours', text)} />
          <Text style={styles.body}>Venue setting</Text>
          <View style={styles.chips}>{(['INDOOR', 'OUTDOOR', 'UNDECIDED'] as const).map((venue) => <ChoiceChip key={venue} label={venue === 'UNDECIDED' ? 'Undecided' : venue === 'INDOOR' ? 'Indoor' : 'Outdoor'} selected={form.venue_type === venue} disabled={saving} onPress={() => update('venue_type', venue)} />)}</View>
          <Input label="Anything else? (optional)" value={form.notes} editable={!saving} onChangeText={(text) => update('notes', text)} multiline maxLength={5000} />
        </>}
      </View>
      <Button label={step === 5 ? 'Save and find vendors' : 'Save and continue'} loading={saving} onPress={() => void save()} />
      <Button label="Save and finish later" variant="secondary" disabled={saving} onPress={() => void save(true)} />
      {step > 0 && <Button label="Previous step" variant="secondary" disabled={saving} onPress={() => { setError(null); setStep(step - 1); }} />}
    </>}
  </DiscoveryScreen>;
}
const local = StyleSheet.create({
  progress: { height: 6, backgroundColor: Colors.light.line, borderRadius: 3, overflow: 'hidden' },
  progressFill: { height: 6, backgroundColor: Colors.light.terracotta },
  exchange: { gap: 8 },
  message: { backgroundColor: Colors.light.backgroundElement, padding: 18, borderRadius: 18, borderBottomLeftRadius: 4, gap: 8, alignSelf: 'flex-start', maxWidth: '95%' },
  answer: { backgroundColor: Colors.light.surface, padding: 14, borderRadius: 18, borderBottomRightRadius: 4, alignSelf: 'flex-end', maxWidth: '90%' },
});
