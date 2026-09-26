export type Category = {
  id: number; name: string; slug: string; service_group: string; service_group_label: string;
  relevant_help_types: HelpType[]; is_featured: boolean;
};
export type EventType = 'WEDDING' | 'BIRTHDAY' | 'CORPORATE' | 'BABY_SHOWER' | 'ANNIVERSARY' | 'OTHER';
export type HelpType = 'EVENT_PLANNER' | 'EVENT_COORDINATOR' | 'DECORATOR' | 'FLORIST' | 'BALLOON_ARTIST' | 'MAKEUP_ARTIST' | 'HAIRSTYLIST' | 'CATERER' | 'PRIVATE_CHEF' | 'PHOTOGRAPHER' | 'VIDEOGRAPHER' | 'ENTERTAINMENT' | 'KIDS_ENTERTAINMENT' | 'CAKE_DESSERTS' | 'VENUE' | 'RENTAL_ITEMS' | 'DELIVERY_PICKUP' | 'SETUP_TEARDOWN' | 'FULL_PLANNING' | 'OTHER' | 'PARTIAL_PLANNING' | 'VENDORS_ONLY' | 'RENTALS' | 'PRODUCTS' | 'PLANNER' | 'COMPLETE_SERVICE' | 'CATERING' | 'OTHER_SERVICES';
export type VenueType = 'INDOOR' | 'OUTDOOR' | 'UNDECIDED';
export type EventRequest = {
  id: number;
  event_type: EventType | '';
  custom_event_type: string;
  event_date: string | null;
  city: string;
  postal_code: string;
  guest_count: number | null;
  budget_min: string | null;
  budget_max: string | null;
  help_types: HelpType[];
  other_help_text: string;
  required_categories: number[];
  theme: string;
  colours: string[];
  venue_type: VenueType;
  notes: string;
  status: 'DRAFT' | 'READY' | 'ARCHIVED';
  completed_step: number;
  saved_vendor_ids: number[];
  created_at: string;
  updated_at: string;
};
export type EventLocation = {
  id: string;
  label: string;
  canonical_id: string;
  canonical_label: string;
  aliases: string[];
};
export type Page<T> = { count: number; next: string | null; previous: string | null; results: T[] };
export type VendorMatch = {
  id: number;
  business_name: string;
  slug: string;
  city: string;
  service_area: string;
  description: string;
  profile_image: string | null;
  approval_status: 'APPROVED';
  profile_url: string;
  match_score: number;
  matching_reasons: { code: string; points: number; label: string }[];
  rating: number | null;
  review_count: number;
  starting_price: string | null;
  created_at: string;
  listings: { id: number; title: string; listing_type: string; category: number | null; pricing_type: string; price: string | null }[];
};
export type MatchPage = Page<VendorMatch> & {
  rating_available: boolean;
  requested_sort: string;
  applied_sort: string;
  matching_version: number;
  price_note: string;
};
export const eventTypes: { value: EventType; label: string }[] = [
  { value: 'WEDDING', label: 'Wedding' }, { value: 'BIRTHDAY', label: 'Birthday' },
  { value: 'CORPORATE', label: 'Corporate event' }, { value: 'BABY_SHOWER', label: 'Baby shower' },
  { value: 'ANNIVERSARY', label: 'Anniversary' }, { value: 'OTHER', label: 'Something else' },
];
export const helpTypes: { value: HelpType; label: string }[] = [
  { value: 'EVENT_PLANNER', label: 'Event planner' }, { value: 'EVENT_COORDINATOR', label: 'Event coordinator' },
  { value: 'DECORATOR', label: 'Decorator' }, { value: 'FLORIST', label: 'Florist' },
  { value: 'BALLOON_ARTIST', label: 'Balloon artist' }, { value: 'MAKEUP_ARTIST', label: 'Makeup artist' },
  { value: 'HAIRSTYLIST', label: 'Hairstylist' }, { value: 'CATERER', label: 'Caterer' },
  { value: 'PRIVATE_CHEF', label: 'Private chef' }, { value: 'PHOTOGRAPHER', label: 'Photographer' },
  { value: 'VIDEOGRAPHER', label: 'Videographer' }, { value: 'ENTERTAINMENT', label: 'DJ / live entertainment' },
  { value: 'KIDS_ENTERTAINMENT', label: "Kids' party entertainment" }, { value: 'CAKE_DESSERTS', label: 'Cake / desserts' },
  { value: 'VENUE', label: 'Venue' }, { value: 'RENTAL_ITEMS', label: 'Decor / equipment rentals' },
  { value: 'DELIVERY_PICKUP', label: 'Delivery / pickup' }, { value: 'SETUP_TEARDOWN', label: 'Setup / teardown' },
  { value: 'FULL_PLANNING', label: 'Full-service planning' }, { value: 'OTHER', label: 'Other — please specify' },
];
export const legacyHelpTypes: { value: HelpType; label: string }[] = [
  { value: 'PARTIAL_PLANNING', label: 'Some planning help' }, { value: 'VENDORS_ONLY', label: 'Find vendors' },
  { value: 'RENTALS', label: 'Rentals' }, { value: 'PRODUCTS', label: 'Products' },
  { value: 'PLANNER', label: 'Planner' }, { value: 'COMPLETE_SERVICE', label: 'Complete service' },
  { value: 'CATERING', label: 'Catering' }, { value: 'OTHER_SERVICES', label: 'Other event services' },
];
export function eventTitle(event: EventRequest) {
  return event.event_type === 'OTHER' ? event.custom_event_type || 'Your event' : eventTypes.find((type) => type.value === event.event_type)?.label || 'Your event';
}
export function formatEventDate(value: string | null) {
  if (!value) return 'Date to come';
  const [year, month, day] = value.split('-').map(Number);
  if (!year || !month || !day) return value;
  return new Intl.DateTimeFormat('en-US', { month: 'short', day: 'numeric', year: 'numeric', timeZone: 'UTC' })
    .format(new Date(Date.UTC(year, month - 1, day)));
}
export function torontoDateIso(now = new Date()) {
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'America/Toronto', year: 'numeric', month: '2-digit', day: '2-digit',
  }).formatToParts(now);
  const part = (type: string) => parts.find((item) => item.type === type)?.value || '';
  return `${part('year')}-${part('month')}-${part('day')}`;
}
export function dateFromIso(value: string) {
  const [year, month, day] = value.split('-').map(Number);
  return new Date(year, month - 1, day);
}
export function isoFromPickerDate(value: Date) {
  return `${value.getFullYear()}-${String(value.getMonth() + 1).padStart(2, '0')}-${String(value.getDate()).padStart(2, '0')}`;
}
export function tomorrowPickerDate(now = new Date()) {
  const [year, month, day] = torontoDateIso(now).split('-').map(Number);
  const tomorrow = new Date(Date.UTC(year, month - 1, day + 1));
  return new Date(tomorrow.getUTCFullYear(), tomorrow.getUTCMonth(), tomorrow.getUTCDate());
}
export function requestError(error: unknown) {
  return error instanceof Error ? error.message : 'We could not connect. Please try again.';
}
