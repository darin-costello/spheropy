#!/usr/bin/env python

from setuptools import setup, find_packages
from codecs import open
from os import path
here = path.abspath(path.dirname(__file__))

with open(path.join(here, 'README.rst'), encoding='utf-8') as f:
    long_desc = f.read()

setup(
    name='SpheroPy',
    version='0.0.1',
    description='A Python Driver for Sphero 2.0',
    long_description=long_desc,

    url='https://github.com/darin-costello/spheropy',

    author='Darin Costello',
    author_email='darin.costello@gmail.com',
    license='MIT',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 2.7',
        'Topic :: Games/Entertainment',


    ],
    keywords='Sphero Driver',
    packages=find_packages(exclude=['docs', 'test*']),
    install_requires=['pybluez'],
    python_requires='>=2.6',
)
