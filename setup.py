# -*- coding: utf-8 -*-
from setuptools import find_packages
from setuptools import setup


test_reqs = [
    "pytest>=9.0.3",
    "pytest-docker-fixtures>=1.4.4",
    "pytest-aiohttp>=1.1.0",
]


setup(
    name="guillotina_gcloudstorage",
    version=open("VERSION").read().strip(),
    description="guillotina gcloud storage support",
    long_description=(open("README.rst").read() + "\n" + open("CHANGELOG.rst").read()),
    long_description_content_type="text/x-rst",
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3 :: Only",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
    python_requires=">=3.10",
    author="Ramon Navarro Bosch",
    author_email="ramon@plone.org",
    keywords="guillotina async cloud storage",
    url="https://pypi.python.org/pypi/guillotina_gcloudstorage",
    license="GPL version 3",
    zip_safe=True,
    include_package_data=True,
    packages=find_packages(exclude=["ez_setup"]),
    package_data={"": ["*.txt", "*.rst"], "guillotina_gcloudstorage": ["py.typed"]},
    install_requires=[
        "aiohttp>=3.13.5",
        "backoff>=2.2.1",
        "google-auth>=2.53.0",
        "google-cloud-storage>=3.10.1",
        "guillotina>=7,<8",
    ],
    extras_require={"test": test_reqs},
    entry_points={"guillotina": ["include = guillotina_gcloudstorage",]},
)
