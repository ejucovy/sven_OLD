from operator import attrgetter
import os
from bzrlib import workingtree
from bzrlib.errors import NoSuchRevision
from bzrlib.inventory import InventoryDirectory
from sven.exc import *

# >>> x=workingtree.WorkingTree.open('bar')
# >>> x.branch.lock_read()
# >>> [x.branch.revision_id_to_revno(a) for a in x.[x.path2id('bar')]]
# [1, 2]

# x = BzrAccess('bar').client

# much help from http://code.google.com/p/django-rcsfield/source/browse/trunk/rcsfield/backends/bzr.py

class BzrAccess(object):
    def __init__(self, checkout_dir,
                 config_location=None,
                 default_commit_message=None,
                 path_fixer=None):

        if config_location and not config_location.startswith('/'):
            config_location = os.path.join(checkout_dir, config_location)

        if config_location and config_location.endswith('/'):
            config_location = config_location.rstrip('/')

        self.config_location = config_location or ''

        #os.chdir(checkout_dir)
        self.checkout_dir = checkout_dir

        self.default_message = default_commit_message or "foom"

        self.path_fixer = path_fixer

    def normalized(self, path):
        """
        normalizes a path

        >>> normalized('/my/path/') == normalized('my/path') == 'my/path'
        True

        optionally a `path_fixer` may be applied, if set on the class. 
        the path will still be guaranteed to have no leading or trailing slashes.
        """
        path = path.strip('/')
        if self.path_fixer:
            path = self.path_fixer(path)
        return path.strip('/')

    @property
    def client(self):
        client = workingtree.WorkingTree.open(self.checkout_dir)
        return client

    def revisions(self, uri):
        """
        revisions at which this file changed
        """
        uri = self.normalized(uri)

        x = self.client

        path = x.path2id(uri)
        if not path:
            raise NoSuchResource(uri)

        ids = x.branch.repository.all_revision_ids()        
        x.branch.lock_read()
        try:
            changes = x.branch.repository.fileids_altered_by_revision_ids(ids)
        finally:
            x.branch.unlock()

        if path not in changes:
            return None

        changes = changes[path]
        changes = [x.branch.revision_id_to_revno(a) for a in changes]
        return list(sorted(changes, reverse=True))

    def last_changed_rev(self, uri, rev=None):
        uri = self.normalized(uri)

        changes = self.revisions(uri)

        if not changes:
            return None

        if rev is None:
            return changes[0]
        
        for revno in changes:
            if rev < revno:
                continue
            return revno

    def read(self, uri, rev=None):
        """
        Return the raw @type:string data stored in @param:uri
        at @param:rev in some sort of ad-hoc JSON format.
        
        @raise:NotAFile
        @raise:NoSuchResource
        @raise:ResourceUnchanged
        XXX TODO @raise additional information for edge cases of accessing
               a file at a revision when it did not yet exist, or a revision
               when it moved or ceased to exist.
        """
        uri = self.normalized(uri)
                
        x = self.client

        if rev is not None:            
            try:
                rev_id = x.branch.get_rev_id(int(rev))
            except NoSuchRevision, e:
                raise NoSuchResource(uri)
            x = x.branch.repository.revision_tree(rev_id)

        path = x.path2id(uri)
        if not path:
            raise NoSuchResource(uri)

        if rev is not None:
            last_change = self.last_changed_rev(uri, rev=rev)
            if last_change < rev:
                raise ResourceUnchanged(uri, last_change)

        x.lock_read()
        try:
            data = x.get_file(path)
        except IOError, e:
            if e.errno == 21:
                raise NotAFile(uri)
        finally:
            x.unlock()

        data = data.read()
        return dict(body=data, kind=None)


    def ls(self, uri, rev=None):
        """
        Return the listing of contents stored under @param:uri
        as a JSON-listing.

        @raise:NotADirectory
        @raise:ResourceUnchanged
        etc.
        """
                
        x = self.client

        uri = self.normalized(uri)

        if rev is not None:
            rev_id = x.branch.get_rev_id(int(rev))
            x = x.branch.repository.revision_tree(rev_id)

        x.lock_read()
        try:
            inv = x.inventory
        finally:
            x.unlock()

        path = x.path2id(uri)
        dir = inv[path]

        if type(dir) is not InventoryDirectory:
            raise NotADirectory(uri)

        if rev is not None:
            last_change = self.last_changed_rev(uri, rev=rev)
            if last_change < rev:
                raise ResourceUnchanged(uri, last_change)

        return ["%s/%s" % (uri, key) for key in dir.children.keys()]

    def log(self, uri, rev=None):
        """
        Return the changelog of data stored at or under @param:uri
        as of time @param:rev in JSON-listing format.
        
        @raise:ResourceUnchanged
        etc.
        """

        uri = self.normalized(uri)
        absolute_uri = '/'.join((self.checkout_dir, uri))

        if rev is not None:
            last_change = self.last_changed_rev(uri, rev)
            if last_change < int(rev):
                raise ResourceUnchanged(uri, last_change)

            rev = pysvn.Revision(pysvn.opt_revision_kind.number, rev)
            try:
                log = self.client.log(absolute_uri, rev,
                                      discover_changed_paths=True)
            except pysvn.ClientError, e:
                if e[1][0][1] == 150004: # has no URL
                    raise NoSuchResource(uri)
                raise
        else:
            try:
                log = self.client.log(absolute_uri,
                                      discover_changed_paths=True)
            except pysvn.ClientError, e:
                if e[1][0][1] == 200005: # not under version control
                    raise NoSuchResource(uri)
                raise

        globs = []
        for obj in log:
            href = obj.changed_paths[0].path
            glob = dict(href=href)
            fields = {'id': href,
                      'message': obj.message,
                      'author': obj.author,
                      'version': obj.revision.number}
            glob['fields'] = fields
            globs.append(glob)
        return globs

    def kind(self, uri):
        uri = self.normalized(uri)
        absolute_uri = '/'.join((self.checkout_dir, uri))

        try:
            properties = self.client.propget('svn:mime-type', absolute_uri)
        except pysvn.ClientError, e:
            if e[1][0][1] == 150000: # not under version control
                return ""
            if e[1][0][1] == 200005: # not under version control
                return ""
            if e[1][0][1] == 155007: # not a working copy
                return ""
            raise
    
        return properties.get(absolute_uri)

    def set_kind(self, uri, kind, msg=None):

        uri = self.normalized(uri)
        absolute_uri = '/'.join((self.checkout_dir, uri))

        self.client.propset('svn:mime-type', kind, absolute_uri)
        
        if not msg:
            msg = "Set svn:mime-type property to '%s'" % kind
        commit_rev = self.client.checkin([absolute_uri], msg)

        return commit_rev
        
    def write(self, uri, contents, msg=None, kind=None):

        uri = self.normalized(uri)
        absolute_uri = '/'.join((self.checkout_dir, uri))

        if os.path.isdir(absolute_uri): # we can't write to a directory
            raise NotAFile(uri)

        parent_dir = os.path.dirname(uri)
        absolute_parent_dir = '/'.join((self.checkout_dir, parent_dir))

        x = self.client

        if parent_dir and not os.path.exists(absolute_parent_dir):
            os.makedirs(absolute_parent_dir)
            x.smart_add([absolute_parent_dir])
            x.commit("Auto-creating directories")

        f = file(absolute_uri, 'w')
        print >> f, contents
        f.close()

        x.add([uri])

        if not msg: # wish we could just do `if msg is None`, but we can't.
            msg = self.default_message

        rev_id = x.commit(message=msg)

        return R(x.branch.revision_id_to_revno(rev_id))

class Revision(object):
    def __init__(self, n):
        self.n = n
    def __repr__(self):
        return "<Revision kind=number %d>" % self.n
R = Revision

if __name__ == '__main__':
    import doctest
    doctest.testfile('bzr.txt')
