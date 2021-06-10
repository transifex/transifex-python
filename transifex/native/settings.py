from transifex.common.utils import import_to_python
from transifex.native.cache import AbstractCache
from transifex.native.rendering import (AbstractErrorPolicy,
                                        AbstractRenderingPolicy, ChainedPolicy)


def parse_setting_class(obj):
    # obj is a tuple like (<path>, <params>)
    # or a string like <path>
    try:
        path, params = obj
    except ValueError:
        path, params = obj, None

    _class = import_to_python(path)
    if params:
        return _class(**params)
    return _class()


def parse_rendering_policy(policy):
    """Parse the given rendering policy and return an AbstractRenderingPolicy
    subclass.

    :param Union[AbstractRenderingPolicy, str, tuple(str, dict), list] policy:
        could be
        - an instance of AbstractRenderingPolicy
        - a tuple of the class's path and parameters
        - the class's path
        - a list of AbstractRenderingPolicy objects or tuples or string paths
    :return: an AbstractRenderingPolicy object
    :rtype: AbstractRenderingPolicy
    """
    if isinstance(policy, AbstractRenderingPolicy) or policy is None:
        return policy

    if isinstance(policy, list):
        return ChainedPolicy(*[parse_rendering_policy(p) for p in policy])

    return parse_setting_class(policy)


def parse_error_policy(policy):
    """Parse the given error policy and return an AbstractErrorPolicy
    subclass.

    :param Union[AbstractRenderingPolicy, str, tuple(str, dict)] policy:
        could be
        - an instance of AbstractErrorPolicy
        - a tuple of the class's path and parameters
        - the class's path
    :return: an AbstractErrorPolicy object
    :rtype: AbstractErrorPolicy
    """
    if isinstance(policy, AbstractErrorPolicy) or policy is None:
        return policy

    return parse_setting_class(policy)


def parse_cache(cache):
    """Parse the given cache and return an AbstractCache subclass.

    :param Union[AbstractCache, str, tuple(str, dict)] cache:
        could be
        - an instance of AbstractCache
        - a tuple of the class's path and parameters
        - the class's path
    :return: an AbstractCache object
    :rtype: AbstractCache
    """
    if isinstance(cache, AbstractCache) or cache is None:
        return cache

    return parse_setting_class(cache)
