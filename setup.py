# -*- coding: utf-8 -*-
from setuptools import find_packages
from setuptools import setup

test_reqs = [
    'pytest',
    'pytest-docker-fixtures',
    'pytest-aiohttp>=0.3.0'
]


setup(
    name='guillotina_gcloudstorage',
    version=open('VERSION').read().strip(),
    description='guillotina gcloud storage support',
    long_description=(open('README.rst').read() + '\n' +
                      open('CHANGELOG.rst').read()),
    classifiers=[
        'Programming Language :: Python :: 3.7',
        'Topic :: Software Development :: Libraries :: Python Modules',
    ],
    author='Ramon Navarro Bosch',
    author_email='ramon@plone.org',
    keywords='guillotina async cloud storage',
    url='https://pypi.python.org/pypi/guillotina_gcloudstorage',
    license='GPL version 3',
    setup_requires=[
        'pytest-runner',
    ],
    zip_safe=True,

    include_package_data=True,
    packages=find_packages(exclude=['ez_setup']),
    package_data={
        "": ["*.txt", "*.rst"], "guillotina_gcloudstorage": ["py.typed"]},
    install_requires=[
        "setuptools",
        "guillotina>=5.3.48",
        "protobuf",
        "oauth2client",
        "google-cloud-storage",
        "gcloud",
        "ujson",
        "backoff",
    ],
    extras_require={
        'test': test_reqs
    },
    tests_require=test_reqs,
    entry_points={
        'guillotina': [
            'include = guillotina_gcloudstorage',
        ]
    }
)
