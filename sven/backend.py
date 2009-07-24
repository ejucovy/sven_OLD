from operator import attrgetter
import os
import pysvn
import subprocess
from exc import *

#def notify(event):
    #import pdb; pdb.set_trace()

class SvnAccess(object):
    def __init__(self, svnuri, checkout_dir,
                 config_location=None):
        self.svnuri = svnuri
        if config_location and not config_location.startswith('/'):
            config_location = os.path.join(checkout_dir, config_location)

        if config_location.endswith('/'):
            config_location = config_location.rstrip('/')

        self.config_location = config_location or ''
        print self.config_location
        os.chdir(checkout_dir)
        self.checkout_dir = checkout_dir

    @property
    def client(self):
        client = pysvn.Client(self.config_location)
        if self.config_location.startswith(self.checkout_dir):
            client.add(self.config_location[len(self.checkout_dir):])
        client.exception_style = 1
        #client.callback_notify = notify
        return client

    def last_changed_rev(self, uri, rev=None):
        uri = uri.strip('/')

        if rev is not None:
            rev = pysvn.Revision(pysvn.opt_revision_kind.number, rev)
            try:
                info = self.client.info2(uri, rev)
            except pysvn.ClientError, e:
                if e[1][0][1] == 150004: # has no URL
                    raise NoSuchResource(uri)
                raise                
        else:
            try:
                info = self.client.info2(uri)
            except pysvn.ClientError, e:
                if e[1][0][1] == 200005: # not under version control
                    raise NoSuchResource(uri)
                if e[1][0][1] == 150000: # not under version control
                    raise NoSuchResource(uri)
                if e[1][0][1] == 155007: # not a working copy
                    raise NoSuchResource(uri)
                raise

        last_change = info[0][1].last_changed_rev.number
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
        uri = uri.strip('/')
        index_template = """<html><head><title></title></head>
<body><div id='content'><ul>%s</ul></div></body></html>"""
        if rev is not None:
            last_change = self.last_changed_rev(uri, rev)
            if last_change < int(rev):
                raise ResourceUnchanged(uri, last_change)

            rev = pysvn.Revision(pysvn.opt_revision_kind.number, rev)
            try:
                return {'body': self.client.cat(uri, rev),
                        'kind': self.kind(uri),
                        }
            except pysvn.ClientError, e:
                if e[1][0][1] == 195007: # URL refers to a directory
                    raise NotAFile(uri)

        try:
            return {'body': file(uri).read(),
                    'kind': self.kind(uri),
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

        uri = uri.strip('/')

        # if uri evals to false we're at the repo root
        if uri and not os.path.isdir(uri):
            raise NotADirectory(uri)

        if rev is not None:
            last_change = self.last_changed_rev(uri, rev)
            if last_change < int(rev):
                raise ResourceUnchanged(uri, last_change)

            rev = pysvn.Revision(pysvn.opt_revision_kind.number, rev)
            contents = self.client.ls(uri, rev)
        else:
            contents = self.client.ls(uri)

        contents.sort(key=attrgetter('name'))
        globs = []
        for obj in contents:
            glob = dict(href='/%s' % obj.name)
            fields = {'id': obj.name}
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

        uri = uri.strip('/')

        if rev is not None:
            last_change = self.last_changed_rev(uri, rev)
            if last_change < int(rev):
                raise ResourceUnchanged(uri, last_change)

            rev = pysvn.Revision(pysvn.opt_revision_kind.number, rev)
            try:
                log = self.client.log(uri, rev, discover_changed_paths=True)
            except pysvn.ClientError, e:
                if e[1][0][1] == 150004: # has no URL
                    raise NoSuchResource(uri)
                raise
        else:
            try:
                log = self.client.log(uri, discover_changed_paths=True)
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
        uri = uri.strip('/')

        try:
            properties = self.client.propget('svn:mime-type', uri)
        except pysvn.ClientError, e:
            if e[1][0][1] == 150000: # not under version control
                return ""
            if e[1][0][1] == 200005: # not under version control
                return ""
            if e[1][0][1] == 155007: # not a working copy
                return ""
            raise
    
        return properties.get(uri)

    def set_kind(self, uri, kind, msg=None):
        uri = uri.strip('/')

        self.client.propset('svn:mime-type', kind, uri)
        
        if not msg:
            msg = "Set svn:mime-type property to '%s'" % kind
        self.client.checkin([uri], msg)
        self.client.update('.')

    def write(self, uri, contents, msg=None, kind=None):
        uri = uri.strip('/')

        if os.path.isdir(uri): # we can't write to a directory
            raise NotAFile(uri)

        parent_dir = '/'.join(uri.split('/')[:-1])

        if parent_dir and not os.path.exists(parent_dir):
            path = '/'.join(uri.split('/')[:-1])
            os.makedirs(path)

            path = path.split('/')
            for i in range(len(path)):
                root_to_add = '/'.join(path[:i+1])
                try: 
                    self.client.add(root_to_add)
                except pysvn.ClientError, e:
                    continue
            self.client.checkin([root_to_add], "auto-creating directories")
            self.client.update('/'.join(path))

        f = file(uri, 'w')
        print >> f, contents
        f.close()
        try:
            self.client.add(uri)
        except pysvn.ClientError, e:
            if e[1][0][1] == 150002: # already under version control
                pass
            else: # i don't know what else this would be! better not make any decisions!
                raise

        if not msg: # wish we could just do `if msg is None`, but we can't.
            msg = "foom"  ### XXX TODO default should be provided to class constructor i suppose

        if kind:
            self.client.propset('svn:mime-type', kind, uri)

        self.client.checkin([uri], msg)
        self.client.update('.')

