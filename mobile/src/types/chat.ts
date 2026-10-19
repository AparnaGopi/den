export type ChatPlan = { active: boolean; active_until: string | null; free_clients_used: number; free_clients_remaining: number; free_clients_limit: number; requested: boolean };
export type VisitStats = { total_views: number; unique_customers: number; last_7_days: number };
export type Conversation = { id: number; vendor_id: number; title: string; updated_at: string; unread_count: number; can_reply: boolean; event: { event_type: string; date: string | null; city: string; guests: number | null; budget_min: string | null; budget_max: string | null; notes: string } | null };
export type Message = { id: number; body: string; mine: boolean; created_at: string; read_at: string | null };
export type Thread = { conversation: Conversation; messages: Message[]; next_before: number | null };
export type QuickProfile = {
  id: number; business_name: string; short_description: string; city: string; help_types: string[]; other_services: string;
  service_locations: number[]; logo_url: string | null; photos: { id: number; url: string }[];
  approval_status: string; review_feedback: string;
  help_choices: { value: string; label: string }[]; location_choices: { id: number; name: string }[];
};
