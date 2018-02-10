import io
import os
from os.path import join, dirname

#import dpm


from setuptools import setup, find_packages


def read(*paths):
    """Read a text file."""
    fullpath = join(dirname(__file__), *paths)
    return io.open(fullpath, encoding='utf-8').read().strip()


INSTALL_REQUIRES = [
    'celery',
    'django',
    'django-rest-framework',  # TODO: can we live without drf dependency?
    'redis',
    'requests',
]

TESTS_REQUIRE = [
    'nose',
    'responses'
]


setup(
    name='websubsub',
    version='0.1',
    description='Django websub subscriber',
    long_description=read('README.md'),
    author='Evstifeev Roman',
    author_email='someuniquename@gmail.com',
    url='https://github.com/Fak3/websubsub',
    license='MIT',
    packages=find_packages(exclude=['tests']),
    include_package_data=True,
    install_requires=INSTALL_REQUIRES,
    tests_require=TESTS_REQUIRE,
    extras_require={'develop': TESTS_REQUIRE},
    test_suite='nose.collector',
    classifiers = [
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Operating System :: Microsoft :: Windows',
        'Operating System :: OS Independent',
        'Operating System :: POSIX :: Linux',
        'Operating System :: MacOS :: MacOS X',
        'Operating System :: Android',
        'Programming Language :: Python :: 3',
        'Topic :: Software Development',
    ],
)
