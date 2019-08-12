#!/usr/bin/env python
"""A module for lazy instantiation of the GRR's Python API."""
from __future__ import absolute_import
from __future__ import division

from __future__ import print_function
from __future__ import unicode_literals

from grr_api_client import api


from grr_colab import flags

FLAGS = flags.FLAGS

_API = None  # type: api.GrrApi


def get():
  """Lazily returns the GRR API object."""
  global _API

  if _API is None:

    if not FLAGS.grr_http_api_endpoint:
      raise ValueError("HTTP API endpoint has not been specified.")
    if not FLAGS.grr_auth_api_user:
      raise ValueError("API user name has not been specified.")
    if not FLAGS.grr_auth_password:
      raise ValueError("API user password has not been specified.")
    auth = (FLAGS.grr_auth_api_user, FLAGS.grr_auth_password)
    _API = api.InitHttp(
        api_endpoint=FLAGS.grr_http_api_endpoint, auth=auth)

  return _API