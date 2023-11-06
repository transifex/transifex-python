from setuptools import find_packages, setup

import versioneer

with open("README.md", "r") as f:
    long_description = f.read()

setup(
    name="transifex-python",
    author="Transifex",
    author_email="info@transifex.com",
    version=versioneer.get_version(),
    cmdclass=versioneer.get_cmdclass(),
    description=("Transifex Python Toolkit"),
    long_description=long_description,
    long_description_content_type="text/markdown",
    packages=find_packages(exclude=["tests"]),
    classifiers=[
        "Programming Language :: Python :: 3.6",
        "License :: OSI Approved :: Apache Software License",
        "Operating System :: OS Independent",
    ],
    url="https://github.com/transifex/transifex-python",
    install_requires=["pyseeyou", "requests", "click", "asttokens"],
)
