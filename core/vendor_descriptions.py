from django.template.loader import render_to_string


def description_draft(data):
    return render_to_string("core/vendor_description.txt", {"vendor": data}).strip()
