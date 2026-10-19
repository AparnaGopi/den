# Vendor profiles and client conversations

The default vendor editor on web and mobile asks for company name, optional logo,
short description, services, city and work photos. Service choices come from the
same list used by customer refinement. Optional company details, guided setup and
manual packages remain available. Generated quote-based search entries never
overwrite existing packages or prices. Company identity or service changes on an
approved profile return it to review.

Customers start conversations from a vendor profile or mobile search result.
They choose whether to share an event. Vendors reply from Messages; customers
receive replies in their own Messages inbox. Only participants can access a
conversation. Removing an event search hides its shared event details.

Each vendor gets three distinct free client conversations for the lifetime of
the profile. A slot is used by the first vendor reply, not by a customer enquiry
or each message. Those three conversations remain free to continue. An active
subscription permits more clients; after expiry, additional conversations require
renewal while the three trial conversations stay available. The allowance check
and message write share a transaction and lock the vendor profile.

Payment collection is not connected. The subscription page records interest
without charging or activating access. For testing, staff can set an expiry on
Vendor chat subscriptions in Django admin. Clients cannot grant themselves access.
Connecting checkout requires a payment provider, plan price and verified payment
events before replacing this test entitlement flow.

Visit analytics show total visits, unique customers and visits over seven days.
Only signed-in customer profile views are counted; previews, vendors and anonymous
views are excluded. Viewer identities are not exposed to vendors.

Uploads use the existing configured Django storage backend. A live Render service
must use persistent media storage (for example, the existing S3 storage option) to
serve and retain uploaded photos. No payment, storage credentials or customer data
are included in this change.
