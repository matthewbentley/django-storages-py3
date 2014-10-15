from django.conf import settings
from storages.backends.s3boto import S3BotoStorage

from boto.gs.connection import GSConnection, SubdomainCallingFormat
from boto.exception import GSResponseError

ACCESS_KEY_NAME = getattr(settings, 'GS_ACCESS_KEY_ID', None)
SECRET_KEY_NAME = getattr(settings, 'GS_SECRET_ACCESS_KEY', None)
HEADERS = getattr(settings, 'GS_HEADERS', {})
STORAGE_BUCKET_NAME = getattr(settings, 'GS_BUCKET_NAME', None)
AUTO_CREATE_BUCKET = getattr(settings, 'GS_AUTO_CREATE_BUCKET', False)
DEFAULT_ACL = getattr(settings, 'GS_DEFAULT_ACL', 'public-read')
BUCKET_ACL = getattr(settings, 'GS_BUCKET_ACL', DEFAULT_ACL)
QUERYSTRING_AUTH = getattr(settings, 'GS_QUERYSTRING_AUTH', True)
QUERYSTRING_EXPIRE = getattr(settings, 'GS_QUERYSTRING_EXPIRE', 3600)
REDUCED_REDUNDANCY = getattr(settings, 'GS_REDUCED_REDUNDANCY', False)
LOCATION = getattr(settings, 'GS_LOCATION', '')
CUSTOM_DOMAIN = getattr(settings, 'GS_CUSTOM_DOMAIN', None)
CALLING_FORMAT = getattr(settings, 'GS_CALLING_FORMAT', SubdomainCallingFormat())
SECURE_URLS = getattr(settings, 'GS_SECURE_URLS', True)
FILE_NAME_CHARSET = getattr(settings, 'GS_FILE_NAME_CHARSET', 'utf-8')
FILE_OVERWRITE = getattr(settings, 'GS_FILE_OVERWRITE', True)
FILE_BUFFER_SIZE = getattr(settings, 'GS_FILE_BUFFER_SIZE', 5242880)
IS_GZIPPED = getattr(settings, 'GS_IS_GZIPPED', False)
PRELOAD_METADATA = getattr(settings, 'GS_PRELOAD_METADATA', False)
GZIP_CONTENT_TYPES = getattr(settings, 'GS_GZIP_CONTENT_TYPES', (
    'text/css',
    'application/javascript',
    'application/x-javascript',
))
try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO  # noqa

from django.core.exceptions import ImproperlyConfigured

from storages.backends.s3boto import S3BotoStorage, S3BotoStorageFile
from storages.utils import setting

try:
    from boto.gs.connection import GSConnection, SubdomainCallingFormat
    from boto.exception import GSResponseError
    from boto.gs.key import Key as GSKey
except ImportError:
    raise ImproperlyConfigured("Could not load Boto's Google Storage bindings.\n"
                               "See https://github.com/boto/boto")


class GSBotoStorageFile(S3BotoStorageFile):

    def write(self, content):
        if 'w' not in self._mode:
            raise AttributeError("File was not opened in write mode.")
        self.file = StringIO(content)
        self._is_dirty = True

    def close(self):
        if self._is_dirty:
            provider = self.key.bucket.connection.provider
            upload_headers = {provider.acl_header: self._storage.default_acl}
            upload_headers.update(self._storage.headers)
            self._storage._save_content(self.key, self.file, upload_headers)
        self.key.close()


