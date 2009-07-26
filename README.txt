It requires `pysvn` which you will probably want to install system-wide.

Basic usage:

    from sven.backend import SvnAccess
    client = SvnAccess(my_svn_server_repo_uri, my_local_checkout_dir)
    
    client.write('path/to/a/file/to/write', "Lovely content to be versioning!")
    client.write('path/to/another/file', "Aw shucks, I'll version this too..",
                 msg="My commit message", kind='text/plain')

    last_rev_int = client.last_changed_rev('path/to/another/file')

    last_rev_int = last_rev_int - 1
    from sven.exc import ResourceUnchanged
    try:
        earlier_version = client.read('path/to/another/file', rev=last_rev_int)
    except ResourceUnchanged, exc:
    	last_rev_int = exc.last_change
        earlier_version = client.read('path/to/another/file', rev=last_rev_int)
	
    changelog = client.log('path/to/another/file', rev=last_rev_int)
    
Each `.write` writes the content to the path on the local filesystem's checkout
and then commits it to the repository. The workflow of one-write-per-commit is
by design and is not likely to change soon; if you need a different workflow,
you probably ought to just be using svn clients directly, anyway.

Currently sven does not help you set up an svn client or server.  It assumes
you've already got a repository and checkout set up.

The formats returned by some of its methods (particularly .log and .ls) are
totally ad-hoc right now and strange; they'll probably be formalized sooner
or later.
