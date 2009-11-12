from operator import attrgetter
import os
import pysvn
from sven.exc import *




class FSAccess(object):
    def __init__(self, checkout_dir):

        #if config_location and not config_location.startswith('/'):
        #    config_location = os.path.join(checkout_dir, config_location)

        #if config_location and config_location.endswith('/'):
        #    config_location = config_location.rstrip('/')

        #self.config_location = config_location or ''

        #os.chdir(checkout_dir)
        self.checkout_dir = checkout_dir

        #self.default_message = default_commit_message or "foom"


    def read(self, uri):
        """
        Return the raw @type:string data stored in @param:uri
        at @param:rev in some sort of ad-hoc JSON format.
        
        @raise:NotAFile
        @raise:NoSuchResource
        XXX TODO @raise additional information for edge cases of accessing
               a file at a revision when it did not yet exist, or a revision
               when it moved or ceased to exist.
        """
        uri = uri.strip('/')
        absolute_uri = '/'.join((self.checkout_dir, uri))

        try:
            return {'body': file(absolute_uri).read(),
                    'kind': None,
                    }
        except IOError, e:
            if e.errno == 21:
                raise NotAFile(uri)
            elif e.errno == 2:
                raise NoSuchResource(uri)
            raise

    def write(self, uri, contents):
        uri = uri.strip('/')
        absolute_uri = '/'.join((self.checkout_dir, uri))

        if os.path.isdir(absolute_uri): # we can't write to a directory
            raise NotAFile(uri)

        parent_dir = '/'.join(uri.split('/')[:-1])
        absolute_parent_dir = '/'.join((self.checkout_dir, parent_dir))

        if parent_dir and not os.path.exists(absolute_parent_dir):
            path = '/'.join(uri.split('/')[:-1])
            os.makedirs('/'.join((self.checkout_dir, path)))

            path = path.split('/')
            success = False
            for i in range(len(path)):
                root_to_add = '/'.join(path[:i+1])

        f = file(absolute_uri, 'w')
        print >> f, contents
        f.close()

if __name__ == '__main__':
    import doctest
    doctest.testfile('doctest.txt')
