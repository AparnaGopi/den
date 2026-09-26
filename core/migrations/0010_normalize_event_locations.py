from django.db import migrations


LOCATION_LABELS = {
    "toronto": "Toronto",
    "ajax": "Ajax",
    "brock": "Brock",
    "clarington": "Clarington",
    "oshawa": "Oshawa",
    "pickering": "Pickering",
    "scugog": "Scugog",
    "uxbridge": "Uxbridge",
    "whitby": "Whitby",
    "burlington": "Burlington",
    "halton hills": "Halton Hills",
    "halton-hills": "Halton Hills",
    "milton": "Milton",
    "oakville": "Oakville",
    "brampton": "Brampton",
    "caledon": "Caledon",
    "mississauga": "Mississauga",
    "aurora": "Aurora",
    "east gwillimbury": "East Gwillimbury",
    "east-gwillimbury": "East Gwillimbury",
    "georgina": "Georgina",
    "king": "King",
    "markham": "Markham",
    "newmarket": "Newmarket",
    "richmond hill": "Richmond Hill",
    "richmond-hill": "Richmond Hill",
    "vaughan": "Vaughan",
    "whitchurch-stouffville": "Whitchurch-Stouffville",
    "north york": "North York",
    "north-york": "North York",
    "scarborough": "Scarborough",
    "etobicoke": "Etobicoke",
    "east york": "East York",
    "east-york": "East York",
    "york (toronto)": "York (Toronto)",
    "york-toronto": "York (Toronto)",
}


def normalize_known_locations(apps, schema_editor):
    EventRequest = apps.get_model("core", "EventRequest")
    database = schema_editor.connection.alias
    for event in EventRequest.objects.using(database).only("pk", "city").iterator():
        normalized = " ".join(event.city.casefold().split())
        friendly_label = LOCATION_LABELS.get(normalized)
        if friendly_label and event.city != friendly_label:
            EventRequest.objects.using(database).filter(pk=event.pk).update(city=friendly_label)


class Migration(migrations.Migration):
    dependencies = [("core", "0009_seed_vendor_options")]
    operations = [migrations.RunPython(normalize_known_locations, migrations.RunPython.noop)]