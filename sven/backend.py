from operator import attrgetter
import os
import pysvn
from sven.exc import *

class BaseSvnAccess(object):
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
        client = pysvn.Client(self.config_location)
        if self.config_location.startswith(self.checkout_dir):
            client.add(self.config_location[len(self.checkout_dir):])
        client.exception_style = 1
        #client.callback_notify = notify
        return client

    def last_changed_rev(self, uri, rev=None):
        uri = self.normalized(uri)
        
        absolute_uri = '/'.join((self.checkout_dir, uri))

        try:
            log = self.client.log(absolute_uri,
                                  discover_changed_paths=True)
        except pysvn.ClientError, e:
            if e[1][0][1] == 155007: # not a working copy
                raise NoSuchResource(uri)
            if e[1][0][1] == 160013: # file not found
                raise NoSuchResource(uri)
            if e[1][0][1] == 150000: # not under version control
                raise NoSuchResource(uri)
            raise
            
        if rev is not None:
            rev = pysvn.Revision(pysvn.opt_revision_kind.number, rev)
            try:
                info = self.client.info2(absolute_uri, rev)
            except pysvn.ClientError, e:
                if e[1][0][1] == 150004: # has no URL
                    raise NoSuchResource(uri)
                if e[1][0][1] == 155007: # not a working copy
                    raise NoSuchResource(uri)
                raise                
        else:
            try:
                info = self.client.info2(absolute_uri)
            except pysvn.ClientError, e:
                if e[1][0][1] == 200005: # not under version control
                    raise NoSuchResource(uri)
                if e[1][0][1] == 150000: # not under version control
                    raise NoSuchResource(uri)
                if e[1][0][1] == 155007: # not a working copy
                    raise NoSuchResource(uri)
                raise

        last_change = info[0][1].last_changed_rev.number
        

        ##### in case the file's parent directory was moved more recently than the file was changed
        # this is particularly tricky if the sven client is "mounted" at a child directory of the moved path
        # e.g. 
        # touch /foo/bar/baz.txt
        # x = SvnAccess('/foo/bar/')
        # svn mv /foo /fleem
        # x.info('baz.txt')

        log = self.client.log(absolute_uri, discover_changed_paths=True)
        problems = [x for x in log[0]['changed_paths']
                    if x['copyfrom_path']]

        repo_url = info[0][1]['repos_root_URL']
        doc_url = info[0][1]['URL']

        move_revision = None
        for problem in problems:
            base_moved_path = '/'.join((repo_url.rstrip('/'), self.normalized(problem['path']) ))
            assert doc_url.startswith(base_moved_path), "I don't know what this means!\nPlease let me know the circumstances of this error if you hit it: ejucovy+sven@gmail.com"
            move_revision = problem.copyfrom_revision.number

        if move_revision:
            if last_change > move_revision:
                return last_change
            return move_revision +1 # +1 is the oldest revision at which the file exists at its current location.

        return last_change

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
        absolute_uri = '/'.join((self.checkout_dir, uri))

        index_template = """<html><head><title></title></head>
<body><div id='content'><ul>%s</ul></div></body></html>"""
        if rev is not None:
            last_change = self.last_changed_rev(uri, rev)
            if last_change < int(rev):
                raise ResourceUnchanged(uri, last_change)

            rev = pysvn.Revision(pysvn.opt_revision_kind.number, rev)
            try:
                return {'body': self.client.cat(absolute_uri, rev),
                        'mimetype': self.mimetype(uri),
                        }
            except pysvn.ClientError, e:
                if e[1][0][1] == 195007: # URL refers to a directory
                    raise NotAFile(uri)
                raise

        try:
            return {'body': file(absolute_uri).read(),
                    'mimetype': self.mimetype(uri),
                    }
        except IOError, e:
            if e.errno == 21:
                raise NotAFile(uri)
            elif e.errno == 2:
                raise NoSuchResource(uri)
            raise

    def ls(self, uri, rev=None):
        """
        Return the listing of contents stored under @param:uri
        as a JSON-listing.

        @raise:NotADirectory
        @raise:ResourceUnchanged
        etc.
        """

        uri = self.normalized(uri)
        absolute_uri = '/'.join((self.checkout_dir, uri))

        # if uri evals to false we're at the repo root
        if uri and not os.path.isdir(absolute_uri):
            raise NotADirectory(uri)

        if rev is not None:
            last_change = self.last_changed_rev(uri, rev)
            if last_change < int(rev):
                raise ResourceUnchanged(uri, last_change)

            rev = pysvn.Revision(pysvn.opt_revision_kind.number, rev)
            contents = self.client.ls(absolute_uri, rev)
        else:
            contents = self.client.ls(absolute_uri)

        contents.sort(key=attrgetter('name'))
        globs = []
        for obj in contents:
            obj_name = obj.name
            if obj_name.startswith(self.checkout_dir):
                obj_name = obj_name[len(self.checkout_dir):]
            glob = dict(href='%s' % obj_name)
            fields = {'id': obj_name}
            if rev is not None:
                fields['version'] = rev.number
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

    def mimetype(self, uri, rev=None):
        uri = self.normalized(uri)
        absolute_uri = '/'.join((
                self.checkout_dir.rstrip('/'),
                uri))

        if rev is not None:
            rev = pysvn.Revision(pysvn.opt_revision_kind.number, rev)
            def propget():
                return self.client.propget('svn:mime-type', absolute_uri, rev)
        else:
            def propget():
                return self.client.propget('svn:mime-type', absolute_uri)
        try:
            properties = propget()
        except pysvn.ClientError, e:
            if e[1][0][1] == 150000: # not under version control
                return ""
            if e[1][0][1] == 200005: # not under version control
                return ""
            if e[1][0][1] == 155007: # not a working copy
                return ""
            raise
    
        return properties.get(absolute_uri)

    def set_mimetype(self, uri, mimetype, msg=None):

        uri = self.normalized(uri)
        absolute_uri = '/'.join((self.checkout_dir, uri))

        self.client.propset('svn:mime-type', mimetype, absolute_uri)
        
        if not msg:
            msg = "Set svn:mime-type property to '%s'" % mimetype
        commit_rev = self.client.checkin([absolute_uri], msg)

        return commit_rev
        
    def write(self, uri, contents, msg=None, mimetype=None, 
              use_newline=True, binary=False):
        uri = self.normalized(uri)
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
                try: 
                    self.client.add('/'.join((self.checkout_dir, root_to_add)))
                    success = True
                except pysvn.ClientError, e: #XXX TODO: typecheck this error
                    if not success:
                        # the resource is already under version control
                        # but not because we just added it. keep walking
                        # up the chain to find something that isn't yet
                        # under version control.
                        continue
                    
                    # the resource is already under version control
                    # because we just added its parent directory.
                    # walk one step down the chain to get back to the
                    # root directory that we just added.
                    root_to_add = '/'.join(path[:i])
                    break
            self.client.checkin(['/'.join((self.checkout_dir, root_to_add))],
                                "auto-creating directories")
            path_to_update = '/'.join([self.checkout_dir] + path)
            self.client.update(path_to_update)

        mode = 'w'
        if binary is True:
            use_newline = False
            mode = 'wb'
        f = file(absolute_uri, mode)
        if use_newline and not contents.endswith('\n'):
            contents += '\n'
        f.write(contents)
        f.close()

        try:
            self.client.add(absolute_uri)
        except pysvn.ClientError, e:
            if e[1][0][1] == 150002: # already under version control
                pass
            else: # i don't know what else this would be! better not make any decisions!
                raise

        if not msg: # wish we could just do `if msg is None`, but we can't.
            msg = self.default_message

        if mimetype:
            self.client.propset('svn:mime-type', mimetype, absolute_uri)

        try:
            commit_rev = self.client.checkin([absolute_uri], msg)
            return commit_rev
        except pysvn.ClientError, e:
            if e[1][0][1] == 160028: # file is out of date
                # we roll back our attempted changes and let the caller deal with merges
                self.client.revert(absolute_uri)
                raise ResourceChanged(uri)
            else: # i don't know what else this would be! better not make any decisions!
                raise



