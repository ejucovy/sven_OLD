from setuptools import setup, find_packages
import sys, os

version = '0.1.2'

setup(name='sven',
      version=version,
      description="sven is a library to help you put content in SVN",
      long_description=open('README.txt').read(),
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
