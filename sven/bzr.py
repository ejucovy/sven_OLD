from operator import attrgetter
import os
from bzrlib import workingtree
from bzrlib.errors import NoSuchRevision, BoundBranchOutOfDate, ConflictsInTree
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

        from bzrlib.log import LogFormatter

        def get_formatter(lst):
            class ListLogFormatter(LogFormatter):
                def __init__(self, *args, **kw):
                    LogFormatter.__init__(self, *args, **kw)
                    self._loglist = lst
                def log_revision(self, revision):
                    self._loglist.append(int(revision.revno))
            return ListLogFormatter

        from bzrlib.builtins import cmd_log
        from bzrlib.revisionspec import RevisionSpec

        log = cmd_log()
        log.outf = None

        foo = []

        rev = None

        absolute_uri = os.path.join(self.checkout_dir, uri)

        log.run(file_list=[absolute_uri],
                revision=rev and [RevisionSpec.from_string(str(rev))] or None,
                log_format = get_formatter(foo),
                )

        return foo

    def last_changed_rev(self, uri, rev=None):
        """
        @raise:NoSuchResource
        """
        uri = self.normalized(uri)

        changes = self.revisions(uri)

        if changes is None:
            return None

        if rev is None:
            return changes[0]

        rev = int(rev)

        for revno in changes:
            if rev < revno:
                continue
            return revno

        raise NoSuchResource(uri)

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
            rev = int(rev)

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

        files = dict([(i[0], i[2]) for i in list(x.list_files())])
        
        if uri in files and files[uri] == 'directory':
            raise NotAFile(uri)

        try:
            data = x.get_file(path)
        except IOError, e:
            if e.errno == 21:
                raise NotAFile(uri)
        finally:
            x.unlock()

        data = data.read()

        mimetype = self.mimetype(uri)
        return dict(body=data, mimetype=mimetype)

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

        x.lock_read()

        if rev is not None:
            rev = int(rev)

            rev_id = x.branch.get_rev_id(int(rev))
            y = x.branch.repository.revision_tree(rev_id)
            x.unlock()
            x = y
            x.lock_read()

        inv = x.inventory

        path = x.path2id(uri)
        dir = inv[path]

        x.unlock()

        if not isinstance(dir, InventoryDirectory):
            raise NotADirectory(uri)

        if rev is not None:
            last_change = self.last_changed_rev(uri, rev=rev)
            if last_change < rev:
                raise ResourceUnchanged(uri, last_change)

        contents = ["%s/%s" % (uri, key) for key in dir.children.keys()]

        globs = []
        for obj in contents:
            glob = dict(href=obj)
            fields = {'id': obj}
            if rev is not None:
                fields['version'] = rev
            glob['fields'] = fields
            globs.append(glob)
        return globs

    def log(self, uri, rev=None):
        """
        Return the changelog of data stored at or under @param:uri
        as of time @param:rev in JSON-listing format.
        
        @raise:ResourceUnchanged
        etc.
        """

        from bzrlib.log import LogFormatter

        def get_formatter(lst):
            class ListLogFormatter(LogFormatter):
                def __init__(self, *args, **kw):
                    LogFormatter.__init__(self, *args, **kw)
                    self._loglist = lst
                def log_revision(self, revision):
                    revno = int(revision.revno)
                    author = revision.rev.committer  # @@@ what about get_apparent_authors?
                    message = revision.rev.message.rstrip('\r\n')
                    self._loglist.append(dict(version=revno,
                                              author=author,
                                              message=message,
                                              id=uri))
            return ListLogFormatter

        from bzrlib.builtins import cmd_log
        from bzrlib.revisionspec import RevisionSpec

        log = cmd_log()
        log.outf = None

        foo = []

        absolute_uri = os.path.join(self.checkout_dir, self.normalized(uri))

        log.run(file_list=[absolute_uri],
                revision=rev and [RevisionSpec.from_string("1"),
                                  RevisionSpec.from_string(str(rev))] or None,
                log_format = get_formatter(foo),
                )

        return [dict(href=uri, fields=i) for i in foo]

    def mimetype(self, uri, rev=None):
        return self.propget(uri, 'mimetype', rev=rev)

    def propget(self, uri, prop, rev=None):
        uri = self.normalized(uri)
        absolute_uri = '/'.join((self.checkout_dir, uri))

        if os.path.isdir(absolute_uri):
            return self._dir_prop(uri, prop, rev=rev)
        return self._file_prop(uri, prop, rev=rev)        

    def _dir_prop(self, uri, prop, rev=None):
        uri = self.normalized(uri)

        if not uri:
            return None

        absolute_props_uri = '/'.join((self.checkout_dir, uri, '.sven-meta'))

        if not os.path.isdir(absolute_props_uri):
            return None
        res = self.read('/'.join((uri, '.sven-meta', '.%s' % prop)), rev=rev)
        if res: return res['body']
        return res

    def _file_prop(self, uri, prop, rev=None):
        uri = self.normalized(uri)
        props_uri = '/'.join((
                '.sven-meta/.%s' % prop, uri))
        
        if not uri:
            raise RuntimeError("Can't do that")

        try:
            res = self.read(props_uri, rev=rev)
        except NoSuchResource, e:
            return None
        if res: return res['body']
        return res

    def _dir_propset(self, uri, prop, val, msg=None):
        uri = self.normalized(uri)

        return self.write('/'.join((uri, '.sven-meta/.%s' % prop)),
                          val, use_newline=False)

    def _file_propset(self, uri, prop, val, msg=None):
        uri = self.normalized(uri)

        return self.write('/'.join(('.sven-meta/.%s' % prop, uri)),
                          val, use_newline=False)

    def propset(self, uri, prop, val, msg=None):
        uri = self.normalized(uri)
        absolute_uri = '/'.join((self.checkout_dir, uri))

        if os.path.isdir(absolute_uri):
            return self._dir_propset(uri, prop, val, msg=msg)
        return self._file_propset(uri, prop, val, msg=msg)
        
    def set_mimetype(self, uri, mimetype, msg=None):
        return self.propset(uri, 'mimetype', mimetype, msg=msg)

    def write(self, uri, contents, msg=None, mimetype=None, use_newline=True):
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
        if use_newline and not contents.endswith('\n'):
            contents += '\n'
        f.write(contents)
        f.close()

        x.add([uri])

        if not msg: # wish we could just do `if msg is None`, but we can't.
            msg = self.default_message

        try:
            rev_id = x.commit(message=msg)
        except (BoundBranchOutOfDate, ConflictsInTree), e:
            raise ResourceChanged(uri)

        if mimetype is not None:
            self.set_mimetype(uri, mimetype, msg=msg)

        return R(x.branch.revision_id_to_revno(rev_id))

class UpdatingBzrAccess(BzrAccess):
    def __init__(self, checkout_dir, config_location=None,
                 default_commit_message=None, path_fixer=None,
                 update_before_write=True, update_after_write=True):
        BzrAccess.__init__(self, checkout_dir, config_location,
                           default_commit_message, path_fixer)
        self.update_before_write = update_before_write
        self.update_after_write = update_after_write

    def write(self, *args, **kw):
        override = kw.get('update_before_write', None)
        if override is not None:
            before_write = override
            del kw['update_before_write']
        else:
            before_write = self.update_before_write
        if before_write:
            self.client.update()
        res = BzrAccess.write(self, *args, **kw)
        if self.update_after_write:
            self.client.update()
        return res

class Revision(object):
    def __init__(self, n):
        self.n = n
    def __repr__(self):
        return "<Revision kind=number %d>" % self.n
R = Revision

if __name__ == '__main__':
    import doctest
    doctest.testfile('bzr.txt')
