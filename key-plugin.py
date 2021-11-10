import optparse
import sys
from json import dumps
from pyang.plugin import PyangPlugin, plugins, register_plugin, init
from pyang.repository import FileRepository
from pyang.context import Context
from pyang.error import error_codes, allow_warning
from pyang import syntax
from pyang.statements import ContainerStatement, ListStatement, LeafLeaflistStatement


def pyang_plugin_init():
    register_plugin(KeysPlugin())

class KeysPlugin(PyangPlugin):
    def __init__(self):
        PyangPlugin.__init__(self, "keys")

    def add_output_format(self, fmts):
        self.multiple_modules = True
        fmts["keys"] = self

    def add_opts(self, optparser):
        optlist: List[Any] = [
            optparse.make_option(
                "--keys-help", dest="keys_help", action="store_true", help="Print help for keys output and exit",
            )
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
        yang_dict = {}
        for module in modules:
            keys = []
            leaves = []
            paths = []
            try:
                self.recurse_on_container_for_keys_and_leaves(module, keys, leaves)
                keys = list(set(keys))
                leaves = [dict(t) for t in {tuple(d.items()) for d in leaves}]
                self.recurse_on_container_for_paths(module, paths, [])
                paths = [f"{module.arg}:{path}" for path in paths]
                yang_dict[module.arg] = {"keys": keys, "paths": paths, "leaves": leaves}
            except Exception as e:
                print("error")
                print(e)
        fd.write(dumps(yang_dict))

    def recurse_on_container_for_keys_and_leaves(self, module, keywords, leafwords):
        for child in module.i_children:
            if isinstance(child, (ContainerStatement, ListStatement)):
                if isinstance(child, ListStatement):
                    has_key = child.search("key")
                    if has_key:
                        for key in has_key:
                            keywords.extend(str(key).split(" ")[1:])
                self.recurse_on_container_for_keys_and_leaves(child, keywords, leafwords)
            if isinstance(child, LeafLeaflistStatement):
                for temp_obj in child.substmts:
                    if temp_obj.keyword == 'type':
                        leafwords.append({child.arg: temp_obj.arg})

    def recurse_on_container_for_paths(self, module, paths, build_path):
        for child in module.i_children:
            if isinstance(child, (ContainerStatement, ListStatement)):
                build_path.append(child.arg)
                self.recurse_on_container_for_paths(child, paths, build_path)
                build_path.pop()
            if isinstance(child, LeafLeaflistStatement):
                build_path.append(child.arg)
                paths.append('/'.join(build_path))
                build_path.pop()