class GSBotoStorage(S3BotoStorage):
    connection_class = GSConnection
    connection_response_error = GSResponseError

    def __init__(self, bucket=STORAGE_BUCKET_NAME, access_key=None,
            secret_key=None, bucket_acl=BUCKET_ACL, acl=DEFAULT_ACL,
            headers=HEADERS, gzip=IS_GZIPPED,
            gzip_content_types=GZIP_CONTENT_TYPES,
            querystring_auth=QUERYSTRING_AUTH,
            querystring_expire=QUERYSTRING_EXPIRE,
            reduced_redundancy=REDUCED_REDUNDANCY,
            custom_domain=CUSTOM_DOMAIN, secure_urls=SECURE_URLS,
            location=LOCATION, file_name_charset=FILE_NAME_CHARSET,
            preload_metadata=PRELOAD_METADATA,
            calling_format=CALLING_FORMAT):
        super(GSBotoStorage, self).__init__(bucket=bucket,
            access_key=access_key, secret_key=secret_key,
            bucket_acl=bucket_acl, acl=acl, headers=headers, gzip=gzip,
            gzip_content_types=gzip_content_types,
            querystring_auth=querystring_auth,
            querystring_expire=querystring_expire,
            reduced_redundancy=reduced_redundancy,
            custom_domain=custom_domain, secure_urls=secure_urls,
            location=location, file_name_charset=file_name_charset,
            preload_metadata=preload_metadata, calling_format=calling_format)
    file_class = GSBotoStorageFile
    key_class = GSKey

    access_key_names = ['GS_ACCESS_KEY_ID']
    secret_key_names = ['GS_SECRET_ACCESS_KEY']

    access_key = setting('GS_ACCESS_KEY_ID')
    secret_key = setting('GS_SECRET_ACCESS_KEY')
    file_overwrite = setting('GS_FILE_OVERWRITE', True)
    headers = setting('GS_HEADERS', {})
    bucket_name = setting('GS_BUCKET_NAME', None)
    auto_create_bucket = setting('GS_AUTO_CREATE_BUCKET', False)
    default_acl = setting('GS_DEFAULT_ACL', 'public-read')
    bucket_acl = setting('GS_BUCKET_ACL', default_acl)
    querystring_auth = setting('GS_QUERYSTRING_AUTH', True)
    querystring_expire = setting('GS_QUERYSTRING_EXPIRE', 3600)
    durable_reduced_availability = setting('GS_DURABLE_REDUCED_AVAILABILITY', False)
    location = setting('GS_LOCATION', '')
    custom_domain = setting('GS_CUSTOM_DOMAIN')
    calling_format = setting('GS_CALLING_FORMAT', SubdomainCallingFormat())
    secure_urls = setting('GS_SECURE_URLS', True)
    file_name_charset = setting('GS_FILE_NAME_CHARSET', 'utf-8')
    is_gzipped = setting('GS_IS_GZIPPED', False)
    preload_metadata = setting('GS_PRELOAD_METADATA', False)
    gzip_content_types = setting('GS_GZIP_CONTENT_TYPES', (
        'text/css',
        'application/javascript',
        'application/x-javascript',
    ))
    url_protocol = setting('GS_URL_PROTOCOL', 'http:')

    def _save_content(self, key, content, headers):
        # only pass backwards incompatible arguments if they vary from the default
        options = {}
        if self.encryption:
            options['encrypt_key'] = self.encryption
        key.set_contents_from_file(content, headers=headers,
                                   policy=self.default_acl,
                                   rewind=True, **options)

    def _get_or_create_bucket(self, name):
        """
        Retrieves a bucket if it exists, otherwise creates it.
        """
        if self.durable_reduced_availability:
            storage_class = 'DURABLE_REDUCED_AVAILABILITY'
        else:
            storage_class = 'STANDARD'
        try:
            return self.connection.get_bucket(name,
                validate=self.auto_create_bucket)
        except self.connection_response_error:
            if self.auto_create_bucket:
                bucket = self.connection.create_bucket(name, storage_class=storage_class)
                bucket.set_acl(self.bucket_acl)
                return bucket
            raise ImproperlyConfigured("Bucket %s does not exist. Buckets "
                                       "can be automatically created by "
                                       "setting GS_AUTO_CREATE_BUCKET to "
                                       "``True``." % name)
