import csv
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from accounts.models import User
from core.models import Category, EventRequest, Listing, ServiceLocation, VendorProfile, VendorTag


HELP_TYPES = {
    "Florist": [EventRequest.HelpType.FLORIST],
    "Decorator": [EventRequest.HelpType.DECORATOR],
    "Balloon vendor": [EventRequest.HelpType.BALLOON_ARTIST],
    "Planner": [EventRequest.HelpType.EVENT_PLANNER],
    "Baker or dessert vendor": [EventRequest.HelpType.CAKE_DESSERTS],
    "Caterer or chef": [EventRequest.HelpType.CATERER, EventRequest.HelpType.PRIVATE_CHEF],
    "Food provider": [EventRequest.HelpType.CATERER],
    "Photographer": [EventRequest.HelpType.PHOTOGRAPHER],
    "Videographer": [EventRequest.HelpType.VIDEOGRAPHER],
    "DJ or musician": [EventRequest.HelpType.ENTERTAINMENT],
    "Makeup artist": [EventRequest.HelpType.MAKEUP_ARTIST],
    "Hairstylist": [EventRequest.HelpType.HAIRSTYLIST],
    "Venue": [EventRequest.HelpType.VENUE],
    "Kids activity or venue": [EventRequest.HelpType.KIDS_ENTERTAINMENT, EventRequest.HelpType.VENUE],
    "Rental vendor": [EventRequest.HelpType.RENTAL_ITEMS],
}

CATEGORY_MAP = {
    "Flowers and florals": "Bouquets",
    "Event decor and styling": "Table styling",
    "Balloons": "Balloon arches",
    "Event planning and coordination": "Event Planning",
    "Cakes and desserts": "Dessert tables",
    "Catering and private dining": "Buffet",
    "Food trucks and mobile catering": "Buffet",
    "Photography and videography": "Event coverage",
    "DJ and music": "DJs",
    "Makeup and beauty": "Guest makeup",
    "Hair styling": "Hairstyling",
    "Event venues": "Event venues",
    "Kids party activities": "Kids entertainment",
    "Event rentals": "Tables",
}

SERVICE_CATEGORY_MAP = {
    "Bouquets": "Bouquets",
    "Centerpieces": "Centrepieces",
    "Floral arches": "Floral arches",
    "Backdrop": "Backdrops",
    "Balloon garland": "Balloon garlands",
    "Table styling": "Table styling",
    "Balloon arch": "Balloon arches",
    "Full planning": "Full planning",
    "Day-of coordination": "Day-of coordination",
    "Dessert table": "Dessert tables",
    "Buffet": "Buffet",
    "Event photography": "Event coverage",
    "Family portraits": "Portraits",
    "Photo booth": "Photo booths",
    "Event videography": "Event coverage",
    "Highlights film": "Event coverage",
    "Live streaming": "Event coverage",
    "DJ": "DJs",
    "Dance lighting": "Lighting",
    "Party makeup": "Guest makeup",
    "Bridal makeup": "Bridal makeup",
    "Hair styling": "Hairstyling",
    "Event hair": "Hairstyling",
    "Updos": "Hairstyling",
    "Tables and chairs": "Tables",
    "Face painting": "Face painting",
    "Table rentals": "Tables",
    "Chair rentals": "Chairs",
    "Backdrop rental": "Backdrops",
}

SERVICE_TAG_ALIASES = {
    "Centerpieces": "Table decoration",
    "Floral arches": "Floral decoration",
    "Balloon garland": "Balloon arches",
    "Backdrop": "Backdrops",
    "Table styling": "Table decoration",
    "Full planning": "Event planning",
    "Vendor coordination": "Event planning",
    "Custom cake": "Cakes and desserts",
    "Cupcakes": "Cakes and desserts",
    "Dessert table": "Cakes and desserts",
    "Cookies": "Cakes and desserts",
    "Cake pops": "Cakes and desserts",
    "Buffet": "Catering",
    "Canapes": "Catering",
    "Food truck": "Catering",
    "Street food": "Catering",
    "Late-night snacks": "Catering",
    "Party makeup": "Makeup",
    "Bridal makeup": "Makeup",
    "Hair styling": "Hairstyling",
    "Event hair": "Hairstyling",
    "Updos": "Hairstyling",
    "Tables and chairs": "Rental items",
    "Indoor play": "Kids entertainment",
    "Birthday party": "Kids entertainment",
    "Kids activities": "Kids entertainment",
    "Craft workshop": "Kids entertainment",
    "Balloon twisting": "Kids entertainment",
    "Table rentals": "Rental items",
    "Chair rentals": "Rental items",
    "Backdrop rental": "Rental items",
}


