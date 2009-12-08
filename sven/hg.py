import os
from StringIO import StringIO

from mercurial import util as hg_util, cmdutil

from sven.exc import *

from mercurial import hg
import mercurial
import mercurial.commands

class HgAccess(object):
    def __init__(self, checkout_dir):
        self.checkout_dir = checkout_dir

    @property
    def client(self):
        return self._client(self.checkout_dir)

    def _client(self, path):
        ui = mercurial.ui.ui(interactive=False)
        ui.verbose = False
        repo = hg.repository(ui, path)
        return repo

    def read(self, uri, rev=None):
        uri = uri.strip('/')
        absolute_uri = '/'.join((self.checkout_dir, uri))

        if rev is not None:
            last_change = self.last_changed_rev(uri, rev)
            if last_change < rev:
                raise ResourceUnchanged(uri, last_change)

        repo = self.client
        
        if rev is not None:
            rev = str(rev)

        ctx = repo[rev]
        
        contents = StringIO()

        try:
            contents.write(ctx[uri].data())
        except IOError, e:
            if e.errno == 2:
                raise NoSuchResource(uri)
            elif e.errno == 21:
                raise NotAFile(uri)
            raise

        contents.seek(0)
        return dict(body=contents.read(), kind=None)

    def write(self, uri, contents, msg=None, kind=None):

        uri = uri.strip('/')
        absolute_uri = '/'.join((self.checkout_dir, uri))

        if os.path.isdir(absolute_uri): # we can't write to a directory
            raise NotAFile(uri)

        parent_dir = '/'.join(uri.split('/')[:-1])
        absolute_parent_dir = '/'.join((self.checkout_dir, parent_dir))

        root_to_add = None
        if parent_dir and not os.path.exists(absolute_parent_dir):
            path = '/'.join(uri.split('/')[:-1])
            os.makedirs('/'.join((self.checkout_dir, path)))

            path = path.split('/')
            success = False
            for i in range(len(path)):
                root_to_add = '/'.join(path[:i])
                
        f = file(absolute_uri, 'w')
        print >> f, contents
        f.close()

        repo = self.client

        # we need to turn up verbosity so we can inspect the output
        # and find the commit, which is totally lame but sort of works
        ui = repo.ui
        ui.verbose = True

        if not msg:
            msg = "Foom!"

        ui.pushbuffer()

        if root_to_add:
            root = '/'.join((self.checkout_dir, root_to_add))
        else:
            root = absolute_uri

        # mercurial will sometimes explode if handed unicode paths
        root = str(root)

        mercurial.commands.add(ui, repo, root)
        mercurial.commands.commit(ui, repo, root, message=msg, logfile=None, user=None, date=None)

        out = ui.popbuffer()

        rev = None
        for line in out.split('\n'):
            if line.startswith("committed changeset"):
                rev = line[len("committed changeset "):]
                rev = rev.split(':')[0]
                break

        class Revision(object):
            def __init__(self, rev):
                self.rev = rev
            def __repr__(self):
                return "<Revision kind=number %s>" % self.rev

        return Revision(rev)

    def last_changed_rev(self, uri, rev=None):
        log = self.log(uri, rev)
        highest = sorted(log.keys())[-1]
        return highest

    def log(self, uri, rev=None):
        uri = uri.strip('/')
        absolute_uri = '/'.join((self.checkout_dir, uri))

        repo = self.client
        ui = repo.ui
        ui.pushbuffer()

        # first check if a file exists at the given revision
        try:
            file = repo[rev][uri]
        except LookupError:  # it's a directory!
            pass
        else:
            try:
                file.data()
            except IOError, e:
                if e.errno == 2:  # no such file or directory
                    raise NoSuchResource(uri)
                if e.errno == 21: # is a directory -- and exists, so we're cool
                    pass

        raw_rev = rev
        if rev is not None:
            rev = ["%d:0" % rev]

        try:
            mercurial.commands.log(ui, repo,
                                   absolute_uri, rev=rev, date=None, user=None)
        except hg_util.Abort, e:
            if str(e).endswith("not under root"):
                raise NoSuchResource(uri)
            raise
        finally:
            out = ui.popbuffer()

        log_info = dict()

        line_info = []
        rev = None

        for line in out.split('\n'):
            if not line.strip():
                continue
            if line.startswith('changeset:'):
                if rev is not None:
                    log_info[int(rev)] = dict(line_info)
                rev = line.split(':')[1].strip()
                line_info = []
            line = line.split(':', 1)
            line_info.append((line[0].strip(), line[1].strip()))

        # here's where we want to get suspicious.
        # if there's no apparent log for any changes
        # under the given uri, AND there's no record of
        # files under the uri in the changeset,
        # we're gonna say this just doesn't exist.
        #
        # note that i have no idea what it means to have 
        # a "record of files under the uri in the changeset."
        # i have literally no idea. but this seems to work.
        if not log_info:
            files = repo[raw_rev].files()
            files_in_this_path = [file for file in files
                                  if file.startswith(uri)]
            if not files_in_this_path:
                raise NoSuchResource(uri)

        return log_info

if __name__ == "__main__":
    import doctest
    doctest.testfile('hg-doctest.txt')

    import sys
    sys.exit(0)

    import os
    from pprint import pprint as pprint

    cwd = os.getcwd()
    
    client = HgAccess(cwd)
    
    pprint(
        client.log('/')
        )
    
    pprint(
        client.last_changed_rev('/foo.txt')
        )
    
    client.write("/baz/fleem.txt", "hello!", "jinkers!")
