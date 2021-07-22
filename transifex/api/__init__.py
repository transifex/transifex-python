import time

import transifex

from .jsonapi import JsonApi
from .jsonapi import Resource as JsonApiResource
from .jsonapi.exceptions import JsonApiException


class DownloadMixin(object):
    """ Mixin that offers a download method for Transifex APIv3. """

    @classmethod
    def download(cls, interval=5, *args, **kwargs):
        """ Create and poll an async download. Return the download URL when
            done.
        """

        download = cls.create(*args, **kwargs)
        while True:
            if hasattr(download, 'errors') and len(download.errors) > 0:
                errors = [{'code': e['code'],
                           'detail': e['detail'],
                           'title': e['detail'],
                           'status': '409'}
                          for e in download.errors]
                raise JsonApiException(409, errors)
            if download.redirect:
                return download.redirect
            time.sleep(interval)
            download.reload()


class TransifexApi(JsonApi):
    HOST = "https://rest.api.transifex.com"
    HEADERS = {
        'User-Agent': "Transifex-API-SDK/{}".format(transifex.__version__),
    }


@TransifexApi.register
class Organization(JsonApiResource):
    TYPE = "organizations"


@TransifexApi.register
class Team(JsonApiResource):
    TYPE = "teams"


@TransifexApi.register
class Project(JsonApiResource):
    TYPE = "projects"


@TransifexApi.register
class Language(JsonApiResource):
    TYPE = "languages"


@TransifexApi.register
class Resource(JsonApiResource):
    TYPE = "resources"

    def purge(self):
        count = 0
        # Instead of filter, if Resource had a plural relationship to
        # ResourceString, we could do `self.fetch('resource_strings')`
        for page in list(self.API.ResourceString.
                         filter(resource=self).
                         all_pages()):
            count += len(page)
            self.API.ResourceString.bulk_delete(page)
        return count


@TransifexApi.register
class ResourceString(JsonApiResource):
    TYPE = "resource_strings"


@TransifexApi.register
class ResourceTranslation(JsonApiResource):
    TYPE = "resource_translations"
    EDITABLE = ["strings", 'reviewed', "proofread"]


@TransifexApi.register
class ResourceStringsAsyncUpload(JsonApiResource):
    TYPE = "resource_strings_async_uploads"

    @classmethod
    def upload(cls, resource, content, interval=5):
        """ Upload source content with multipart/form-data.

            :param resource: A (transifex) Resource instance or ID
            :param content: A string or file-like object
            :param interval: How often (in seconds) to poll for the completion
                             of the upload job
        """

        if isinstance(resource, JsonApiResource):
            resource = resource.id

        upload = cls.create_with_form(data={'resource': resource},
                                      files={'content': content})

        while True:
            if hasattr(upload, 'errors') and len(upload.errors) > 0:
                errors = [{
                    'code': e['code'],
                    'detail': e['detail'],
                    'title': e['detail'],
                    'status': '409'} for e in upload.errors]
                raise JsonApiException(409, errors)

            if upload.redirect:
                return upload.follow()
            if (hasattr(upload, 'attributes')
                    and upload.attributes.get("details")):
                return upload.attributes.get("details")

            time.sleep(interval)
            upload.reload()


@TransifexApi.register
class ResourceTranslationsAsyncUpload(JsonApiResource):
    TYPE = "resource_translations_async_uploads"

    @classmethod
    def upload(cls, resource, content, language, interval=5,
               file_type='default'):
        """ Upload translation content with multipart/form-data.

            :param resource: A (transifex) Resource instance or ID
            :param content: A string or file-like object
            :param language: A (transifex) Language instance or ID
            :param interval: How often (in seconds) to poll for the completion
                             of the upload job
            :param file_type: The content file type
        """

        if isinstance(resource, JsonApiResource):
            resource = resource.id

        upload = cls.create_with_form(data={'resource': resource,
                                            'language': language,
                                            'file_type': file_type},
                                      files={'content': content})

        while True:
            if hasattr(upload, 'errors') and len(upload.errors) > 0:
                errors = [{
                    'code': e['code'],
                    'detail': e['detail'],
                    'title': e['detail'],
                    'status': '409'} for e in upload.errors]
                raise JsonApiException(409, errors)

            if upload.redirect:
                return upload.follow()
            if (hasattr(upload, 'attributes')
                    and upload.attributes.get("details")):
                return upload.attributes.get("details")

            time.sleep(interval)
            upload.reload()


@TransifexApi.register
class User(JsonApiResource):
    TYPE = "users"


@TransifexApi.register
class TeamMembership(JsonApiResource):
    TYPE = "team_memberships"


@TransifexApi.register
class ResourceLanguageStats(JsonApiResource):
    TYPE = "resource_language_stats"


@TransifexApi.register
class ResourceStringsAsyncDownload(JsonApiResource, DownloadMixin):
    TYPE = "resource_strings_async_downloads"


@TransifexApi.register
class ResourceTranslationsAsyncDownload(JsonApiResource, DownloadMixin):
    TYPE = "resource_translations_async_downloads"


@TransifexApi.register
class I18nFormat(JsonApiResource):
    TYPE = "i18n_formats"


# This is our global object
transifex_api = TransifexApi()