class Command(BaseCommand):
    help = "Seed fictional Den demo vendors into the local development database."

    def add_arguments(self, parser):
        parser.add_argument(
            "--confirm-local",
            action="store_true",
            help="Confirm this import targets the local SQLite development database.",
        )

    def handle(self, *args, **options):
        self.check_local_database(options["confirm_local"])
        rows = self.read_rows()
        created = 0
        already_seeded = 0
        with transaction.atomic():
            categories = {item.name: item for item in Category.objects.filter(is_active=True)}
            for row in rows:
                primary_name = CATEGORY_MAP[row["category"]]
                primary_category = self.category(categories, primary_name, create_demo_category=True)
                help_types = HELP_TYPES[row["vendor_type"]]
                service_names = [value.strip() for value in row["specific_services"].split("|") if value.strip()]
                service_tags = [self.service_tag(value) for value in service_names]
                related_categories = []
                for service_name in service_names:
                    category_name = SERVICE_CATEGORY_MAP.get(service_name)
                    category = self.category(categories, category_name)
                    if category and category != primary_category and category not in related_categories:
                        related_categories.append(category)

                email = f"{row['test_id'].lower()}@example.test"
                slug = row["test_id"].lower()
                existing_user = User.objects.filter(email=email).first()
                slug_owner = VendorProfile.objects.filter(slug=slug).first()
                if existing_user or slug_owner:
                    self.verify_existing_demo(existing_user, slug_owner, row, email, slug, service_tags)
                    already_seeded += 1
                    continue

                user = User(email=email, role=User.Role.VENDOR, is_active=True)
                user.set_unusable_password()
                user.save()

                areas = [value.strip() for value in row["service_areas"].split("|") if value.strip()]
                description = f"DEMO TEST DATA. {row['description']}"
                profile = VendorProfile.objects.create(
                    user=user,
                    business_name=row["company_name"],
                    slug=slug,
                    primary_category=primary_category,
                    city=row["base_city"],
                    service_area=", ".join(areas),
                    areas_served=", ".join(areas),
                    short_description=description,
                    description=description,
                    tags=f"DEN DEMO {row['test_id']}",
                    is_active=True,
                    approval_status=VendorProfile.ApprovalStatus.APPROVED,
                )
                profile.additional_categories.set(related_categories[:3])
                profile.service_tags.set(service_tags)
                locations = [
                    ServiceLocation.objects.get_or_create(name=area)[0]
                    for area in areas
                ]
                profile.service_locations.set(locations)

                minimum = Decimal(row["price_min_cad"])
                maximum = Decimal(row["price_max_cad"])
                listing_type = Listing.ListingType.RENTAL if row["vendor_type"] == "Rental vendor" else Listing.ListingType.PACKAGE
                listing_title = f"{row['vendor_type']} event package"
                listing_description = (
                    f"DEMO TEST DATA. {row['description']} "
                    f"Specific services: {', '.join(service_names)}. "
                    f"Indicative package range: CAD ${minimum} to ${maximum}."
                )
                listing = Listing.objects.create(
                    profile=profile,
                    listing_type=listing_type,
                    title=listing_title,
                    category=primary_category,
                    description=listing_description,
                    pricing_type=Listing.PricingType.STARTING_FROM,
                    price=minimum,
                    help_types=help_types,
                    is_active=True,
                )
                listing.service_tags.set(service_tags)
                created += 1

        self.stdout.write(self.style.SUCCESS(
            f"Demo vendors created: {created}; already seeded: {already_seeded}; rows: {len(rows)}."
        ))

    def check_local_database(self, confirmed):
        configured_path = Path(str(settings.DATABASES["default"]["NAME"])).resolve()
        expected_path = (settings.BASE_DIR / "db.sqlite3").resolve()
        if not confirmed:
            raise CommandError("Pass --confirm-local to explicitly confirm the local seed target.")
        if not settings.DEBUG or not getattr(settings, "DEN_ALLOW_LOCAL_DEMO_VENDOR_SEED", False):
            raise CommandError("Demo vendor seeding requires DEBUG and DEN_ALLOW_LOCAL_DEMO_VENDOR_SEED=1.")
        if connection.vendor != "sqlite" or configured_path != expected_path:
            raise CommandError("Demo vendor seeding is restricted to the project-local SQLite db.sqlite3.")

    def read_rows(self):
        path = settings.BASE_DIR / "core" / "den_approved_demo_vendors.csv"
        try:
            with path.open(encoding="utf-8-sig", newline="") as source:
                reader = csv.DictReader(source)
                required = {
                    "test_id", "company_name", "vendor_type", "category", "specific_services",
                    "base_city", "service_areas", "price_min_cad", "price_max_cad",
                    "description", "approval_status", "is_test_data",
                }
                if not reader.fieldnames or not required.issubset(reader.fieldnames):
                    raise CommandError("Demo CSV is missing required columns.")
                rows = list(reader)
        except OSError as error:
            raise CommandError(f"Could not read demo CSV: {error}") from error

        seen_ids = set()
        for row in rows:
            test_id = row["test_id"].strip()
            if not test_id.startswith("DEN-DEMO-") or test_id in seen_ids:
                raise CommandError(f"Invalid or duplicate demo test_id: {test_id}")
            seen_ids.add(test_id)
            if row["is_test_data"].strip().lower() != "true" or row["approval_status"].strip().lower() != "approved":
                raise CommandError(f"Refusing non-test or non-approved row: {test_id}")
            if row["vendor_type"] not in HELP_TYPES or row["category"] not in CATEGORY_MAP:
                raise CommandError(f"No Den mapping exists for row: {test_id}")
            try:
                minimum = Decimal(row["price_min_cad"])
                maximum = Decimal(row["price_max_cad"])
            except InvalidOperation as error:
                raise CommandError(f"Invalid price for row: {test_id}") from error
            if minimum < 0 or maximum < minimum:
                raise CommandError(f"Invalid price range for row: {test_id}")
        if not rows:
            raise CommandError("Demo CSV contains no rows.")
        return rows

    @staticmethod
    def category(categories, name, create_demo_category=False):
        if not name:
            return None
        category = categories.get(name)
        if category is None and create_demo_category and name in {"Event venues", "Kids entertainment"}:
            service_group = Category.ServiceGroup.RENTALS if name == "Event venues" else Category.ServiceGroup.ENTERTAINMENT
            category, _ = Category.objects.get_or_create(
                name=name,
                defaults={
                    "slug": "event-venues" if name == "Event venues" else "kids-entertainment",
                    "service_group": service_group,
                    "relevant_help_types": [
                        EventRequest.HelpType.VENUE if name == "Event venues" else EventRequest.HelpType.KIDS_ENTERTAINMENT,
                    ],
                    "is_featured": True,
                },
            )
            categories[name] = category
        if category is None:
            raise CommandError(f"Required active Den category is missing: {name}")
        return category

    @staticmethod
    def service_tag(name):
        canonical_name = SERVICE_TAG_ALIASES.get(name, name)
        tag, _ = VendorTag.objects.get_or_create(
            name=canonical_name,
            kind=VendorTag.Kind.SERVICE,
            defaults={"is_active": True},
        )
        if not tag.is_active:
            raise CommandError(f"Required service tag is inactive: {canonical_name}")
        return tag

    @staticmethod
    def verify_existing_demo(user, slug_owner, row, email, slug, service_tags):
        profile = VendorProfile.objects.filter(user=user).first() if user else None
        marker = f"DEN DEMO {row['test_id']}"
        if (
            not user or not profile or not slug_owner or slug_owner.pk != profile.pk
            or user.role != User.Role.VENDOR
            or profile.slug != slug
            or profile.business_name != row["company_name"]
            or profile.tags != marker
            or not user.is_active
            or not profile.is_active
            or profile.approval_status != VendorProfile.ApprovalStatus.APPROVED
        ):
            raise CommandError(f"Demo identity collision; refusing to modify existing data for {row['test_id']}.")
        listing = profile.listings.filter(title=f"{row['vendor_type']} event package").first()
        if not listing or set(listing.service_tags.values_list("pk", flat=True)) != {tag.pk for tag in service_tags}:
            raise CommandError(f"Existing demo listing differs from CSV; refusing to modify {email}.")