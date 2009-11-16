import os
from StringIO import StringIO

from mercurial import commands as cmd, ui as UI, hg, util as hg_util, cmdutil

from sven.exc import *

class HgAccess(object):
    def __init__(self, checkout_dir):
        self.checkout_dir = checkout_dir

    @property
    def client(self):
        return self._client(self.checkout_dir)

    def _client(self, path):
        ui = UI.ui()
        repo = hg.repository(ui, path)
        return repo

    def read(self, uri, rev=None):
        uri = uri.strip('/')
        absolute_uri = '/'.join((self.checkout_dir, uri))

        repo = self.client
        ui = repo.ui
        
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

        repo = self.client
        ui = repo.ui
        ui.verbose = True

        if not msg:
            msg = "Foom!"

        ui.pushbuffer()

        cmd.add(ui, repo, absolute_uri)
        cmd.commit(ui, repo, absolute_uri, message=msg, logfile=None)

        out = ui.popbuffer()

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

        if rev is not None:
            rev = ["%d:0" % rev]

        try:
            cmd.log(ui, repo, uri, rev=rev, date=None, user=None)
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
