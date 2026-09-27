import { useFocusEffect, useLocalSearchParams, useRouter } from 'expo-router';
import { useCallback, useState } from 'react';
import { Image, Linking, Text, View } from 'react-native';
import { ChoiceChip, DiscoveryScreen, ErrorNotice, Loading, discoveryStyles as s } from '@/components/discovery-ui';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { useAuth } from '@/context/auth-context';
import { eventTitle, formatEventDate, helpTypes, requestError, type Category, type DiscoveryService, type EventRequest, type MatchPage, type VendorMatch } from '@/types/events';

type Filters = { category: string; help_types: string[]; service_tag: string; listing_type: string; location: string; price_min: string; price_max: string; rating_min: string };
const blank: Filters = { category: '', help_types: [], service_tag: '', listing_type: '', location: '', price_min: '', price_max: '', rating_min: '' };
const listingTypes = [['', 'All types'], ['SERVICE', 'Services'], ['PACKAGE', 'Packages'], ['RENTAL', 'Rentals'], ['PRODUCT', 'Products']] as const;
const sorts = [['relevance', 'Best match'], ['price', 'Price'], ['newest', 'Newest'], ['rating', 'Verified rating']] as const;

export default function EventMatchesScreen() {
  const { id } = useLocalSearchParams<{ id?: string }>();
  const router = useRouter();
  const { status, authenticatedRequest } = useAuth();
  const [event, setEvent] = useState<EventRequest | null>(null);
  const [categories, setCategories] = useState<Category[]>([]);
  const [serviceOptions, setServiceOptions] = useState<DiscoveryService[]>([]);
  const [matches, setMatches] = useState<VendorMatch[]>([]);
  const [metadata, setMetadata] = useState<MatchPage | null>(null);
  const [inputs, setInputs] = useState<Filters>(blank);
  const [filters, setFilters] = useState<Filters>(blank);
  const [sort, setSort] = useState('relevance');
  const [showFilters, setShowFilters] = useState(false);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [savingId, setSavingId] = useState<number | null>(null);
  const [creatingEvent, setCreatingEvent] = useState(false);
  const load = useCallback(async (number = 1) => {
    setLoading(true); setError(null);
    if (number === 1) { setMatches([]); setMetadata(null); }
    try {
      const query = new URLSearchParams({ sort, page: String(number), approval_status: 'APPROVED' });
      Object.entries(filters).forEach(([key, value]) => {
        if (Array.isArray(value)) value.forEach((item) => query.append(key, item));
        else if (value.trim()) query.set(key, value.trim());
      });
      if (id && !/^\d+$/.test(id)) throw new Error('Choose an event from Your Den to view matches.');
      const [saved, activeCategories, serviceOptions, response] = await Promise.all([
        id ? authenticatedRequest<EventRequest>(`/events/${id}/`) : Promise.resolve(null),
        authenticatedRequest<Category[]>('/categories/'), authenticatedRequest<DiscoveryService[]>('/discovery-services/'),
        authenticatedRequest<MatchPage>(`${id ? `/events/${id}/matches/` : '/vendors/discovery/'}?${query}`),
      ]);
      setEvent(saved); setCategories(activeCategories); setServiceOptions(serviceOptions); setMetadata(response); setPage(number);
      setMatches((previous) => number === 1 ? response.results : [...previous, ...response.results]);
    } catch (cause) { setError(requestError(cause)); } finally { setLoading(false); }
  }, [authenticatedRequest, filters, id, sort]);
  useFocusEffect(useCallback(() => { if (status === 'authenticated') void load(); }, [load, status]));
  async function toggleSave(vendor: VendorMatch) {
    if (!event) return;
    setSavingId(vendor.id); setActionError(null);
    try {
      setEvent(await authenticatedRequest<EventRequest>(`/events/${id}/saved-vendors/${vendor.id}/`, { method: event.saved_vendor_ids.includes(vendor.id) ? 'DELETE' : 'PUT' }));
    } catch (cause) { setActionError(requestError(cause)); } finally { setSavingId(null); }
  }
  const setInput = (key: keyof Filters, value: string) => setInputs((old) => ({ ...old, [key]: value }));
  const reset = () => { setInputs({ ...blank, help_types: [] }); setFilters({ ...blank, help_types: [] }); setSort('relevance'); };
  async function startGuided() {
    setActionError(null); setCreatingEvent(true);
    try {
      const draft = await authenticatedRequest<EventRequest>('/events/', { method: 'POST', body: '{}' });
      const prefill: Record<string, unknown> = {};
      const describedHelpTypes = filters.help_types.filter((helpType) => helpType !== 'OTHER');
      if (describedHelpTypes.length) prefill.help_types = describedHelpTypes;
      if (filters.category) prefill.required_categories = [Number(filters.category)];
      if (Object.keys(prefill).length) await authenticatedRequest<EventRequest>(`/events/${draft.id}/`, { method: 'PATCH', body: JSON.stringify(prefill) });
      router.push({ pathname: '/plan-event', params: { id: String(draft.id) } });
    } catch (cause) { setActionError(requestError(cause)); } finally { setCreatingEvent(false); }
  }
  return <DiscoveryScreen title={event ? 'Meet your possible people.' : 'Find your people.'}>
    <Text style={s.body}>{event ? `${eventTitle(event)} | ${event.city} | ${formatEventDate(event.event_date)}` : 'Browse active, approved vendors now. No event plan required.'}</Text>
    {!event && <Button label="Help me refine" variant="secondary" loading={creatingEvent} onPress={() => void startGuided()} />}
    <View style={s.row}><Text style={s.badge}>APPROVED VENDORS ONLY</Text><Button label={showFilters ? 'Hide filters' : 'Filters'} variant="secondary" onPress={() => setShowFilters(!showFilters)} /></View>
    {showFilters && <View style={s.card}>
      <Text style={s.heading}>Refine your discovery</Text><Text style={s.body}>What do you need help with?</Text>
      <View style={s.chips}>{helpTypes.map((item) => <ChoiceChip key={item.value} label={item.label} selected={inputs.help_types.includes(item.value)} onPress={() => setInputs((old) => ({ ...old, help_types: old.help_types.includes(item.value) ? old.help_types.filter((value) => value !== item.value) : [...old.help_types, item.value] }))} />)}</View>
      <Text style={s.body}>Category</Text>
      <View style={s.chips}><ChoiceChip label="All requested categories" selected={!inputs.category} onPress={() => setInput('category', '')} />{categories.map((item) => <ChoiceChip key={item.id} label={item.name} selected={inputs.category === String(item.id)} onPress={() => setInput('category', String(item.id))} />)}</View>
      <Text style={s.body}>Specific service</Text><View style={s.chips}><ChoiceChip label="Any service" selected={!inputs.service_tag} onPress={() => setInput('service_tag', '')} />{serviceOptions.map((item) => <ChoiceChip key={item.id} label={item.name} selected={inputs.service_tag === String(item.id)} onPress={() => setInput('service_tag', String(item.id))} />)}</View>
      <Text style={s.body}>Listing type</Text><View style={s.chips}><ChoiceChip label="All types" selected={!inputs.listing_type} onPress={() => setInput('listing_type', '')} />{listingTypes.map(([value, label]) => <ChoiceChip key={value} label={label} selected={inputs.listing_type === value} onPress={() => setInput('listing_type', value)} />)}</View>
      <Text style={s.body}>Minimum verified rating</Text><View style={s.chips}>{[['', 'Any rating'], ['3', '3+'], ['4', '4+'], ['5', '5']].map(([value, label]) => <ChoiceChip key={value} label={label} selected={inputs.rating_min === value} onPress={() => setInput('rating_min', value)} />)}</View>
      <Input label="Service location" value={inputs.location} onChangeText={(value) => setInput('location', value)} placeholder="City or listed service area" maxLength={100} />
      <Input label="Minimum published listing price ($)" keyboardType="decimal-pad" value={inputs.price_min} onChangeText={(value) => setInput('price_min', value)} />
      <Input label="Maximum published listing price ($)" keyboardType="decimal-pad" value={inputs.price_max} onChangeText={(value) => setInput('price_max', value)} />
      <Text style={s.body}>Price filters compare published amounts, including hourly rates. Quote-only listings have no amount to filter.</Text>
      <Text style={s.body}>Approval status: Approved. Private vendor profiles are never included.</Text>
      <Button label="Apply filters" disabled={loading} onPress={() => { setFilters({ ...inputs }); setShowFilters(false); }} /><Button label="Reset filters" variant="secondary" disabled={loading} onPress={reset} />
    </View>}
    <Text style={s.heading}>Sort by</Text><View style={s.chips}>{sorts.map(([value, label]) => <ChoiceChip key={value} label={label} selected={sort === value} disabled={loading} onPress={() => setSort(value)} />)}</View>
    <Text style={s.body}>Ratings come only from verified Den reviews. Unrated vendors appear last when sorting by rating.</Text>
    {loading && <Loading />}{error && <ErrorNotice message={error} retry={() => void load(page)} />}{actionError && <ErrorNotice message={actionError} />}
    {!loading && !error && metadata && <Text style={s.body}>{metadata.count} {metadata.count === 1 ? 'vendor' : 'vendors'} found · {metadata.price_note}</Text>}
    {!loading && !error && !matches.length && <View style={s.card}><Text style={s.heading}>No vendors found</Text><Text style={s.body}>{Object.values(filters).some((value) => Array.isArray(value) ? value.length > 0 : Boolean(value)) ? 'No active, approved vendors match these filters yet. Change or clear a filter to see more.' : 'There are no active, approved vendors to display yet. Please check back soon.'}</Text><Button label="Clear filters" variant="secondary" onPress={reset} />{event && <Button label="Edit event" variant="secondary" onPress={() => router.push({ pathname: '/plan-event', params: { id } })} />}</View>}
    {matches.map((vendor) => <View key={vendor.id} style={s.card}>
      {vendor.profile_image && <Image source={{ uri: vendor.profile_image }} accessibilityLabel={`${vendor.business_name} profile`} alt={`${vendor.business_name} profile`} style={{ width: 64, height: 64, borderRadius: 16 }} />}
      <Text style={s.badge}>Approved · {vendor.match_score}/100 match</Text><Text style={s.heading}>{vendor.business_name}</Text><Text style={s.body}>{vendor.city} · Serving {vendor.service_area}</Text><Text style={s.body} numberOfLines={3}>{vendor.description}</Text>
      <Text style={s.body}>{vendor.rating === null ? 'No verified reviews yet' : `${vendor.rating}/5 | ${vendor.review_count} verified Den reviews`}</Text>
      {vendor.matching_reasons.filter((reason) => reason.points > 0).map((reason) => <Text key={reason.code} style={s.body}>• {reason.label}</Text>)}
      {vendor.listings.map((listing) => <Text key={listing.id} style={s.body}>{listing.title}{listing.service_tags.length ? ` · ${listing.service_tags.map((tag) => tag.name).join(', ')}` : ''} · {listing.price === null || listing.pricing_type === 'CONTACT_FOR_QUOTE' ? 'Contact for a quote' : `${listing.pricing_type === 'STARTING_FROM' ? 'From ' : ''}$${listing.price}${listing.pricing_type === 'HOURLY' ? '/hour' : ''}`}</Text>)}
      <Button label="View Profile" variant="secondary" onPress={() => { void Linking.openURL(vendor.profile_url).catch((cause: unknown) => setActionError(requestError(cause))); }} />
      {event && <Button label={event.saved_vendor_ids.includes(vendor.id) ? 'Saved · Remove' : 'Save'} loading={savingId === vendor.id} disabled={savingId !== null} onPress={() => void toggleSave(vendor)} />}
    </View>)}
    {metadata?.next && <Button label="Load more vendors" variant="secondary" loading={loading} onPress={() => void load(page + 1)} />}
    {event && <Button label="Edit event answers" variant="secondary" onPress={() => router.push({ pathname: '/plan-event', params: { id } })} />}
  </DiscoveryScreen>;
}
