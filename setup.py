from setuptools import setup, find_packages
from os import path

here = path.abspath(path.dirname(__file__))

with open(path.join(here, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

setup(
    name='hangouts_linkgrabber',
    version='0.1.0',
    description='Get a digest of links sent to you on Hangouts during the day.',
    long_description=long_description,
    url='https://github.com/ammgws/hangouts_linkgrabber',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Programming Language :: Python :: 3.6',
    ],
    python_requires='>=3.6',
    packages=find_packages(exclude=['tests']),
    install_requires=['click', 'requests'],
    tests_require=['pytest'],
    dependency_links=['https://github.com/ammgws/hangouts_client/tarball/master']
)
