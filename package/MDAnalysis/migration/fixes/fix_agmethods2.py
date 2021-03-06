'''
run with: python ten2eleven.py -f agmethods2 test_dummy_old_MDA_code.py 
Author: Tyler Reddy
'''

from lib2to3.fixer_base import BaseFix
from lib2to3.fixer_util import Name, Call, LParen, RParen, ArgList, Dot
from lib2to3 import pytree


class FixAgmethods2(BaseFix):

    PATTERN = """
        power< head =any+
                trailer< dot = '.' method=('bond'|'angle'|'torsion'|
                                         'improper')>
                                parens=trailer< '(' ')' >
                                tail=any*>
    """

    def transform(self, node, results):
        head = results['head']
        method = results['method'][0]
        tail = results['tail']
        syms = self.syms
        method_name = method.value
        if method_name == 'torsion':
            method_name = 'dihedral'
        head = [n.clone() for n in head]
        tail = [n.clone() for n in tail]
        args = head + [pytree.Node(syms.trailer, [Dot(), Name(method_name, prefix = method.prefix), Dot(), Name('value'), LParen(), RParen()])]
        new = pytree.Node(syms.power, args)
        return new

