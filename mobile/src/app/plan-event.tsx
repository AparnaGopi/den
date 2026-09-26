import { useFocusEffect, useLocalSearchParams, useRouter } from 'expo-router';
import { useCallback, useState } from 'react';
import DateTimePicker from '@react-native-community/datetimepicker';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { ChoiceChip, DiscoveryScreen, ErrorNotice, Loading, discoveryStyles as styles } from '@/components/discovery-ui';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Colors } from '@/constants/theme';
import { useAuth } from '@/context/auth-context';
import { dateFromIso, eventTitle, eventTypes, formatEventDate, helpTypes, isoFromPickerDate, legacyHelpTypes, requestError, tomorrowPickerDate, torontoDateIso, type Category, type EventLocation, type EventRequest, type EventType, type HelpType, type VenueType } from '@/types/events';

type PlannerForm = {
  event_type: EventType | ''; custom_event_type: string; event_date: string; city: string; postal_code: string;
  guest_count: string; budget_min: string; budget_max: string; help_types: HelpType[]; other_help_text: string; required_categories: number[];
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
function formFor(event: EventRequest, locations: EventLocation[]): PlannerForm {
  const matchedLocation = locations.find((location) => [location.label, ...location.aliases].some((label) => label.toLowerCase() === event.city.trim().toLowerCase()));
  return {
    event_type: event.event_type, custom_event_type: event.custom_event_type, event_date: event.event_date || '',
    city: matchedLocation?.id || event.city, postal_code: event.postal_code, guest_count: String(event.guest_count ?? ''),
    budget_min: event.budget_min ?? '', budget_max: event.budget_max ?? '', help_types: event.help_types,
    other_help_text: event.other_help_text || '',
    required_categories: event.required_categories, theme: event.theme, colours: event.colours.join(', '),
    venue_type: event.venue_type, notes: event.notes,
  };
}
function payloadFor(form: PlannerForm, step: number): Record<string, unknown> {
  switch (step) {
    case 0: return { event_type: form.event_type, custom_event_type: form.event_type === 'OTHER' ? form.custom_event_type : '' };
    case 1: return { event_date: form.event_date || null, city: form.city.trim(), postal_code: form.postal_code.trim() };
    case 2:
      if (form.guest_count && !/^\d+$/.test(form.guest_count)) throw new Error('Guest count must be a whole number.');
      return { guest_count: form.guest_count ? Number(form.guest_count) : null, budget_min: form.budget_min || null, budget_max: form.budget_max || null };
    case 3: return { help_types: form.help_types, other_help_text: form.other_help_text.trim() };
    case 4: return { required_categories: form.required_categories };
    default: return { theme: form.theme, colours: form.colours.split(',').map((colour) => colour.trim()).filter(Boolean), venue_type: form.venue_type, notes: form.notes };
  }
}
function fullPayloadFor(form: PlannerForm): Record<string, unknown> {
  const payload = {
    ...payloadFor(form, 0), ...payloadFor(form, 1), ...payloadFor(form, 2),
    ...payloadFor(form, 3), ...payloadFor(form, 4), ...payloadFor(form, 5),
  };
  if (!form.city.trim()) delete payload.city;
  return payload;
}
function money(value: string) {
  const amount = Number(value);
  return Number.isFinite(amount) ? amount.toFixed(2) : '0.00';
}

export default function PlanEventScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();
  const { status, authenticatedRequest } = useAuth();
  const [event, setEvent] = useState<EventRequest | null>(null);
  const [form, setForm] = useState<PlannerForm | null>(null);
  const [categories, setCategories] = useState<Category[]>([]);
  const [showAllServices, setShowAllServices] = useState(false);
  const [locations, setLocations] = useState<EventLocation[]>([]);
  const [locationSearch, setLocationSearch] = useState('');
  const [showLocationOptions, setShowLocationOptions] = useState(false);
  const [showDatePicker, setShowDatePicker] = useState(false);
  const [step, setStep] = useState(0);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const load = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      if (!id || !/^\d+$/.test(id)) throw new Error('Choose an event from Your Den to continue.');
      const [saved, activeCategories, availableLocations] = await Promise.all([
        authenticatedRequest<EventRequest>(`/events/${id}/`), authenticatedRequest<Category[]>('/categories/'),
        authenticatedRequest<EventLocation[]>('/event-locations/'),
      ]);
      if (saved.status === 'ARCHIVED') throw new Error('This event has been archived. Start a new event from Your Den.');
      setEvent(saved); setForm(formFor(saved, availableLocations)); setCategories(activeCategories); setLocations(availableLocations);
      setLocationSearch(saved.city);
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
    if (form.help_types.includes('OTHER') && !form.other_help_text.trim()) {
      setError('Please describe the other help you need.');
      return;
    }
    if (step === 1) {
      const today = torontoDateIso();
      if (!form.event_date || (form.event_date <= today && form.event_date !== event.event_date)) {
        setError('Please choose a date after today.');
        return;
      }
      const knownLocation = locations.some((location) => location.id === form.city);
      if (!knownLocation && form.city !== event.city) {
        setError('Den currently supports events within the Greater Toronto Area.');
        return;
      }
    }
    setSaving(true); setError(null);
    try {
      const payload = exit ? fullPayloadFor(form) : payloadFor(form, step);
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
  async function saveCurrentAndGoBack() {
    if (!form || !event || step === 0) return;
    if (form.help_types.includes('OTHER') && !form.other_help_text.trim()) {
      setError('Please describe the other help you need.');
      return;
    }
    setSaving(true); setError(null);
    try {
      const saved = await authenticatedRequest<EventRequest>(`/events/${id}/`, {
        method: 'PATCH', body: JSON.stringify(payloadFor(form, step)),
      });
      setEvent(saved);
      setStep(step - 1);
    } catch (saveError) { setError(requestError(saveError)); }
    finally { setSaving(false); }
  }
  function summary(index: number) {
    if (!event) return '';
    switch (index) {
      case 0: return eventTitle(event);
      case 1: return `${formatEventDate(event.event_date)} | ${event.city}${event.postal_code ? ` | ${event.postal_code}` : ''}`;
      case 2: return `${event.guest_count} guests | CAD $${money(event.budget_min || '0')} - $${money(event.budget_max || '0')}`;
      case 3: return `${event.help_types.map((value) => helpTypes.find((help) => help.value === value)?.label || legacyHelpTypes.find((help) => help.value === value)?.label || value).join(', ')}${event.help_types.includes('OTHER') && event.other_help_text ? `: ${event.other_help_text}` : ''}`;
      case 4: return event.required_categories.map((value) => categories.find((category) => category.id === value)?.name || 'Category no longer available').join(', ');
      default: return event.theme || 'Open to ideas';
    }
  }
  const ready = !loading && form && event;
  const selectedLocation = locations.find((location) => location.id === form?.city);
  const matchingLocations = locations.filter((location) => {
    const search = locationSearch.trim().toLowerCase();
    return !search || [location.label, ...location.aliases].some((name) => name.toLowerCase().includes(search));
  }).slice(0, 8);
  const minimumDate = tomorrowPickerDate();
  const helpChoices = [...helpTypes, ...legacyHelpTypes.filter((choice) => form?.help_types.includes(choice.value))];
  const selectedCategoryIds = form?.required_categories || [];
  const featuredCategories = categories.filter((category) => category.is_featured
    || category.relevant_help_types.some((helpType) => form?.help_types.includes(helpType))
    || selectedCategoryIds.includes(category.id));
  const additionalCategories = categories.filter((category) => !featuredCategories.includes(category));
  const visibleCategories = showAllServices ? categories : featuredCategories;
  const visibleGroups = [...new Set(visibleCategories.map((category) => category.service_group_label))];
  return <DiscoveryScreen title="Let's plan your event.">
    {loading && <Loading />}
    {error && <ErrorNotice message={error} retry={!event ? () => void load() : undefined} />}
    {ready && <>
      <View accessibilityRole="progressbar" accessibilityValue={{ min: 0, max: 6, now: step + 1 }} style={local.progress}><View style={[local.progressFill, { width: `${(step + 1) / 6 * 100}%` }]} /></View>
      <Text style={styles.badge}>Step {step + 1} of 6 | {event.completed_step} steps saved</Text>
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
          <View style={local.field}>
            <Text style={local.label}>Event date</Text>
            <Pressable accessibilityRole="button" accessibilityLabel={`Choose event date${form.event_date ? `, ${formatEventDate(form.event_date)}` : ''}`} disabled={saving} onPress={() => setShowDatePicker(true)} style={local.dateButton}>
              <Text style={local.dateText}>{form.event_date ? formatEventDate(form.event_date) : 'Choose a date'}</Text>
            </Pressable>
          </View>
          {showDatePicker && <DateTimePicker value={form.event_date ? dateFromIso(form.event_date) : minimumDate} mode="date" display="default" minimumDate={minimumDate} onChange={(pickerEvent, selectedDate) => {
            setShowDatePicker(false);
            if (pickerEvent.type === 'set' && selectedDate) update('event_date', isoFromPickerDate(selectedDate));
          }} />}
          <Input label="Search GTA locations" placeholder="Start typing a city or district" value={locationSearch} editable={!saving} onFocus={() => setShowLocationOptions(true)} onChangeText={(text) => {
            setLocationSearch(text);
            setShowLocationOptions(true);
            if (text.trim().toLowerCase() !== selectedLocation?.label.toLowerCase()) update('city', '');
          }} />
          {showLocationOptions && <View style={styles.chips}>{matchingLocations.map((location) => <ChoiceChip key={location.id} label={location.label} selected={form.city === location.id} disabled={saving} onPress={() => {
            update('city', location.id);
            setLocationSearch(location.label);
            setShowLocationOptions(false);
          }} />)}</View>}
          {showLocationOptions && !matchingLocations.length && <Text style={styles.body}>Den currently supports events within the Greater Toronto Area.</Text>}
          <Input label="Postal code (optional)" value={form.postal_code} editable={!saving} onChangeText={(text) => update('postal_code', text)} autoCapitalize="characters" maxLength={20} />
          <Text style={styles.body}>City is enough for discovery. Keep exact addresses out of this planner.</Text>
        </>}
        {step === 2 && <>
          <Input label="Number of guests" keyboardType="number-pad" value={form.guest_count} editable={!saving} onChangeText={(text) => update('guest_count', text)} />
          <Input label="Minimum event budget ($)" keyboardType="decimal-pad" value={form.budget_min} editable={!saving} onChangeText={(text) => update('budget_min', text)} />
          <Input label="Maximum event budget ($)" keyboardType="decimal-pad" value={form.budget_max} editable={!saving} onChangeText={(text) => update('budget_max', text)} />
          <Text style={styles.body}>Published vendor prices are only a starting point. This is your overall event budget.</Text>
        </>}
        {step === 3 && <>
          <Text style={styles.body}>Choose all that apply.</Text>
          <View style={styles.chips}>{helpChoices.map((help) => <ChoiceChip key={help.value} label={help.label} disabled={saving} selected={form.help_types.includes(help.value)} onPress={() => {
            const selected = form.help_types.includes(help.value);
            update('help_types', selected ? form.help_types.filter((value) => value !== help.value) : [...form.help_types, help.value]);
            if (help.value === 'OTHER' && selected) update('other_help_text', '');
          }} />)}</View>
          {form.help_types.includes('OTHER') && <Input label="Please specify" value={form.other_help_text} editable={!saving} onChangeText={(text) => update('other_help_text', text)} maxLength={500} />}
        </>}
        {step === 4 && <>
          <Text style={styles.body}>Choose at least one category.</Text>
          {visibleGroups.map((group) => <View key={group} style={local.categoryGroup}><Text style={styles.badge}>{group}</Text><View style={styles.chips}>{visibleCategories.filter((category) => category.service_group_label === group).map((category) => <ChoiceChip key={category.id} label={category.name} disabled={saving} selected={form.required_categories.includes(category.id)} onPress={() => update('required_categories', form.required_categories.includes(category.id) ? form.required_categories.filter((value) => value !== category.id) : [...form.required_categories, category.id])} />)}</View></View>)}
          {additionalCategories.length > 0 && <Button label={showAllServices ? 'Show relevant services' : 'Browse all services'} variant="secondary" disabled={saving} onPress={() => setShowAllServices(!showAllServices)} />}
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
      {step > 0 && <Button label="Previous step" variant="secondary" loading={saving} onPress={() => void saveCurrentAndGoBack()} />}
    </>}
  </DiscoveryScreen>;
}
const local = StyleSheet.create({
  field: { gap: 8 },
  label: { color: Colors.light.ink, fontSize: 14, fontWeight: '700' },
  dateButton: { backgroundColor: Colors.light.surface, borderColor: Colors.light.line, borderRadius: 12, borderWidth: 1, justifyContent: 'center', minHeight: 54, paddingHorizontal: 16 },
  dateText: { color: Colors.light.ink, fontSize: 16 },
  categoryGroup: { gap: 8 },
  progress: { height: 6, backgroundColor: Colors.light.line, borderRadius: 3, overflow: 'hidden' },
  progressFill: { height: 6, backgroundColor: Colors.light.terracotta },
  exchange: { gap: 8 },
  message: { backgroundColor: Colors.light.backgroundElement, padding: 18, borderRadius: 18, borderBottomLeftRadius: 4, gap: 8, alignSelf: 'flex-start', maxWidth: '95%' },
  answer: { backgroundColor: Colors.light.surface, padding: 14, borderRadius: 18, borderBottomRightRadius: 4, alignSelf: 'flex-end', maxWidth: '90%' },
});
