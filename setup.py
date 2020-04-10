from setuptools import find_packages, setup

with open("README.md", "r") as f:
    long_description = f.read()

setup(
    name='transifex-python',
    author='Transifex',
    author_email='info@transifex.com',
    version='0.0.1',
    description=(
        'A Python SDK for Transifex'
    ),
    long_description=long_description,
    long_description_content_type="text/markdown",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python :: 3.6",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    url='https://github.com/transifex/tx-python',
    install_requires=[
        'pyseeyou', 'pytz', 'requests', 'six', 'click'
    ],
)
