import compileall
import sys

ok = compileall.compile_dir("src/app", force=True)
if not ok:
    print("compile failed")
    sys.exit(1)
print("compile ok")
