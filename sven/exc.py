"""
'sven.exc': svn-related exceptions
"""

class NotAFile(IOError):
    def __init__(self, uri):
        IOError.__init__(self, 21, "Is a directory", uri)

class NotADirectory(IOError):
    def __init__(self, uri):
        IOError.__init__(self, 20, "Not a directory", uri)

class NoSuchResource(IOError):
    def __init__(self, uri):
        IOError.__init__(self, 2, "No such file or directory", uri)

class ResourceUnchanged(Exception):
    def __init__(self, uri, last_change):
        Exception.__init__(self, "Resource '%s' unchanged since %d" % (uri, last_change))
        self.last_change = last_change

class ResourceChanged(Exception):
    def __init__(self, uri):
        Exception.__init__(self, "Resource '%s' is out of date" % uri)
