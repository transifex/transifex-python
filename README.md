[![Build Status](https://travis-ci.org/transifex/transifex-python.svg?branch=master)](https://travis-ci.org/transifex/transifex-python)
[![codecov](https://codecov.io/gh/transifex/transifex-python/branch/master/graph/badge.svg)](https://codecov.io/gh/transifex/transifex-python)

# Transifex Python Toolkit

### Index

- [Overview](#overview)
  * [Introduction](#introduction)
  * [Features](#features)
  * [Authentication](#authentication)
  * [Hosting Translations](#hosting-translations)
- [Supported Frameworks](#supported-frameworks)
  * [Django](#django)
  * [Python](#python)
- [License](#license)

---

# Overview

## Introduction

Transifex Python Toolkit (referred as **the Toolkit** for brevity) is a collection of tools that allows for easy localization of your applications. Forget about files! Embed the SDK directly into your code and make localization a seamless part of the development cycle.

Using Transifex (TX) the localization workflow typically consists of the following steps:

1. Create a TX Native project from within the Transifex application
2. Install the Transifex Native SDK for your preferred dev language/framework
3. Find and extract the source strings in your source code
4. Push them into a **Transifex** project
5. Get your content translated
6. Translations for the selected language are displayed in your application

Transifex Python Toolkit is used in steps 2, 3, 4, 5 above.

### Usage Scenarios

*  [In a Django web application](#django) The toolkit is fully integrated in Django framework. It contains utilities to mark your source strings for translation, **retrieve the translated strings** and display translation in templates or views. It also provides special CLI commands for pushing to TX and even migrating your existing template code to the new syntax.

   > Please visit the [Django Quickstart](#quickstart) for detailed examples.

*  [In a Python application](#python) In other python applications or frameworks you can utilize the toolkit as a python library. The building blocks are there: you can push your source strings to TX and retrieve translations over the air to display them to your users.

   > Please visit the [Python Quickstart](#quickstart-1) for detailed examples.

## Features

This section refers to the generic functionality provided by the Toolkit. For implementation details refer to the specific usage scenario detailed in following sections.

- **ICU message Format** (variables, plurals), context, metadata (comment, charlimit, tags) support
- HTML escaping & un-escaping
- Automatic fetch of translations over-the-air (OTA) via a background thread
- Policies to handle missing translations or errors
- Use of an intermediary service, [CDS](#hosting-translations), to retrieve translations and an in-toolkit memory cache to serve them fast.

### Authentication

Before you begin using the Toolkit, you will also need an account in [Transifex](https://www.transifex.com) and a project.

To set a project compatible with this toolkit contact [support](https://www.transifex.com/contact/) and you
will be given a set of credentials (a public token and a secret), that you can use in your code for authentication.

We will refer to these credentials in the text below as:

- `project_token` (used for pulling translations from Transifex)
- `project_secret` (used for pushing source content to Transifex)

## Hosting Translations

The Transifex Native solution retrieves the translated content via an intermediate called Content Delivery Service (CDS). It works similarly to a CDN and serves all translations from a cache, so that the retrieval is fast.

We offer a cloud-based CDS instance at Transifex that you can optionally host it yourself, so that translations are served directly from your servers.

In order to do that, you need to provide its host in the settings file of your project.

For 

```django
TRANSIFEX_CDS_HOST = 'https://cds.example.com'
```

# Supported Frameworks

## Django

+ [Setup](#setup)
+ [Quickstart](#quickstart)
+ [Use in Templates and Views](#use-in-templates-and-views)
+ [Uploading source content to Transifex](#uploading-source-content-to-transifex)
+ [Fetching translations from Transifex](#fetching-translations-from-transifex)
+ [Missing translations](#missing-translations)
+ [Advanced](#advanced)
+ [Error Handling](#error-handling)
+ [Tests](#tests)

### Setup

#### Installation

**Transifex Python Toolkit** supports the following versions:

- Python 2.7, 3.5+
- Django 1.11+

To install the SDK to your project use this command:

```bash
pip install transifex-python
```

You can also find the toolkit in PyPi: [Transifex Python toolkit](https://pypi.org/project/transifex-python/).

With the toolkit installed in your project see next how to [configure your project](#configuration).

#### Configuration

Add the following entries in the settings file of your Django project.

Note: The Transifex Python Toolkit uses some parts of Django's i18n framework, like the available languages and current language. Some of these settings will affect your project as a whole, while others are only used by the Transifex Toolkit.

```django
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

TRANSIFEX_SYNC_INTERVAL = <seconds> # used for defining the daemon running interval in seconds
```

A list of supported language codes is available [here](https://www.transifex.com/explore/languages/) and should
be declared in the `ll-cc` format, compatible with the `Accept-Language` HTTP header specification, for example
`pt-br` instead of `pt_BR`.

### Quickstart

These are the minimum steps required for testing the Transifex Toolkit with a Django project end-to-end:

1. Install Transifex Python toolkit in your Django project, using the `pip install transifex-python` in your console. Read more about [toolkit installation](#installation).
2. Update your project's Django settings file with the settings required for using the Transifex Python toolkit. Read more about [configuring your project](#configuration).
3. [Add translation hooks in your templates](#add-translation-hooks)
4. [Push the source content to Transifex](#push-source-content-to-transifex)
5. [Translate content on Transifex](#translate-content-on-transifex)
6. [Display translated content to your users](#display-translated-content)

#### Add Translation Hooks

##### Django template simple example 

Open a Django template file (e.g. an `.html` file) and add the following:

```django
{% load transifex %}
<p>{% t "Hello!" %}</p>
<p>{% t "I want to be translated." %}</p>
```

##### Django view simple example 

```django
from transifex.native.django import t
from django.http import HttpResponse

def my_view(request):
    output = t("Welcome aboard!")
    return HttpResponse(output)
```
	
To see more examples on translation hooks checkout [Use in Templates and Views](#use-in-templates-and-views).	

#### Push Source Content to Transifex

This command will collect all translatable strings and push them to Transifex.

```bash
./manage.py transifex push
```

#### Translate Content on Transifex

The next step is for your translators to translate the strings in various languages using Transifex.
When a translation is added on Transifex, it becomes available over-the-air on your application.
Please note that it can take a few minutes for the translations to become available on your application.

#### Display Translated Content

The Transifex Toolkit automatically displays translated content in the language currently selected in your Django project.
In order to allow changing the current language, you will need a **language picker**.

Here is an example of how you can add a **language picker** in your application:

1. You can add this on the same HTML file you added the translatable strings before, like so:

   ```django
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

2. Add the following route in your Project's routes, so that the `set_language` hook shown above will work when submitting the form.

   ```django
   from django.conf.urls import url, include
   
   urlpatterns = [
       ...,
       url(r'^i18n/', include('django.conf.urls.i18n')),
   ]
   ```

3. Last, add `'django.middleware.locale.LocaleMiddleware'` in your `settings.MIDDLEWARE` to enable the functionality.

   Now you can test the language picker. Each string will be shown translated in the current language.
   
   If a translation is not available on Transifex, the source string will appear instead by default.
   This behavior is configurable by defining a different [missing policy](#missing-translations).
   For example, you can choose to show dummy content instead of the source string, a method often referred to as “pseudo-localization”.
   
   This way, you can test the UI and allow strings that have not been translated to stand out.
   
   ```django
   TRANSIFEX_MISSING_POLICY = 'transifex.native.rendering.PseudoTranslationPolicy'
   # _t("Hello, friend") -> returns "Ȟêĺĺø, ƒȓıêñđ"
   ```

> Please refer to Django documentation for further information:
>
> - https://docs.djangoproject.com/en/3.0/topics/i18n/translation/#the-set-language-redirect-view
> - https://docs.djangoproject.com/en/3.0/topics/i18n/translation/#how-django-discovers-language-preference

### Use in Templates and Views

#### Contents

- [Internationalization in Template Code](#internationalization-in-template-code)
- [Inline and Block Syntax](#inline-and-block-syntax)
- [Localization Syntax](#localization-syntax)
- [Passing Parameters](#passing-parameters)
- [Outcome as Variable](#outcome-as-variable)
- [Applying Filters](#applying-filters)
- [XML Escaping](#xml-escaping)
- [Internationalization in Python Code](#internationalization-in-python-code)

---

You can use the toolkit both inside Django templates as well as inside views.

#### Internationalization in Template Code

To start using Transifex SDK in your templates add the following template tag on the top of your file:

```django
{% load transifex %}
```

Translations in Django templates use one of two template tags, `{% t %}` and `{% ut %}`. These tags are used to translate strings or variables that contain strings.

```django
<p>{% t "This is a great sentence." %}</p>
<h2>{% t "Welcome, {username}" username=user.name %}</h2>
<pre>{% t snippet.code  %}</pre>
```

Each string can contain any combination of the below items:

- Constant strings
- Variables, that can be resolved either from the parameters of the template tags or the context of the template
- Additional ICU Message Format to express complex localization forms, that are resolved by Transifex Native SDK.

You can read more about the differences of the two tags in the section [XML escaping](#XML-Escaping) of this article.

To find out more about ICU Message Format syntax please check [here](http://userguide.icu-project.org/formatparse/messages). For a nice introduction to ICU syntax you can checkout this [tutorial and online editor](https://format-message.github.io/icu-message-format-for-translators/index.html).

#### Inline and Block Syntax

Both template tags support two styles:

1. The inline syntax
   
   ```django
   {% t <source>[|filters...] [key=param[|filters...]...] [as <var_name>] %}
   {% ut <source>[|filters...] [key=param[|filters...]...] [as <var_name>] %}
   ```

2. The block syntax

   ```django
   {% t [|filters...] [key=param[|filters...]...] [as <var_name>] %}
   <source>
   {% endt %}
   
   {% ut [|filters...] [key=param[|filters...]...] [as <var_name>] %}
   <source>
   {% endut %}
   ```
   
   In general, the outcome of the block syntax will be identical to the inline
   syntax, if you had supplied the block contents as a literal argument. ie
   this:
   
   ```django
   {% t ... %}hello world{% endt %}
   ```
   
   should be identical to this:
   
   ```django
   {% t "hello world" ... %}
   ```
   
   With the block syntax, however, you can include characters that would be
   problematic with the inline syntax, like quotes (`"`) or newlines.

#### Localization Syntax

The Transifex Toolkit supports the [ICU Message Format](http://userguide.icu-project.org/formatparse/messages).

Using the Message Format syntax you can support various types of logic, with
the same template tag:

```django
{% t "{num, plural, one {Found {num} user} other {Found {num} users} }" num=total_users %}
```

```django
{% t num=total_users visit_type=user.visit.type username=user.name %}
  {visit_type, select,
    first {Welcome, {username}}
    returning {Welcome back, {username}}
  }
{% endt %}
```

A more complex example, using nested rules, is the following:

```django
{% t gender_of_host="female" total_guests=current_event.total_guests host=current_event.host.user.name guest=guest.name %}
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

Transifex Native supports a subset of ICU Message format including:

- Plurals
- ICU Select, that includes gender definitions and placeholders

You can see syntax for all supported syntax in the expanded example right above.

#### Passing Parameters

Context variables will be used to render ICU parameters in translations. For
example, if you have a context variable called `username`, you can render the
following:

```django
{% t "Hello {username}" %}
```

You can also pass variables as parameters to the tag:

```django
{% t "Hello {user_name}" user_name=username %}
```

Template filters are fully supported, so you can use something like the
following in order to display the total number of items inside a list object or
transform a string to uppercase:

```django
{% t "Found {total} errors." total=result.errors|length %}
{% t "PROJECT '{name}'" name=project.name|upper %}
```

##### Parameter keys

Several parameter keys can be used in order to annotate the string with metadata 
that will be used in Transifex. The supported parameter keys are:

- **_context**, to define additional context for the specific phrase. You can add a list of strings and separate them with a comma. Context data will be visible in the context tab of the editor.
- **_comment**, to provide instructions to the localization team working on this phrase. This information is displayed in the editor's translation area as string instructions.
- **_charlimit**, to add a character limit count for the translations. This information is displayed both in the editor's context tab and in the translation area.
- **_tags**, to define tag-keywords that can help the localization team to organize better their work over phrases. To add   
multiple tags use a comma-separator. Tags are visible in the editor's context tab. Read more about tags.

Learn more on how metadata can improve the localization process
by reading about [character limits](https://docs.transifex.com/translation/tools-in-the-editor#character-limits),
[developer comments](https://docs.transifex.com/translation/tools-in-the-editor#string-instruction-and-developer-notes) and
[tags](https://docs.transifex.com/translation/tools-in-the-editor#section-tags) in Transifex documentation.

> Defining context makes it possible to distinguish between two identical source
> strings and disambiguate the translation.

#### Outcome as Variable

Using the `as <var_name>` suffix, instead of displaying the outcome of the
translation, you will save it in a variable which you can later use however you
like:

```django
{% t "Your credit card was accepted" as success_msg %}
{% t "Your credit card was declined" as failure_msg %}
{% if success %}
    {{ success_msg }}
{% else %}
    {{ failure_msg }}
{% endif %}
```

This also works for block syntax:

```django
{% t as text %}
    Hello world
{% endt %}
{{ text }}
```

#### Applying Filters

Apart from using filters for parameters, you can also apply them on the source
string:

```django
{% t "Hello {username}"|capfirst %}
{% t source_string|capfirst %}
```

The important thing to note here is that the filter will be applied to the
**translation**, not the source string. For example, if you had the following
translations in French:

```json
{
    "hello": "bonjour",
    "Hello": "I like pancakes"
}
```

and you translate to French using this tag:

```django
{% t "hello"|capfirst %}
```

You will get `Bonjour`. If the filter had been applied to the source string
before a translation was looked up, then the second translation would have been
matched and you would have gotten `I like pancakes`.

Source string filters work with block syntax as well, just make sure you
prepend the filter(s) with `|`:

```django
{% t |capfirst %}
    hello world
{% endt %}
```

Transifex Native supports all possible filters, both built-in or user created.

In the section below we highlight two specific filters that are most commonly used:

- [escapejs](#escapejs)
- [trimmed](#trimmed)

##### escapejs

   This filter is provided by Django and is very useful when you want to set
   translations as the values of javascript variables. Consider the following
   example:

   ```django
   <script>var msg = '{% ut "hello world" %}';</script>
   ```

   If a translation has the single-quote (`'`) character in it, this would
   break your javascript code as the browser would end up reading something
   like:

   ```django
   <script>var msg = 'one ' two';</script>
   ```

   To counter this, you can use the `escapejs` filter:

   ```django
   <script>var msg = '{% ut "hello world"|escapejs %}';</script>
   ```

   In which case your browser would end up reading something like:

   ```html
   <script>var msg = 'one \u0027 two';</script>
   ```

   which is the correct way to include a single-quote character in a javascript
   string literal.

##### trimmed

   This is a filter included in our template library, so it will be available
   to you since you included the library with `{% load transifex %}`. Its
   purpose is to allow you to split a long source string into multiple lines
   using the block syntax, without having the splitting appear in the
   translation outcome. It essentially returns all non-empty lines of the
   translation joined with a single space. So this:

   ```django
   {% t |trimmed %}
     First line
     Second line
   {% endt %}
   ```

   would be rendered as

   ```
   Πρώτη γραμμή Δεύτερη γραμμή
   ```

#### XML Escaping

Choosing between the `{% t %}` or the `{% ut %}` tags will determine whether
you want to perform escaping on the **translation** (or the source string if a
translation isn't available). Using `t` will apply escaping on the translation
while `ut` will not.

So for example, if you use:

```django
{% t '<a href="{url}" title="help page">click here</a>' %}
```

Your translators in Transifex will be presented with:

```django
<a href="{url}" title="help page">click here</a>
```

but your application will actually render the XML-escaped version of the
translation (or source string if a translation isn't found):

```xml
&lt;a href=&quot;https://some.url/&quot; title=&quot;Σελίδα βοήθειας&quot;&gt;Κάντε κλικ εδώ&lt;/a&gt;
```

> **NOTE**
>
> If you want to avoid this, you should use the `{% ut %}` tag instead. Just keep
> in mind that your translators would be able to include malicious content in the
> translations, so make sure you have a proofreading process in place.

Escaping of the ICU parameters is not affected by the choice of tag. If a
context variable is used without specifying a parameter in the tag, then
whether the variable will be escaped or not depends on the choice of the
autoescape setting, which is usually set to true. Otherwise, you can apply the
`|safe` or `|escape` filters on the parameters to specify the behavior you
want. For example, assuming you have the following translation:

```json
{"<b>hello</b> {var}": "<b>καλημέρα</b> {var}"}
```

and the following context variable:

```json
{"var": "<b>world</b>"}
```

you can expect the following outcomes:

| Template                                        | Result                                                 |
| ----------------------------------------------- | ------------------------------------------------------ |
| `{% t  "<b>hello</b> {var}" var=var\|escape %}` | `&lt;b&gt;καλημέρα&lt;/b&gt; &lt;b&gt;world&lt;/b&gt;` |
| `{% t  "<b>hello</b> {var}" var=var\|safe   %}` | `&lt;b&gt;καλημέρα&lt;/b&gt; <b>world</b>`             |
| `{% ut "<b>hello</b> {var}" var=var\|escape %}` | `<b>καλημέρα</b>             &lt;b&gt;world&lt;/b&gt;` |
| `{% ut "<b>hello</b> {var}" var=var\|safe   %}` | `<b>καλημέρα</b>             <b>world</b>`             |

Because using the above two mechanisms (the choice of tag and applying
escape-related filters to the parameters) gives you good control over escaping,
the outcome of the tag is always marked as _safe_ and applying escape-related
filters to it will not have any effect. This effectively means that the use of
`|escape` or `|safe` as source string filters or as filters applied to a saved
translation outcome will be ignored, ie the following examples in each column
should behave identically:

| Source string filters                    | Saved variable filters                                     |
| ---------------------------------------- | ---------------------------------------------------------- |
| `{% t/ut <source_string> ... %}`         | `{% t/ut <source_string> ... as text %}{{ text }}`         |
| `{% t/ut <source_string>\|safe ... %}`   | `{% t/ut <source_string> ... as text %}{{ text\|safe }}`   |
| `{% t/ut <source_string>\|escape ... %}` | `{% t/ut <source_string> ... as text %}{{ text\|escape }}` |

> Because of the complexity of the cases with regards to how escaping works, the
> toolkit comes with a django management command that acts as a sandbox for all
> combinations of tags, filters etc. 
>
> **You can invoke it with**: `./manage.py transifex try-templatetag --interactive`

#### Internationalization in Python Code

Similar to template tags, each Transifex Native function call can use the same string syntax, with any combination of the below:

- Constant strings
- Variables, as named arguments.
- ICU Message Format to express complex localization forms, that are resolved by Transifex Native SDK.

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

### Uploading source content to Transifex

After the strings have been marked either inside templates or Python code, you can push them to Transifex.

In order to be able to do so, first make sure your Transifex project secret is in your Django settings file,
as described in the [configuration section](#configuration), and then simply run:

```bash
./manage.py transifex push
```

This command works in two phases:
1. First it goes through all files of the current directory (and subdirectories) and collects all translatable strings in memory
2. Then it contacts Transifex and pushes the strings with all metadata to the project (and resource) that is associated with the token you have given during setup

This way, the source strings reach Transifex and become available for translation.

### Fetching translations from Transifex

The Django integration fetches translations **automatically** from Transifex continuously over-the-air (OTA), **without having to restart your server**.

What actually happens is:

* The first time the application starts, the integration populates its internal memory with the state of translations in Transifex.
* A daemon (thread) runs in the background to periodically re-fetch translations and update the internal memory.

This functionality starts with your application. However, it does not start by default when running a Django shell or any `./manage.py <command>` commands, which means that in those cases by default translations will not be available on your application.

### Missing translations

If a translation on a specific locale is missing, by default the Transifex Toolkit will return the string in the source language. However, you can change that behavior by providing a different "missing policy".

The currently available options are:

- [Source String](#source-string)
- [Pseudo Translation](#pseudo-translation)
- [Source String Inside Brackets](#source-string-inside-brackets)
- [Source String with Extra Characters](#source-string-with-extra-characters)
- [A Complex Policy](#a-complex-policy)
- [Custom Policy](#custom-policy)

You can set the policy with a Django setting named `TRANSIFEX_MISSING_POLICY` and you could easily define a different policy for development and production environments.

#### Source string (default)

This is the default policy, where the source string will appear when a translation is missing.

```django
TRANSIFEX_MISSING_POLICY = 'transifex.native.rendering.SourceStringPolicy'
# _t("Hello, friend") -> returns "Hello, friend"
```

#### Pseudo translation

This is a nice way to do translation QA during development, as pseudo-translated strings stand out and are easy to identify.

```django
TRANSIFEX_MISSING_POLICY = 'transifex.native.rendering.PseudoTranslationPolicy'
# _t("Hello, friend") -> returns "Ȟêĺĺø, ƒȓıêñđ"
```

It's advised that you do that only for your development environment, as you probably don't want to show pseudo translations to your actual users on production.

#### Source string inside brackets

Another way to show that a string is placeholder text is to show it wrapped around some symbols.

```django
TRANSIFEX_MISSING_POLICY = (
    'transifex.native.rendering.WrappedStringPolicy',
    {'start': '[', 'end': ']'},
)
# _t("Hello, friend") -> returns "[Hello, friend]"
```

#### Source string with extra characters

Translations in some locales are typically longer than in English. This policy allows you to do QA for your UI during development and make sure that longer strings can be accommodated by your current UI elements.

```django
TRANSIFEX_MISSING_POLICY = (
    'transifex.native.rendering.WrappedStringPolicy',
    {'extra_percentage': 0.5, 'extra_str': '~#'},
)
# _t("Hello, friend") -> returns "Hello, friend~#~#~#"
```

#### A complex policy

You can also combine multiple policies to get a result that stands out even more visually and also supports features like extra length or something custom you want.

Simply set the policy to a list, with each item being a tuple of a string, depending on whether or not it needs parameters:

```django
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

```django
TRANSIFEX_MISSING_POLICY = (
    'myapp.module_name.MyMissingPolicy',
    {'param1': 'value1', 'param2': 'value2'},
)
# _t("Hello, friend") -> returns a custom string
```
### Advanced

Translation are available **over the air (OTA)** for your application when the Django server is running and listening for HTTP requests.

However if you need to run Django shell or Django commands and have Transifex Toolkit provide localized content, you can control this using the `FORCE_TRANSLATIONS_SYNC` environment variable, which will start the daemon and fetch translations periodically.

So, for example, if you want to run a Django shell with translations available & receive OTA updates you can do so by running:

```django
FORCE_TRANSLATIONS_SYNC=true ./manage.py shell
```

### Error Handling

The Transifex Native solution protects the application from errors caused during rendering. Examples of those could be:
* **Missing variables** (variables that exist in the translation but their value is not provided)
* **Malformed ICU messages** (those would break the rendering of the ICU message)
* Unspecified **rendering errors**

The way this works is that every time a string is being rendered, if rendering fails, then an **error policy** is invocated, which defines what to render instead.

Currently, a `SourceStringErrorPolicy` is implemented, which tries to render the source string. If this also fails, a default text is rendered instead.

The default text is configured by setting the `TRANSIFEX_ERROR_POLICY` setting. An example of setting a different default text would be configuring the setting as such:

```django
TRANSIFEX_ERROR_POLICY = (
    'transifex.native.rendering.SourceStringErrorPolicy',
    {'default_text': 'some_custom_text'},
)
```
#### Custom Error Policies

You can implement your own error policies, please consider the following hints:

- The interface can mimic the one described in `AbstractErrorPolicy`, and it is suggest to subclass this for your implementation.
- The structure & configuration options of error policies mimic the way **missing translation policies** are implemented, so you can take a look [in the documentation](#missing-translations) as well for inspiration.

### Tests

In order to run tests, use:

```bash
make localtests
```

> **NOTE:** If this the first time you are doing it, you will also have to run `make build` too.

This will spawn a docker container & run all the builds that run on the CI platform.
In the end, it will produce a coverage report as well.

During development, in case you want to run tests with a debugger (interactive debugging),
you can use `pytest -s`. However, since tests will also test the Django integration, you will need
to install `pytest-django` and a supported Django version (currently 1.11). Then, run `pytest` as follows

```bash
PYTHONPATH=$PYTHONPATH:$(pwd) DJANGO_SETTINGS_MODULE=tests.native.django.settings pytest
```

Use `pytest -s` to enable interactive debugging.

## Python

### Contents

- [Setup](#setup-1)
- [Quickstart](#quickstart-1)

---      

### Setup

**Transifex Python Toolkit** supports the following versions:

- Python 2.7
- Python 3.5+

Install the toolkit to your project using the following command:

```bash
pip install transifex-python
```

### Quickstart

A sample usage of the library is given below with the following main concerns:

- [Initialization](#initialization)
- [Missing Policies](#missing-policies)
- [Automation in Background Thread](#automation-in-background-thread)
- [Fetch Translations from CDS](#fetch-translations-from-cds)
- [Push Strings to Transifex](#tpush-source-strings-to-transifex)

#### Initialization

A sample usage of the library is given below where we initialize it and call it's `translate()` method to get a translation: 

```python
from __future__ import absolute_import

from transifex.native import init, tx
# Simple case of initializing the library to be able to retrieve
# en (source language) and el, fr translations
init('project_token', ['el', 'fr', 'en'], ), 'project_secret')
# populate toolkit memory cache with translations from CDS service the first time
tx.fetch_translations() 
# get a translation of your project strings, the translation is served from cache
el_translation = tx.translate('my source string', 'el')
print(el_translation)
# get a translation with plurals and variable
translation = tx.translate(
            u'{cnt, plural, one {{cnt} {gender} duck} other {{cnt} {gender} ducks}}',
            'el',
            params={'cnt': 1, 'gender': 'ugly'}
)
```

The `translate()` method can be further parameterized by the following kwargs:
- `is_source` boolean, False by default, to return the source string if True
- `escape` boolean, True by default, to HTML escape the translation
- `_context` either a list[str] or a comma delimited string of the context of the source string in TX

The initialization of the Toolkit we can be further parameterized by:
- the missing translation policy: what `translation()` returns when an actual translation is missing.
- the error policy: how translation rendering errors are handled
- the cds host: point to your CDS server instead of Transifex's

```python
from transifex.native import init, tx
from transifex.native.rendering import PseudoTranslationPolicy, SourceStringErrorPolicy

# PseudoTranslationPolicy: on missing translation return a string that looks like the
#                          source string but contains accented characters
# SourceStringErrorPolicy: if an error happens when trying to render the translation
#                          default to the source string
init('project_token', ['el', 'fr', 'en'], ), 'project_secret',
     cds_host='http://127.0.0.1:10300',  # local dev environment CDS
     missing_policy=PseudoTranslationPolicy(),
     error_policy=SourceStringErrorPolicy())
```

#### Missing Policies

The available missing policies are `SourceStringPolicy, PseudoTranslationPolicy, WrappedStringPolicy, ExtraLengthPolicy, ChainedPolicy`. For details please look into `transifex.native.rendering` package for all classes that inherit `AbstractRenderingPolicy`. The same package contains the available error policies. Of course you can base on these policies and extend them to cater for your needs.

#### Automation in Background Thread

We can further automate this by using a background thread:

```python
from transifex.native.daemon import daemon
# ...

# start a thread that every interval secs fetches translations in cache
daemon.start_daemon(interval=30)
```

#### Fetch Translations from CDS

We saw that to force fetching all translations from the CDS we called:

```python
tx.fetch_translations()
```

#### Push Source Strings to Transifex

Finally let's use the Toolkit to push source strings to Transifex:

```python
from transifex.native.parsing import SourceString
# construct a list of strings to send
source1 = SourceString(u'Hello stranger', 
            _context=u'one,two,three',
            _comment=u'A crucial comment',
            _charlimit=33,
            _tags=u' t1,t2 ,  t3')
source2 = SourceString(u'Hello stranger', 
            _context=u'context1,context2,context3',
            _tags=' t1,t2')
source3 = SourceString(u'{cnt, plural, one {{cnt} {gender} duck} other {{cnt} {gender} ducks}}') 
# use purge=True only if you want to delete all other Transifex strings 
# except the ones we send. Alternatively all push strings are appended
# to those existing in Tx.
response_code, response_content = tx.push_source_strings([source1, source2, source3], purge=True)
```

# License

Licensed under Apache License 2.0, see `LICENSE` file.