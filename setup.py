import os
from setuptools import setup

def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()

setup(
    name = "munch",
    version = "0.0.1",
    author = "Victor Vicente de Carvalho",
    author_email = "victor.v.carvalho@gmail.com",
    description = ("A tool for manipulation, convertion and generation of source code"),
    license = "BSD",
    keywords = "swig source-to-source",
    url = "https://github.com/scooterman/pymunch",
    packages=['munch', 'tests'],
    long_description=read('README.md'),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Topic :: Utilities",
        "License :: OSI Approved :: BSD License",
    ],
)