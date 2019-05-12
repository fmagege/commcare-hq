from __future__ import absolute_import
from __future__ import unicode_literals

from io import open
from celery.task import task

from corehq.apps.app_manager.dbaccessors import get_build_by_version
from corehq.apps.hqmedia.tasks import create_ccz_files
from corehq.apps.app_manager.dbaccessors import wrap_app
from custom.icds.models import CCZHosting


@task
def setup_ccz_file_for_hosting(ccz_hosting_id):
    try:
        ccz_hosting = CCZHosting.objects.get(pk=ccz_hosting_id)
    except CCZHosting.DoesNotExist:
        return
    version = ccz_hosting.version
    ccz_utility = ccz_hosting.utility
    # set up the file if not already present
    if not ccz_utility.file_exists():
        build = wrap_app(get_build_by_version(ccz_hosting.link.domain, ccz_hosting.app_id, version))
        ccz_file = create_ccz_files(build, ccz_hosting.profile_id)
        try:
            with open(ccz_file, 'rb') as ccz:
                ccz_utility.store_file_in_blobdb(ccz, name=ccz_hosting.file_name)
        except Exception as e:
            # delete the file from blob db if it was added but later failed
            ccz_utility.remove_file_from_blobdb()
            raise e