class SvnAccessWriteUpdateHandler(BaseSvnAccess):
    def set_mimetype(self, uri, mimetype, msg=None,
                     update_before_write=True,
                     update_after_write=True):
        uri = self.normalized(uri)
        absolute_uri = '/'.join((self.checkout_dir, uri))

        if update_before_write:
            self.client.update(self.checkout_dir)

        BaseSvnAccess.set_mimetype(self, uri, mimetype, msg)

        if update_after_write:
            self.client.update(self.checkout_dir)

    def write(self, uri, contents, msg=None, mimetype=None,
              update_before_write=True,
              update_after_write=True):
        uri = self.normalized(uri)
        absolute_uri = '/'.join((self.checkout_dir, uri))

        if update_before_write:
            self.client.update(self.checkout_dir)

        result = BaseSvnAccess.write(self, uri, contents, msg, mimetype)

        if update_after_write:
            self.client.update(self.checkout_dir)

        return result

#bbb
#deprecate in 0.5
# XXX????
SvnAccess = SvnAccessWriteUpdateHandler

class SvnAccessEventEmitter(SvnAccess):
    def __init__(self, *args, **kw):
        SvnAccess.__init__(self, *args, **kw)
        self.listeners = []

    def add_listener(self, callback):
        self.listeners.append(callback)

    def set_mimetype(self, uri, mimetype, msg=None):

        uri = self.normalized(uri)
        absolute_uri = '/'.join((self.checkout_dir, uri))

        pre_rev = self.client.info2(absolute_uri)[0][1].rev
        post_rev = SvnAccess.set_mimetype(self, uri, mimetype, msg)

        for callback in self.listeners:
            callback(absolute_uri, contents, msg, mimetype, (pre_rev, post_rev))

    def write(self, uri, contents, msg=None, mimetype=None):

        uri = self.normalized(uri)
        absolute_uri = '/'.join((self.checkout_dir, uri))

        pre_rev = self.client.info2(absolute_uri)[0][1].rev
        post_rev = SvnAccess.write(self, uri, contents, msg, mimetype)
        for callback in self.listeners:
            callback(uri, contents, msg, mimetype, (pre_rev, post_rev))

if __name__ == '__main__':
    import doctest
    doctest.testfile('doctest.txt')
