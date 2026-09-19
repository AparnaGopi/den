from django.db import migrations, models


def migrate_approval_status(apps, schema_editor):
    profiles = apps.get_model("core", "VendorProfile").objects.using(schema_editor.connection.alias)
    profiles.filter(is_approved=True).update(approval_status="APPROVED")
    profiles.filter(is_approved=False).update(approval_status="PENDING")


def restore_approval_flag(apps, schema_editor):
    profiles = apps.get_model("core", "VendorProfile").objects.using(schema_editor.connection.alias)
    profiles.update(is_approved=False)
    profiles.filter(approval_status="APPROVED").update(is_approved=True)


class Migration(migrations.Migration):
    dependencies = [("core", "0003_category_remove_vendorprofile_category_and_more")]
    operations = [
        migrations.AddField(
            model_name="vendorprofile",
            name="approval_status",
            field=models.CharField(max_length=20, choices=[("DRAFT", "Draft"), ("PENDING", "Pending"), ("APPROVED", "Approved"), ("REJECTED", "Rejected")], default="DRAFT"),
        ),
        migrations.RunPython(migrate_approval_status, restore_approval_flag),
        migrations.RemoveField(model_name="vendorprofile", name="is_approved"),
    ]
