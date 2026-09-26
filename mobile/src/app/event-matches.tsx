import { useFocusEffect, useLocalSearchParams, useRouter } from 'expo-router';
import { useCallback, useState } from 'react';
import { Image, Linking, Text, View } from 'react-native';
import { ChoiceChip, DiscoveryScreen, ErrorNotice, Loading, discoveryStyles as s } from '@/components/discovery-ui';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { useAuth } from '@/context/auth-context';
import { eventTitle, formatEventDate, helpTypes, legacyHelpTypes, requestError, type Category, type EventRequest, type MatchPage, type VendorMatch } from '@/types/events';

type Filters = { category: string; service: string; listing_type: string; location: string; price_min: string; price_max: string; rating_min: string };
const blank: Filters = { category: '', service: '', listing_type: '', location: '', price_min: '', price_max: '', rating_min: '' };
const listingTypes = [['SERVICE', 'Services'], ['PACKAGE', 'Packages'], ['RENTAL', 'Rentals'], ['PRODUCT', 'Products']] as const;
const sorts = [['relevance', 'Best match'], ['price', 'Price'], ['newest', 'Newest'], ['rating', 'Verified rating']] as const;
const matchServices = [...helpTypes, ...legacyHelpTypes];

export default function EventMatchesScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();
  const { status, authenticatedRequest } = useAuth();
  const [event, setEvent] = useState<EventRequest | null>(null);
  const [categories, setCategories] = useState<Category[]>([]);
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
  const load = useCallback(async (number = 1) => {
    setLoading(true); setError(null);
    if (number === 1) { setMatches([]); setMetadata(null); }
    try {
      if (!id || !/^\d+$/.test(id)) throw new Error('Choose an event from Your Den to view matches.');
      const query = new URLSearchParams({ sort, page: String(number), approval_status: 'APPROVED' });
      Object.entries(filters).forEach(([key, value]) => { if (value.trim()) query.set(key, value.trim()); });
      const [saved, activeCategories, response] = await Promise.all([
        authenticatedRequest<EventRequest>(`/events/${id}/`), authenticatedRequest<Category[]>('/categories/'),
        authenticatedRequest<MatchPage>(`/events/${id}/matches/?${query}`),
      ]);
      setEvent(saved); setCategories(activeCategories); setMetadata(response); setPage(number);
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
  const reset = () => { setInputs(blank); setFilters({ ...blank }); setSort('relevance'); };
  return <DiscoveryScreen title="Meet your possible people.">
    <Text style={s.body}>{event ? `${eventTitle(event)} | ${event.city} | ${formatEventDate(event.event_date)}` : 'Vendors selected around your event needs.'}</Text>
    <View style={s.row}><Text style={s.badge}>APPROVED VENDORS ONLY</Text><Button label={showFilters ? 'Hide filters' : 'Filters'} variant="secondary" onPress={() => setShowFilters(!showFilters)} /></View>
    {showFilters && <View style={s.card}>
      <Text style={s.heading}>Refine your discovery</Text><Text style={s.body}>Category</Text>
      <View style={s.chips}><ChoiceChip label="All requested categories" selected={!inputs.category} onPress={() => setInput('category', '')} />{categories.map((item) => <ChoiceChip key={item.id} label={item.name} selected={inputs.category === String(item.id)} onPress={() => setInput('category', String(item.id))} />)}</View>
      <Text style={s.body}>Service</Text><View style={s.chips}><ChoiceChip label="All services" selected={!inputs.service} onPress={() => setInput('service', '')} />{matchServices.map((item) => <ChoiceChip key={item.value} label={item.label} selected={inputs.service === item.value} onPress={() => setInput('service', item.value)} />)}</View>
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
    {!loading && !error && !matches.length && <View style={s.card}><Text style={s.heading}>A little more room to look</Text><Text style={s.body}>No active approved vendors fit these choices yet. Try fewer filters, or adjust your event categories, city, or budget.</Text><Button label="Clear filters" variant="secondary" onPress={reset} /><Button label="Edit event" variant="secondary" onPress={() => router.push({ pathname: '/plan-event', params: { id } })} /></View>}
    {matches.map((vendor) => <View key={vendor.id} style={s.card}>
      {vendor.profile_image && <Image source={{ uri: vendor.profile_image }} accessibilityLabel={`${vendor.business_name} profile`} alt={`${vendor.business_name} profile`} style={{ width: 64, height: 64, borderRadius: 16 }} />}
      <Text style={s.badge}>Approved · {vendor.match_score}/100 match</Text><Text style={s.heading}>{vendor.business_name}</Text><Text style={s.body}>{vendor.city} · Serving {vendor.service_area}</Text><Text style={s.body} numberOfLines={3}>{vendor.description}</Text>
      <Text style={s.body}>{vendor.rating === null ? 'No verified reviews yet' : `${vendor.rating}/5 | ${vendor.review_count} verified Den reviews`}</Text>
      {vendor.matching_reasons.filter((reason) => reason.points > 0).map((reason) => <Text key={reason.code} style={s.body}>• {reason.label}</Text>)}
      {vendor.listings.map((listing) => <Text key={listing.id} style={s.body}>{listing.title} · {listing.price === null || listing.pricing_type === 'CONTACT_FOR_QUOTE' ? 'Contact for a quote' : `${listing.pricing_type === 'STARTING_FROM' ? 'From ' : ''}$${listing.price}${listing.pricing_type === 'HOURLY' ? '/hour' : ''}`}</Text>)}
      <Button label="View Profile" variant="secondary" onPress={() => { void Linking.openURL(vendor.profile_url).catch((cause: unknown) => setActionError(requestError(cause))); }} />
      <Button label={event?.saved_vendor_ids.includes(vendor.id) ? 'Saved · Remove' : 'Save'} loading={savingId === vendor.id} disabled={savingId !== null} onPress={() => void toggleSave(vendor)} />
    </View>)}
    {metadata?.next && <Button label="Load more vendors" variant="secondary" loading={loading} onPress={() => void load(page + 1)} />}
    {event && <Button label="Edit event answers" variant="secondary" onPress={() => router.push({ pathname: '/plan-event', params: { id } })} />}
  </DiscoveryScreen>;
}
