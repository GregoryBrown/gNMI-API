import optparse
import sys
import re
import json

from pyang import plugin
from pyang import statements
from tree import TreePlugin

def pyang_plugin_init():
    plugin.register_plugin(KeysPlugin())

class KeysPlugin(plugin.PyangPlugin):
    def __init__(self):
        plugin.PyangPlugin.__init__(self, 'keys')

    def add_output_format(self, fmts):
        self.multiple_modules = True
        fmts['keys'] = self
        
    def add_opts(self, optparser):
        optlist = [
            optparse.make_option("--keys-help",
                                 dest="keys_help",
                                 action="store_true",
                                 help="Print help for keys output and exit")
            ]
        g = optparser.add_option_group("Keys output specific options")
        g.add_options(optlist)


    def setup_ctx(self, ctx):
        if ctx.opts.keys_help:
            print_help()
            sys.exit(0)

    def setup_fmt(self, ctx):
        ctx.implicit_errors = False

    def emit(self, ctx, modules, fd):
        keys_dict = {}
        for module in modules:
            try:
                keys = []
                self.recurse_on_container(module,keys)
                keys = list(set(keys))
                keys_dict[module.arg] = keys
            except Exception as e:
                print(e)
        print(json.dumps(keys_dict))
        
    def recurse_on_container(self, module, keywords):
        try:
            for child in module.i_children:
                if isinstance(child,statements.ContainerStatement) or isinstance(child,statements.ListStatement):
                    if isinstance(child,statements.ListStatement):
                        rc = child.search("key")
                        if rc:
                            for r in rc:
                                keywords.extend(str(r).split(' ')[1:])
                    self.recurse_on_container(child, keywords)
        except Exception as e:
            print(e)


def print_help():
    print("Keys Help")
