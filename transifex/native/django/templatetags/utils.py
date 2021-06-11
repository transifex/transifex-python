from parsimonious.nodes import NodeVisitor
from pyseeyou.grammar import ICUMessageFormat


class IcuKeysVisitor(NodeVisitor):
    """ This visits ASTs produced by the ICUMessageFormat grammar. Its goal is
        to extract all parameter names that it will need to compile. For this,
        it implements the `visit_id` method which captures the 'id' rule of the
        grammar, which applies to parameter names.

        Unfortunately, it also captures some other strings, like the names of
        the plural rules in plural statements. So, if what you want is the set
        of all parameter names the ICU template can accept, be aware that you
        will get a "slightly bigger superset" of that.
    """

    def __init__(self):
        self.keys = set()

    def generic_visit(self, node, visited_children):
        return visited_children or node

    def visit_id(self, node, *args, **kwargs):
        self.keys.add(str(node.text))


def get_icu_keys(msg):
    """ Get the names of the parameters that the 'msg' ICU template needs in
        order to compile.

        :param str msg: The ICU template to be parsed
        :return: A "slightly bigger superset" of the parameter names
        :rtype: set
    """

    v = IcuKeysVisitor()
    try:
        ast = ICUMessageFormat.parse(msg)
        v.visit(ast)
    except Exception:
        return set()
    return v.keys
