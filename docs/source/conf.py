import os
import sys

sys.path.insert(0, os.path.abspath('../..'))

# In order to find indirect dependency
sys.path.insert(0, os.path.abspath('../../..'))

# use a try to force not to reorder sys.path and import.
try:
    import _building
except Exception as e:
    raise e


(project,
 pkg,
 release,
 author,
 copyright,

 extensions,
 templates_path,
 exclude_patterns,
 master_doc,
 html_theme,
 html_static_path,
 ) = _building.sphinx_confs()
