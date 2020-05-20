[![Build Status](https://travis-ci.org/transifex/transifex-python.svg?branch=master)](https://travis-ci.org/transifex/transifex-python)
[![codecov](https://codecov.io/gh/transifex/transifex-python/branch/master/graph/badge.svg)](https://codecov.io/gh/transifex/transifex-python)

# Transifex Python Toolkit

Transifex Python Toolkit is a collection of tools that allow you to easily localize your Django and Python applications using Transifex. The toolkit features fetching translations over the air (OTA) to your apps.

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
* [Quickstart guide for Django web application](https://docs.transifex.com/django-sdk/quickstart-1?utm_campaign=tx-native&utm_source=github&utm_medium=link)
* [Quickstart guide for Python application](https://docs.transifex.com/python-sdk/quickstart?utm_campaign=tx-native&utm_source=github&utm_medium=link)
* For a general overview visit [Transifex Native overview](https://docs.transifex.com/transifex-native-sdk-overview/introduction?utm_campaign=tx-native&utm_source=github&utm_medium=link)

# License

Licensed under Apache License 2.0, see `LICENSE` file.
