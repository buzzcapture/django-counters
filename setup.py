from setuptools import setup
import sys, os

version = '0.1'

long_description = (
    open('README.txt').read()
    + '\n' +
    open('CHANGES.txt').read())

setup(name='django_counters',
      version=version,
      description='A Django app adding PyCounters to Django and offering admin like interface for the monitored info.',
      long_description=long_description,
      classifiers=[], # Get strings from http://pypi.python.org/pypi?%3Aaction=list_classifiers
      keywords='',
      author='DjangoCounters Developers',
      author_email='b.leskes@gmail.com',
      url='',
      license='apache',
      packages=['django_counters'],
      package_dir = {'': 'src'},
      include_package_data=True,
      zip_safe=False,
      install_requires=[
          'pycounters',
          'Django >= 1.2, <1.4',
        ])