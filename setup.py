from setuptools import setup, find_packages
import sys, os

version = '0.1.1'

setup(name='sven',
      version=version,
      description="sven is a helpful fellow who wants you to use svn for more things",
      long_description="""\
""",
      classifiers=[], # Get strings from http://pypi.python.org/pypi?%3Aaction=list_classifiers
      keywords='',
      author='Ethan Jucovy & Jeff Hammel',
      author_email='ejucovy+sven@gmail.com',
      url='',
      license='GPL',
      packages=find_packages(exclude=['ez_setup', 'examples', 'tests']),
      include_package_data=True,
      zip_safe=False,
      install_requires=[
          # -*- Extra requirements: -*-
      ],
      entry_points="""
      # -*- Entry points: -*-
      """,
      )
