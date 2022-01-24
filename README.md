![Test suite](https://github.com/transifex/transifex-python/workflows/Test%20suite/badge.svg?branch=master)
[![codecov](https://codecov.io/gh/transifex/transifex-python/branch/master/graph/badge.svg)](https://codecov.io/gh/transifex/transifex-python)

# Transifex Python Toolkit

Transifex Python Toolkit is a collection of tools that allow you to easily localize your Django and Python applications using Transifex. The toolkit features fetching translations over the air (OTA) to your apps.

This project adheres to the Contributor Covenant [code of conduct](/CODE_OF_CONDUCT.md). To contribute to Transifex Python Toolkit, please check out the [contribution guidelines](/CONTRIBUTING.md).

# Upgrade to v2

If you are upgrading from the `1.x.x` version, please read this [migration guide](https://github.com/transifex/transifex-python/blob/HEAD/UPGRADE_TO_V2.md), as there are breaking changes in place.

# Quick starting guide

1. Install toolkit in your code `$ pip install transifex-python`
2. Add a provided TOKEN and SECRET in your config, connecting your application with a Transifex project
3. Add internationalization commands in your code
```HTML+Django
  <!-- Django app template example -->

  {% load transifex %}
  <p>{% t "Hello!" %}</p>
  <p>{% t "I want to be translated." %}</p>
  ```

```python
  # Django view sample
  from transifex.native.django import t

  output = {
      "msg1": t("Welcome aboard!"),
      "msg2": t("It's great to have you here!"),
  }
  return JsonResponse(output)
  ```
4. Push strings to your connected Transifex project `./manage.py transifex push`
5. When translations are added in your Transifex project are automatically made available

To learn more about using Transifex Python toolkit check:
* [Quickstart guide for Django web application](https://developers.transifex.com/docs/django-sdk?utm_campaign=tx-native&utm_source=github&utm_medium=link)
* [Quickstart guide for Python application](https://developers.transifex.com/docs/python-sdk?utm_campaign=tx-native&utm_source=github&utm_medium=link)
* For a general overview visit [Transifex Native overview](https://developers.transifex.com/docs/native?utm_campaign=tx-native&utm_source=github&utm_medium=link)
* For some common questions & answers check our [Transifex Native community](https://community.transifex.com/c/transifex-native/17)

# License

Licensed under Apache License 2.0, see `LICENSE` file.
