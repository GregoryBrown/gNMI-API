"""
.. module:: errors
   :platform: Unix, Windows
   :synopsis: Global error classes for gNMIP-API

.. moduleauthor:: Greg Brown <gsb5067@gmail.com>


"""


class GNMIException(Exception):
    """ Exception for GNMI API Errors """

    pass


class ElasticSearchUploaderException(Exception):
    """ Exception for ElasticSearchUploader Errors """

    pass
