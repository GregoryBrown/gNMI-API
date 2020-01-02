"""
Global Real Time Network Monitoring exception and warning classes.
"""


class Error(Exception):
    pass


class GetIndexListError(Error):
    """Error while doing a Get request against ES"""
    def __init__(self, code, response_json, message):
        self.code = code 
        self.response = response_json
        self.message = message


class PostDataError(Error):
    """Error Posting data to ES"""
    def	__init__(self, code, response_json, message):
        self.code = code
        self.response =	response_json
        self.message = message


class PutIndexError(Error):
    """Error Putting an index into ES"""
    def	__init__(self, code, response_json, index, message):
        self.code = code
        self.response =	response_json
        self.index = index
        self.message = message

