"""
implements a `path_fixer` for the backend
"""

from datetime import date
class DateLayoutPathFixer(object):
    """
    a bloggish directory structure

    assuming today is 2009-12-22::
    >>> fixed_path = DateLayoutPathFixer()
    >>> fixed_path("/my/post.html")
    '2009/12/22/my/post.html'

    you can set the date and a timedelta::
    >>> fixed_path = DateLayoutPathFixer(from_date=datetime.datetime(2009, 12, 20), delta=datetime.timedelta(4))
    >>> fixed_path("/my/post.html")
    '2009/12/24/my/post.html'
    """
    def __init__(self, from_date=None, delta=None):
        self.from_date = from_date
        self.delta = delta
    def __call__(self, path):
        from_date = self.from_date or date.today()
        if self.delta:
            from_date += delta
        prefix = from_date.strftime("%Y/%m/%d")
        return "%s/%s" % (prefix, path)

