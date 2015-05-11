import os
import tempfile
from wsgiref.util import FileWrapper
import zipfile

from soil import DownloadBase
from django.http import StreamingHttpResponse
from django.views.generic import View
from corehq.util.view_utils import set_file_download
from soil.util import expose_download

CHUNK_SIZE = 8192
MULTIMEDIA_EXTENSIONS = ('.mp3', '.wav', '.jpg', '.png', '.gif', '.3gp', '.mp4', '.zip', )


def make_zip_tempfile(files, compress, download_id):
    compression = zipfile.ZIP_DEFLATED if compress else zipfile.ZIP_STORED
    fd, fpath = tempfile.mkstemp()
    with os.fdopen(fd, 'w') as tmp:
        with zipfile.ZipFile(tmp, "w") as z:
            for path, data in files:
                # don't compress multimedia files
                extension = os.path.splitext(path)[1]
                print "zipping: ", path
                file_compression = zipfile.ZIP_STORED if extension in MULTIMEDIA_EXTENSIONS else compression
                z.writestr(path, data, file_compression)
    # return fpath
    f = open(fpath, 'r')
    return expose_download(f.read(),
                           60 * 60 * 2,
                           mimetype='application/zip',
                           download_id=download_id,
                           content_disposition='attachment; filename="commcare.zip"'
                           )


class DownloadZip(View):
    compress_zip = None
    zip_name = None
    download_async = False

    @property
    def zip_mimetype(self):
        if self.compress_zip:
            return 'application/zip'
        else:
            return 'application/x-zip-compressed'

    def log_errors(self, errors):
        raise NotImplementedError()

    def iter_files(self):
        raise NotImplementedError()

    # def iter_files_async(self):
    #     raise NotImplementedError()

    def check_before_zipping(self):
        raise NotImplementedError()

    def _get_async(self, files, compress=True):
        from corehq.util.tasks import make_zip_tempfile_async
        download = DownloadBase()
        download.set_task(make_zip_tempfile_async.delay(
            list(files), compress=compress, download_id=download.download_id))
        return download.get_start_response()

    def get(self, request, *args, **kwargs):
        error_response = self.check_before_zipping()
        if error_response:
            return error_response

        files, errors = self.iter_files()
        if self.download_async:
            return self._get_async(files, compress=self.compress_zip)

        fpath = make_zip_tempfile(files, compress=self.compress_zip)
        if errors:
            self.log_errors(errors)

        response = StreamingHttpResponse(FileWrapper(open(fpath), CHUNK_SIZE), mimetype=self.zip_mimetype)
        response['Content-Length'] = os.path.getsize(fpath)
        set_file_download(response, self.zip_name)
        return response
