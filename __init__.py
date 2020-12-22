"""
package-name is utility to create sub process.

Execute a shell script::

    import pk3proc

    # execute a shell script

    returncode, out, err = pk3proc.shell_script('ls / | grep bin')
    print returncode
    print out
    # output:
    # > 0
    # > bin
    # > sbin

Run a command::

    # Unlike the above snippet, following statement does not start an sh process.
    returncode, out, err = pk3proc.command('ls', 'a*', cwd='/usr/local')

"""

# from .proc import CalledProcessError
# from .proc import ProcError

__version__ = "0.2.2"
__name__ = "k3proc"

from .proc import foo
from .proc import SomeError

class Bar(object):
    def foo(self):
        pass
