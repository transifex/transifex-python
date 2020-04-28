# Releasing to PyPI

Releasing to PyPI happens via the [travis](https://travis-ci.org) integration.
In order for a PyPI deployment to occur, a new tag must be pushed to the
`master` branch. So, if you have setup your git to push to
[this reposository](https://github.com/transifex/transifex-python), in order to
deploy the latest changes from `devel`, you need to run:

```sh
git checkout master
git merge --ff-only devel
git tag <next-version>
git push origin <next-version>
```

## Versioning

We use the [SemVer](https://semver.org/) specification:

> Given a version number MAJOR.MINOR.PATCH, increment the:
> 
> 1. MAJOR version when you make incompatible API changes,
> 2. MINOR version when you add functionality in a backwards compatible manner,
>    and
> 3. PATCH version when you make backwards compatible bug fixes.
