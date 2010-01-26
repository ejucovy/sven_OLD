from setuptools import setup, find_packages
import sys, os

version = '0.7'

long_description = open('README.txt').read()
new_in_this_version = open('changes/changes.txt').read()
history = open('changes/history.txt').read()

long_description = """
%s

New in this version
-------------------

%s

History
-------

%s
""" % (long_description, new_in_this_version, history)

setup(name='sven',
      version=version,
      description="sven is a document-oriented programming library that helps you put content in a version-controlled document repository",
      long_description=long_description,
      classifiers=[],
      keywords='',
      author='Ethan Jucovy & Jeff Hammel',
      author_email='ejucovy@gmail.com',
      url='',
      license='GPL',
      packages=find_packages(exclude=['ez_setup', 'examples', 'tests']),
      include_package_data=True,
      zip_safe=False,
      install_requires=[
      ],
      entry_points="""
      """,
      )
