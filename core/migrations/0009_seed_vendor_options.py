from django.db import migrations


def seed(apps, schema_editor):
    Tag = apps.get_model("core", "VendorTag")
    for kind, names in {
        "SERVICE": ["Event planning", "Balloon arches", "Floral decoration", "Backdrops", "Table decoration", "Makeup", "Hairstyling", "Photography", "Videography", "Catering", "Private chef", "Cakes and desserts", "Kids entertainment", "Rental items", "Delivery", "Setup", "Teardown"],
        "EVENT": ["Birthday", "Wedding", "Baby shower", "Bridal shower", "Gender reveal", "Corporate event", "Anniversary", "Graduation", "Religious event", "Kids party"],
    }.items():
        for name in names:
            Tag.objects.get_or_create(name=name, kind=kind)
    # Preserve existing locations and account contact details when upgrading.
    Profile = apps.get_model("core", "VendorProfile")
    Location = apps.get_model("core", "ServiceLocation")
    for profile in Profile.objects.select_related("user").all():
        profile.contact_first_name = profile.user.first_name
        profile.contact_last_name = profile.user.last_name
        profile.business_email = profile.user.email
        profile.save(update_fields=["contact_first_name", "contact_last_name", "business_email"])
        if profile.city.strip():
            Location.objects.get_or_create(name=profile.city.strip())
        for name in profile.service_area.split(","):
            if name.strip() and len(name.strip()) <= 100:
                location, _ = Location.objects.get_or_create(name=name.strip())
                profile.service_locations.add(location)


class Migration(migrations.Migration):
    dependencies = [("core", "0008_servicelocation_vendorprofile_business_address_and_more")]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
