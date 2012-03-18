from setuptools import setup
import setuptools

setup=setuptools.setup

setup(name='testproject',
      version='0.1',
      description='testproject',
      packages=['testproject'],
      install_requires=[
          'django-counters',
      ],
      entry_points={
          },
      )