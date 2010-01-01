# based on sven.backend.SvnAccess behavior

class SvnPropMetadata(object):

    def __init__(self, client, checkout_dir):
        self.client = client
        self.checkout_dir = checkout_dir

    def _get(self, uri, key):
        return self.client.propget(key, uri)

    def get(self, uri, key):
        return self._get(uri, 'sven:' + key)

    def mimetype(self, uri):
        return self._get(uri, 'svn:mime-type')

    def _set(self, uri, key, val):
        return self.client.propset(key, uri, val)

    def set(self, uri, key, val):
        return self._set(uri, 'sven:' + key, val)

    def set_mimetype(self, uri, val):
        return self._get(uri, 'svn:mime-type', val)


# two:
/foo/greeb.txt
/foo/bar/baz.html
/.sven-meta/.mimetype/foo/bar/baz.html
/.sven-meta/.mimetype/foo/greeb.txt
/.sven-meta/.frabble/foo/bar/baz.html
/foo/.sven-meta/.mimetype
/foo/.sven-meta/.frabble
/foo/bar/.sven-meta/.mimetype

