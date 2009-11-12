from mercurial import commands as cmd, ui as UI, hg

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

        if not msg:
            msg = "Foom!"

        cmd.add(ui, repo, uri)
        cmd.commit(ui, repo, uri, message=msg, logfile=None)

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

        cmd.log(ui, repo, uri, rev=rev, date=None, user=None)
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
