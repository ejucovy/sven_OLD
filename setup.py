from setuptools import setup, find_packages
import sys, os

version = '0.6'

long_description = open('README.txt').read()
new_in_this_version = open('changes/changes.txt').read()
history = open('changes/history.txt').read()

long_description = "%s\n\nNew in version %s:\n\n%s\n\nHistory:\n\n%s" % (long_description,version,new_in_this_version,history)

setup(name='sven',
      version=version,
      description="sven is a document-oriented programming library that helps you put content in a version-controlled document repository",
      long_description=long_description,
      classifiers=[],
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
