Transifex Python Toolkit
------------------------

Transifex Python Toolkit is a collection of tools that allow you to easily localize your applications using Transifex.

# Installation
```python
pip install transifex-python
```

The toolkit provides a Python interface for preparing your code for localization, as well as a thin Django wrapper for Django apps.


# Integrate with a Django app

- [Setup](#setup)
- [Quick guide](#quick-guide)
- [Detailed usage](#detailed-usage)
  * [Internationalization in Python code](#internationalization-in-python-code)
  * [Internationalization in template code](#internationalization-in-template-code)
  * [Metadata](#metadata)
  * [Fetching source content from Transifex](#fetching-source-content-from-transifex)
  * [Uploading source content to Transifex](#uploading-source-content-to-transifex)
  * [Missing translations](#missing-translations)
 - [Hosting translations on your servers](#hosting-translations-on-your-servers)
 - [Tests](#tests)

## Setup


Before you begin, you will need an account in [Transifex](https://www.transifex.com) and a project.
To set a project compatible with this toolkit contact [support](https://www.transifex.com/contact/) and you
will be given a set of credentials (a public token and a secret), that you can use in your code for authentication.

Add the following entries in the settings file of your Django project.

Note: The Transifex Python Toolkit uses some parts of Django's i18n framework, like the available languages and current language. Some of these settings will affect your project as a whole, while others are only used by the Transifex Toolkit.

```python
INSTALLED_APPS = [
    ...,
    'transifex.native.django',
]

LANGUAGE_CODE = 'en-us'  # replace with your project's source language
USE_I18N = True
USE_L10N = True

# Replace with the proper values for the Transifex project token and secret,
# as found in the Transifex UI under your project
TRANSIFEX_TOKEN = <project_token>  # used for pulling translations from Transifex
TRANSIFEX_SECRET = <project_secret>  # used for pushing source content to Transifex
```

A list of supported language codes is available [here](https://www.transifex.com/explore/languages/) and should
be declared in the `ll-cc` format, compatible with the `Accept-Language` HTTP header specification, for example
`pt-br` instead of `pt_BR`.

## Quick guide

These are the minimum steps required for testing the Transifex Toolkit with a Django project end-to-end:

1. Add translation hooks in your templates
2. Push the source content to Transifex
3. Translate content on Transifex
4. Display translated content to your users

### 1. Add translation hooks

Open a Django template file (e.g. an `.html` file) and add the following:
```
{% load transifex %}

<p>{% t "Hello!" %}</p>
<p>{% t "I want to be translated." %}</p>
```

### 2. Push source content to Transifex

This command will collect all translatable strings and push them to Transifex.
```
./manage.py pushtransifex
```

### 3. Translate content on Transifex

The next step is for your translators to translate the strings in various languages using Transifex.
When a translation is added on Transifex, it becomes available over-the-air on your app.
Please note that it can take a few minutes for the translations to become available on your app.

### 4. Display translated content

The Transifex Toolkit automatically displays translated content in the language currently selected in your Django project.

In order to allow changing the current language, you will need the following:

#### 4.1 A language picker

Here is an example of how you can add a language picker in your app.
You can add this on the same HTML file you added the translatable strings before, like so:

```html
{% load i18n %}
{% load transifex %}

<p>{% t "Hello!" %}</p>
<p>{% t "I want to be translated." %}</p>

<form action="{% url 'set_language' %}" method="post">{% csrf_token %}
    <input name="next" type="hidden" value="/" />
    <select name="language">
        {% get_current_language as LANGUAGE_CODE %}
        {% get_available_languages as LANGUAGES %}
        {% get_language_info_list for LANGUAGES as languages %}
        {% for language in languages %}
        <option value="{{ language.code }}"{% if language.code == LANGUAGE_CODE %} selected{% endif %}>
        {{ language.name_local }} ({{ language.code }})
        </option>
        {% endfor %}
    </select>
    <input type="submit" value="Go" />
</form>
```

Add the following route in your Project's routes, so that the `set_language` hook shown above will work when submitting the form.
```python
from django.conf.urls import url, include

urlpatterns = [
    ...,
    url(r'^i18n/', include('django.conf.urls.i18n')),
]
```

Now you can test the language picker. Each string will be shown translated in the current language.

If a translation is not available on Transifex, the source string will appear instead by default.
This behavior is configurable by defining a different [missing policy](#missing-translations).
For example, you can choose to show dummy content instead of the source string, a method often referred to as “pseudo-localization”.
This way, you can test the UI and allow strings that have not been translated to stand out.

```python
TRANSIFEX_MISSING_POLICY = 'transifex.native.rendering.PseudoTranslationPolicy'
# _t("Hello, friend") -> returns "Ȟêĺĺø, ƒȓıêñđ"
```

## Detailed usage

You can use the toolkit both inside Django templates as well as inside views.

### Internationalization in template code

First of all, near the top of every template in which you want to include localized content, add the following template tag:
```
{% load transifex %}
```

Translations in Django templates use a single template tag, `{% t %}`. It translates constant strings or strings that contain both literals and variable content.

```html
<p>{% t "This is a great sentence." %}</p>
<h2>{% t "Welcome, {username}" username=user.name %}</h2>
```

#### Context

You can provide contextual information that accompany a string using the special `_context` keyword:

```
{% t "Contact us" _context="Support page CTA" %}
```

Defining context makes it possible to distinguish between two identical source strings and disambiguate the translation.

#### Plurals and other complex structures

The Transifex Toolkit supports the [ICU Message Format](http://userguide.icu-project.org/formatparse/messages).

Using the Message Format syntax you can support various types of logic, with the same template tag:

```
{% t "{num, plural, one {Found {num} user} other {Found {num} users} }" num=total_users %}
```

To write a string that spans multiple lines, use a `{% t %}` tag and close it with an `{% endt %}` tag.

```
{% t num=total_users visit_type=user.visit.type username=user.name %}
  {visit_type, select,
    first {Welcome, {username}}
    returning {Welcome back, {username}}
  }
{% endt %}
```

A more complex example, using nested rules, is the following:
```
{% t
  gender_of_host="female"
  total_guests=current_event.total_guests
  host=current_event.host.user.name
  guest=guest.name %}
  {gender_of_host, select,
    female {
      {total_guests, plural, offset:1
        =0 {{host} does not give a party.}
        =1 {{host} invites {guest} to her party.}
        =2 {{host} invites {guest} and one other person to her party.}
        other {{host} invites {guest} and # other people to her party.}
      }
    }
    male {
      {total_guests, plural, offset:1
        =0 {{host} does not give a party.}
        =1 {{host} invites {guest} to his party.}
        =2 {{host} invites {guest} and one other person to his party.}
        other {{host} invites {guest} and # other people to his party.}
      }
    }
    other {
      {total_guests, plural, offset:1
        =0 {{host} does not give a party.}
        =1 {{host} invites {guest} to their party.}
        =2 {{host} invites {guest} and one other person to their party.}
        other {{host} invites {guest} and # other people to their party.}
      }
    }
  }
{% endt %}
```

#### Filters

Template filters are fully supported, so you can use something like the following in order to display the total number of items inside a list object or transform a string to uppercase:
```html
{% t "Found {total} errors." total=result.errors|length %}
{% t "PROJECT '{name}'" name=project.name|upper %}
```

### Internationalization in Python code

In order to mark translatable strings inside Python code, import a function and wrap your strings with it.

```python
from transifex.native.django import t
from django.http import HttpResponse

def my_view(request):
    output = t("Welcome aboard!")
    return HttpResponse(output)
```

Again, ICU Message Format is supported, so you can use the same string syntax as in Django templates, and pass all variables as named arguments.

```python
text = t("Welcome, {username}", username=user.name)
text = t("Contact", _context="support")
```

```python
text = t(
    "{num, plural, "
    "    one {There is {num} user in this team.} "
    "    other {There are {num} users in this team.}"
    "}",
    num=total_users,
)
```

```python
text = t("""
  {gender_of_host, select,
    female {
      {total_guests, plural, offset:1
        =0 {{host} does not give a party.}
        =1 {{host} invites {guest} to her party.}
        =2 {{host} invites {guest} and one other person to her party.}
        other {{host} invites {guest} and # other people to her party.}
      }
    }
    male {
      {total_guests, plural, offset:1
        =0 {{host} does not give a party.}
        =1 {{host} invites {guest} to his party.}
        =2 {{host} invites {guest} and one other person to his party.}
        other {{host} invites {guest} and # other people to his party.}
      }
    }
    other {
      {total_guests, plural, offset:1
        =0 {{host} does not give a party.}
        =1 {{host} invites {guest} to their party.}
        =2 {{host} invites {guest} and one other person to their party.}
        other {{host} invites {guest} and # other people to their party.}
      }
    }
  }""",
  gender_of_host="female",
  total_guests=current_event.total_guests,
  host=current_event.host.user.name,
  guest=guest.name,
)
```

### Metadata

Along with the string and its contexts you can also send optional metadata that can support your localization flow:
- `_comment`: A comment to the translators
- `_charlimit`: The maximum length of characters for the translation
- `_tags`: Comma separated _tags that accompany the source string

```
{% t "A string" _comment="Developer comment" _charlimit=30 _tags="t1,t2" %}
```

```python
t(
    "A string",
    _comment="A comment to the translators",
    _charlimit=30,
    _tags="t1,t2",
)
```

In total, the reserved keywords that have special meaning and cannot be used as variable placholders are the following:
- `_context`
- `_comment`
- `_charlimit`
- `_tags`

Learn more on how metadata can improve the localization process
by reading about [character limits](https://docs.transifex.com/translation/tools-in-the-editor#character-limits),
[developer comments](https://docs.transifex.com/translation/tools-in-the-editor#string-instruction-and-developer-notes) and
[tags](https://docs.transifex.com/translation/tools-in-the-editor#section-tags) in Transifex documentation.


### Escaped & unescaped strings

Both the `{% t %}` template tag and the `t()` method escape HTML.

If you want to display unescaped text, you can use `{% ut %}` and `ut()` respectively. This way, the source & translation string will **not** be escaped, however any variables that replace placeholders in the string will be escaped.
Use the unescape tag and method carefully, because otherwise, you might be prone to XSS attacks.

```html
{% t "<script type="text/javascript">alert({name})</script>" name="<b>Joe</b>" %}
# Renders as &lt;script type=&quot;text/javascript&quot;&gt;alert(&lt;b&gt;Joe&lt;/b&gt;)&lt;/script&gt;

{% ut "<script type="text/javascript">alert({name})</script>" name="<b>Joe</b>" %}
# Renders as <script type="text/javascript">alert(&lt;b&gt;Joe&lt;/b&gt;)</script>
```

```python
from transifex.native.django import t, ut
t('<script type="text/javascript">alert({name})</script>', name='<b>Joe</b>')
# Renders as &lt;script type=&quot;text/javascript&quot;&gt;alert(&lt;b&gt;Joe&lt;/b&gt;)&lt;/script&gt;

ut('<script type="text/javascript">alert({name})</script>', name='<b>Joe</b>')
# Renders as <script type="text/javascript">alert(&lt;b&gt;Joe&lt;/b&gt;)</script>
```

### Fetching translations from Transifex

The Django integration fetches translations **automatically** from Transifex continuously over-the-air (OTA), **without having to restart your server**.

What actually happens is:

* The first time the application starts, the integration populates its internal memory with the state of translations in Transifex.
* A daemon (thread) runs in the background to periodically re-fetch translations & update the internal memory.

This functionality starts with your application. However, it does not start by default when running a Django shell or any `./manage.py <command>` commands, which means that in those cases by default translations will not be available on your application.

#### Advanced

Translation are available over the air for your app when the Django server is running and listening for HTTP requests.
However if you need to run Django shell or Django commands and have Transifex Toolkit provide localized content,
you can control this using the `FORCE_TRANSLATIONS_SYNC` environment variable,
which will start the daemon and fetch translations periodically.

So, for example, if you want to run a Django shell with translations available & receive OTA updates you can do so by running:
```python
FORCE_TRANSLATIONS_SYNC=true ./manage.py shell
```

### Uploading source content to Transifex

After the strings have been marked either inside templates or Python code, you can push them to Transifex.

In order to be able to do so, first make sure your Transifex project secret is in your Django settings file,
as described in the [setup section](#setup), and then simply run:

```
./manage.py pushtransifex
```

This command works in two phases:
1. First it goes through all files of the current directory (and subdirectories) and collects all translatable strings in memory
2. Then it contacts Transifex and pushes the strings with all metadata to the project (and resource) that is associated with the token you have given during setup

This way, the source strings reach Transifex and become available for translation.

### Missing translations

If a translation on a specific locale is missing, by default the Transifex Toolkit will return the string in the source language. However, you can change that behavior by providing a different "missing policy".

The currently available options are:

- Source String
- Pseudo translation
- Source string inside brackets
- Source string with extra characters
- A custom policy of yours
- A combined policy

You can set the policy with a Django setting named `TRANSIFEX_MISSING_POLICY` and you could easily define a different policy for development and production environments.

#### Source string (default)

This is the default policy, where the source string will appear when a translation is missing.

```python
TRANSIFEX_MISSING_POLICY = 'transifex.native.rendering.SourceStringPolicy'
# _t("Hello, friend") -> returns "Hello, friend"
```

#### Pseudo translation

This is a nice way to do translation QA during development, as pseudo-translated strings stand out and are easy to identify.

```python
TRANSIFEX_MISSING_POLICY = 'transifex.native.rendering.PseudoTranslationPolicy'
# _t("Hello, friend") -> returns "Ȟêĺĺø, ƒȓıêñđ"
```

It's advised that you do that only for your development environment, as you probably don't want to show pseudo translations to your actual users on production.

#### Source string inside brackets

Another way to show that a string is placeholder text is to show it wrapped around some symbols.

```python
TRANSIFEX_MISSING_POLICY = (
    'transifex.native.rendering.WrappedStringPolicy',
    {'start': '[', 'end': ']'},
)
# _t("Hello, friend") -> returns "[Hello, friend]"
```

#### Source string with extra characters

Translations in some locales are typically longer than in English. This policy allows you to do QA for your UI during development and make sure that longer strings can be accommodated by your current UI elements.

```python
TRANSIFEX_MISSING_POLICY = (
    'transifex.native.rendering.WrappedStringPolicy',
    {'extra_percentage': 0.5, 'extra_str': '~#'},
)
# _t("Hello, friend") -> returns "Hello, friend~#~#~#"
```

#### A complex policy

You can also combine multiple policies to get a result that stands out even more visually and also supports features like extra length or something custom you want.

Simply set the policy to a list, with each item being a tuple of a string, depending on whether or not it needs parameters:

```python
TRANSIFEX_MISSING_POLICY = [
    'transifex.native.rendering.PseudoTranslationPolicy',
    (
        'transifex.native.rendering.ExtraLengthPolicy',
        {'extra_percentage': 0.5},
    ),
    (
        'transifex.native.rendering.WrappedStringPolicy',
        {'start': '{', 'end': '}'},
    )
]
# _t("Hello, friend") -> returns "{Ȟêĺĺø, ƒȓıêñđ~extra~}"
```

#### Custom policy

You can easily create your own policy:

```python
TRANSIFEX_MISSING_POLICY = (
    'myapp.module_name.MyMissingPolicy',
    {'param1': 'value1', 'param2': 'value2'},
)
# _t("Hello, friend") -> returns a custom string
```

### Rendering errors

The Transifex Native solution protects the application from errors caused during rendering. Examples of those could be:
* Missing variables (variables that exist in the translation but their value is not provided)
* Malformed ICU messages (those would break the rendering of the ICU message)
* Unspecified rendering errors

The way this works is that every time a string is being rendered, if rendering fails, then an "error policy" is invocated, which defines what to render instead.

Currently, a `SourceStringErrorPolicy` is implemented, which tries to render the source string. If this also fails, a default text is rendered instead.

The default text is configured by setting the `TRANSIFEX_ERROR_POLICY` setting. An example of setting a different default text would be configuring the setting as such:

```python
TRANSIFEX_ERROR_POLICY = (
    'transifex.native.rendering.SourceStringErrorPolicy',
    {'default_text': 'some_custom_text'},
)
```

You can implement your own error policies. The interface can mimic the one described in `AbstractErrorPolicy`, and it is suggest to subclass this for your implementation. The structure & configuration options of error policies mimic the way missing policies are implemented, so you can take a look there as well for inspiration.

# Hosting translations on your servers

The Transifex Native solution retrieves the translated content via an intermediate called Content Delivery Service (CDS). It works similarly to a CDN and serves all translations from a cache, so that the retrieval is fast.

We offer a cloud-based CDS instance at Transifex, however, you can (and we encourage you) to host it yourself, so that translations are served directly from your servers.
In order to do that, you need to provide its host in the settings file of your Django project:

```python
TRANSIFEX_CDS_HOST = 'https://cds.example.com'
```

# Tests

In order to run tests, use:

```
make localtests
```

If this the first time you are doing it, you will also have to run `make build` too.

This will spawn a docker container & run all the builds that run on the CI platform.
In the end, it will produce a coverage report as well.

During development, in case you want to run tests with a debugger (interactive debugging),
you can use `pytest -s`. However, since tests will also test the Django integration, you will need
to install `pytest-django` and a supported Django version (currently 1.11). Then, run `pytest` as follows

```
PYTHONPATH=$PYTHONPATH:$(pwd) DJANGO_SETTINGS_MODULE=tests.native.django.settings pytest
```

Use `pytest -s` to enable interactive debugging.

# License

Licensed under Apache License 2.0, see `LICENSE` file.
