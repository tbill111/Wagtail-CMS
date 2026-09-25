from django.db import migrations


def rename_homepage(apps, schema_editor):
    HomePage = apps.get_model("home.HomePage")
    HomePage.objects.filter(title="Home").update(title="Trang chủ", draft_title="Trang chủ")
    Site = apps.get_model("wagtailcore.Site")
    Site.objects.filter(is_default_site=True).update(site_name="SmartCRM")


class Migration(migrations.Migration):
    dependencies = [("home", "0002_create_homepage")]

    operations = [migrations.RunPython(rename_homepage, migrations.RunPython.noop)]
