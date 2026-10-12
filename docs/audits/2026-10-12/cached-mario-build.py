from types import SimpleNamespace
import sys
from pathlib import Path
sys.path.insert(0,str(Path.cwd()/'scripts'))
import soc
try:
    soc.firmware(SimpleNamespace(cc='clang',objcopy=None,app='mario',boot=None,image_name='repo-audit-mario',use_sdram=False,extra_flags=[]))
except Exception as exc:
    print('REPRODUCED:',repr(exc));sys.exit(1)
