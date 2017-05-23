from celery.task import task
from corehq.apps.commtrack.consumption import recalculate_domain_consumption
from corehq.apps.locations.bulk_management import new_locations_import
from corehq.util.decorators import serial_task
from corehq.util.workbook_json.excel_importer import MultiExcelImporter
from django.conf import settings

LOCK_LOCATIONS_TIMEOUT = 60 * 60 * 10  # seconds


@serial_task('{domain}', default_retry_delay=5 * 60, timeout=LOCK_LOCATIONS_TIMEOUT, max_retries=12,
             queue=settings.CELERY_MAIN_QUEUE, ignore_result=False)
def import_locations_async(domain, file_ref_id):
    importer = MultiExcelImporter(import_locations_async, file_ref_id)
    results = new_locations_import(domain, importer)
    importer.mark_complete()

    return {
        'messages': results
    }


@task(ignore_result=True)
def recalculate_domain_consumption_task(domain):
    recalculate_domain_consumption(domain)


def location_lock_key(domain):
    # use the key generated by serial_task decorator of import_locations_async
    return "import_locations_async-{domain}".format(domain=domain)
