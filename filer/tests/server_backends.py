#-*- coding: utf-8 -*-
import time
import shutil
import os
from django.core.files.uploadedfile import SimpleUploadedFile
from django.http import HttpResponseNotModified, Http404
from django.test import TestCase
from django.utils.http import http_date
from filer import settings as filer_settings
from filer.models import File
from filer.server.backends.default import DefaultServer
from filer.server.backends.nginx import NginxXAccelRedirectServer
from filer.server.backends.xsendfile import ApacheXSendfileServer
from filer.tests.helpers import create_image
from filer.tests.utils import Mock


class BaseServerBackendTestCase(TestCase):
    def setUp(self):
        original_filename = 'myimage.jpg'
        file_obj = SimpleUploadedFile(
            name=original_filename,
            content=create_image().tostring(),
            content_type='image/jpeg')
        self.filer_file = File.objects.create(
            file=file_obj,
            original_filename=original_filename)
    def tearDown(self):
        # delete all the files
        for location in (
                filer_settings.FILER_PUBLICMEDIA_STORAGE.location,
                filer_settings.FILER_PUBLICMEDIA_THUMBNAIL_STORAGE.location,
                filer_settings.FILER_PUBLICMEDIA_FORMATS_STORAGE.location,
                filer_settings.FILER_PRIVATEMEDIA_STORAGE.location,
                filer_settings.FILER_PRIVATEMEDIA_THUMBNAIL_STORAGE.location,
                filer_settings.FILER_PRIVATEMEDIA_FORMATS_STORAGE.location):
            shutil.rmtree(location,ignore_errors=True)


class DefaultServerTestCase(BaseServerBackendTestCase):
    def test_normal(self):
        server = DefaultServer()
        request = Mock()
        request.META = {}
        response = server.serve(request, self.filer_file.file)
        self.assertTrue(response.has_header('Last-Modified'))

    def test_not_modified(self):
        server = DefaultServer()
        request = Mock()
        request.META = {'HTTP_IF_MODIFIED_SINCE': http_date(time.time())}
        response = server.serve(request, self.filer_file.file)
        self.assertTrue(isinstance(response, HttpResponseNotModified))

    def test_missing_file(self):
        server = DefaultServer()
        request = Mock()
        request.META = {}
        os.remove(self.filer_file.file.path)
        self.assertRaises(Http404, server.serve, *(request, self.filer_file.file))


class NginxServerTestCase(BaseServerBackendTestCase):
    def setUp(self):
        super(NginxServerTestCase, self).setUp()
        self.server = NginxXAccelRedirectServer(
            location='mylocation',
            nginx_location=filer_settings.FILER_PUBLICMEDIA_STORAGE.location,
        )

    def test_normal(self):
        request = Mock()
        request.META = {}
        response = self.server.serve(request, self.filer_file.file)
        headers = dict(response.items())
        self.assertTrue(response.has_header('X-Accel-Redirect'))
        self.assertTrue(headers['X-Accel-Redirect'].startswith(self.server.nginx_location))
        # make sure the file object was never opened (otherwise the whole delegating to nginx would kinda
        # be useless)
        self.assertTrue(self.filer_file.file.closed)


    def test_missing_file(self):
        """
        this backend should not even notice if the file is missing.
        """
        request = Mock()
        request.META = {}
        os.remove(self.filer_file.file.path)
        response = self.server.serve(request, self.filer_file.file)
        headers = dict(response.items())
        self.assertTrue(response.has_header('X-Accel-Redirect'))
        self.assertTrue(headers['X-Accel-Redirect'].startswith(self.server.nginx_location))
        self.assertTrue(self.filer_file.file.closed)


class XSendfileServerTestCase(BaseServerBackendTestCase):
    def setUp(self):
        super(XSendfileServerTestCase, self).setUp()
        self.server = ApacheXSendfileServer()

    def test_normal(self):
        request = Mock()
        request.META = {}
        response = self.server.serve(request, self.filer_file.file)
        headers = dict(response.items())
        self.assertTrue(response.has_header('X-Sendfile'))
        self.assertEqual(headers['X-Sendfile'], self.filer_file.file.path)
        # make sure the file object was never opened (otherwise the whole delegating to nginx would kinda
        # be useless)
        self.assertTrue(self.filer_file.file.closed)


    def test_missing_file(self):
        """
        this backend should not even notice if the file is missing.
        """
        request = Mock()
        request.META = {}
        os.remove(self.filer_file.file.path)
        response = self.server.serve(request, self.filer_file.file)
        headers = dict(response.items())
        self.assertTrue(response.has_header('X-Sendfile'))
        self.assertEqual(headers['X-Sendfile'], self.filer_file.file.path)
        # make sure the file object was never opened (otherwise the whole delegating to nginx would kinda
        # be useless)
        self.assertTrue(self.filer_file.file.closed)