import io
import os
from os.path import join, dirname

from setuptools import setup, find_packages

try:
    import pypandoc
    description = pypandoc.convert('README.md', 'rst')
except (IOError, ImportError):
    description = open('README.md').read()


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
    version='0.3',
    description='Django websub subscriber',
    long_description=description,
    author='Evstifeev Roman',
    author_email='someuniquename@gmail.com',
    url='https://github.com/Fak3/websubsub',
    license='MIT',
    packages=find_packages(exclude=['tests']),
    include_package_data=True,
    install_requires=INSTALL_REQUIRES,
    tests_require=TESTS_REQUIRE,
    extras_require={'develop': TESTS_REQUIRE},
    python_requires='>=3.6',
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
