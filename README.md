Copyright © 2026 Aparna Gopi. All rights reserved.
# Den

Den is an event-planning platform with a shared Django REST API, a Django web portal for vendors and service providers, and a React Native Expo app planned for customers and event hosts.

The current milestone includes the Django web authentication flow and the versioned API authentication foundation. Listings, mood boards, payments, messaging, and the Expo app are not implemented yet.

## Local setup

1. Create and activate a virtual environment:

	```powershell
	python -m venv .venv
	.\.venv\Scripts\Activate.ps1
	```

2. Install Python dependencies:

	```powershell
	python -m pip install -r requirements.txt
	```

3. Apply migrations:

	```powershell
	python manage.py migrate
	```

4. Create an admin account when needed:

	```powershell
	python manage.py createsuperuser
	```

5. Run the Django server:

	```powershell
	python manage.py runserver
	```

Run the complete test suite with:

```powershell
python manage.py test
```

## API v1

The API is available under `/api/v1/`. Registration returns the created user and JWT access and refresh tokens. The public registration endpoints accept only the role assigned to that endpoint; administrator accounts can only be created through Django Admin.

### Endpoints

| Method | Endpoint | Authentication | Purpose |
| --- | --- | --- | --- |
| POST | `/api/v1/auth/register/customer/` | None | Register a customer |
| POST | `/api/v1/auth/register/vendor/` | None | Register a vendor |
| POST | `/api/v1/auth/login/` | None | Create access and refresh tokens |
| POST | `/api/v1/auth/token/refresh/` | None | Exchange a refresh token for an access token |
| GET | `/api/v1/auth/me/` | Bearer access token | Return the current user |

### Register

```http
POST /api/v1/auth/register/customer/
Content-Type: application/json

{
  "email": "host@example.com",
  "password": "a-strong-password-123",
  "first_name": "Alex",
  "last_name": "Host",
  "role": "customer"
}
```

Use the same payload with `"role": "vendor"` at the vendor registration endpoint. A role mismatch or `"role": "admin"` returns HTTP 400 with a field-level `role` error.

### Login

```http
POST /api/v1/auth/login/
Content-Type: application/json

{
  "email": "host@example.com",
  "password": "a-strong-password-123"
}
```

Use the returned access token on protected requests:

```http
GET /api/v1/auth/me/
Authorization: Bearer <access-token>
```

Successful user responses contain only the public identity fields needed by clients:

```json
{
  "id": 1,
  "email": "host@example.com",
  "first_name": "Alex",
  "last_name": "Host",
  "role": "customer"
}
```

In development, CORS is open because `DEBUG` is enabled. Restrict `CORS_ALLOW_ALL_ORIGINS` to an explicit allowlist before production deployment.
This is a [Next.js](https://nextjs.org) project bootstrapped with [`create-next-app`](https://nextjs.org/docs/app/api-reference/cli/create-next-app).

## Getting Started

First, run the development server:

```bash
npm run dev
# or
yarn dev
# or
pnpm dev
# or
bun dev
```

Open [http://localhost:3000](http://localhost:3000) with your browser to see the result.

You can start editing the page by modifying `app/page.tsx`. The page auto-updates as you edit the file.

This project uses [`next/font`](https://nextjs.org/docs/app/building-your-application/optimizing/fonts) to automatically optimize and load [Geist](https://vercel.com/font), a new font family for Vercel.

## Learn More

To learn more about Next.js, take a look at the following resources:

- [Next.js Documentation](https://nextjs.org/docs) - learn about Next.js features and API.
- [Learn Next.js](https://nextjs.org/learn) - an interactive Next.js tutorial.

You can check out [the Next.js GitHub repository](https://github.com/vercel/next.js) - your feedback and contributions are welcome!

## Deploy on Vercel

The easiest way to deploy your Next.js app is to use the [Vercel Platform](https://vercel.com/new?utm_medium=default-template&filter=next.js&utm_source=create-next-app&utm_campaign=create-next-app-readme) from the creators of Next.js.

Check out our [Next.js deployment documentation](https://nextjs.org/docs/app/building-your-application/deploying) for more details.


## Customer discovery and vendor milestone

Django serves the customer questionnaire at `/events/plan/`, results at
`/events/<id>/matches/`, and full vendor editing at `/vendor/profile/`.
The Expo application uses the same event records through `/api/v1/events/`
and the shared server matcher. Set `EXPO_PUBLIC_API_URL` to the reachable
Django origin plus `/api/v1` (use your computer's LAN address on a device).

Apply schema changes with `python manage.py migrate`. Vendors should edit
listings on the website and select **Services / tasks provided**. Existing
listings retain their data, but must explicitly declare planner, decorator,
catering, or complete service before matching those specific requests.
Rental requests continue to use the rental listing type. Availability is
vendor-provided text; matching does not promise availability on a given date.

Both results interfaces support category, service, location, price and
`rating_min` filters, with relevance, price, newest and rating sorting.
Only active approved vendors with active listings appear. Ratings average
verified Den reviews only; unrated vendors sort last and are excluded by a
minimum-rating filter. No Google reviews are imported.

Customers can submit a review using
`POST /api/v1/events/<id>/vendors/<vendor_id>/reviews/` with `rating` (1?5)
and `comment`. The event must belong to the customer, be in the past and
have that vendor saved. Submissions remain unverified until staff records
service-verification evidence in Django admin. Saving a vendor is not proof
of a booking. Customers and vendors cannot set verification or approval.

`GET/PATCH /api/v1/vendor/profile/` exposes only the signed-in vendor's basic
profile fields. Full services, products, prices, portfolio, tags, availability
and Google Business URL editing stays on the website. The mobile web button
opens the returned `full_profile_url`; the browser uses normal Django login.

Validation:

```sh
python manage.py check
python manage.py test
cd mobile
npm run lint
npm run typecheck
```


### Vendor onboarding (Django + Expo)

Run `python manage.py migrate` to apply the additive profile migration and seed
service/event tags. Existing category, logo (`profile_image`), cover, portfolio,
listing prices and free-text location/tag data are preserved. Existing account
contact details and service areas are copied into the new structured fields.
Admins manage categories, vendor tags and service locations in Django admin;
add cities/service areas there for the autocomplete and selection chips.

Vendors save drafts at `/vendor/profile/`, preview at `/vendor/profile/preview/`,
and explicitly submit for review. Admins can approve complete profiles, reject,
or request changes with `review_feedback`. Changes to company name, contact
identity, logo, primary category or business links requeue approved profiles.
Customer discovery continues to require approval. Business addresses are private
and never included in public profiles or the mobile profile response. No location
coordinates are collected.

The description button uses `templates/core/vendor_description.txt` and makes no
external AI request. Vendors can edit the resulting draft before saving. Uploads
accept verified JPEG, PNG and WebP files, up to 5 MB each (20 images per web batch).
Portfolio captions can be edited individually after a batch upload.

Expo uses the existing authenticated `/api/v1/vendor/profile/` endpoint plus
`vendor/options/` and `vendor/portfolio/`. Profile edits and portfolio mutations
are scoped to the authenticated vendor. The full web editor requires web login;
the mobile link does not transfer authentication tokens.

Media uses Django's local filesystem storage by default. For a future cloud
backend, install its Django storage package and configure `DEN_STORAGE_BACKEND`
and `DEN_STORAGE_OPTIONS` (a JSON object); credentials belong in deployment
configuration. Removed images are unlinked from profiles/listings; physical
orphan-file cleanup remains a storage maintenance task.

Validation: `python manage.py check`, `python manage.py test --noinput`, and,
from `mobile/`, `npm run lint` and `npm run typecheck`.
