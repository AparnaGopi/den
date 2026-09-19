export type Category = { id: number; name: string; slug: string };
export type EventType = 'WEDDING' | 'BIRTHDAY' | 'CORPORATE' | 'BABY_SHOWER' | 'ANNIVERSARY' | 'OTHER';
export type HelpType = 'FULL_PLANNING' | 'PARTIAL_PLANNING' | 'VENDORS_ONLY' | 'RENTALS' | 'PRODUCTS' | 'PLANNER' | 'DECORATOR' | 'COMPLETE_SERVICE' | 'RENTAL_ITEMS' | 'CATERING' | 'OTHER_SERVICES';
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
  rating: null;
  starting_price: string | null;
  created_at: string;
  listings: { id: number; title: string; listing_type: string; category: number | null; pricing_type: string; price: string | null }[];
};
export type MatchPage = Page<VendorMatch> & {
  rating_available: false;
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
  { value: 'PLANNER', label: 'Planner' }, { value: 'DECORATOR', label: 'Decorator' },
  { value: 'COMPLETE_SERVICE', label: 'Complete service' }, { value: 'RENTAL_ITEMS', label: 'Rental items only' },
  { value: 'CATERING', label: 'Catering' }, { value: 'OTHER_SERVICES', label: 'Other event services' },
];
export function eventTitle(event: EventRequest) {
  return event.event_type === 'OTHER' ? event.custom_event_type || 'Your event' : eventTypes.find((type) => type.value === event.event_type)?.label || 'Your event';
}
export function requestError(error: unknown) {
  return error instanceof Error ? error.message : 'We could not connect. Please try again.';
}
