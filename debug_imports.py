import sys
import os

print('Python executable:', sys.executable)
print('CWD:', os.getcwd())
print('Script dir (__file__):', os.path.dirname(os.path.abspath(__file__)))
print('\nsys.path:')
for p in sys.path:
    print(' -', p)

app_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'app')
print('\nExpected app path:', app_path)
print('exists:', os.path.exists(app_path))
print('files:', os.listdir(app_path) if os.path.exists(app_path) else 'N/A')

try:
    import app
    print('\nImport app: OK')
    print('app.__file__ =', getattr(app, '__file__', None))
except Exception as e:
    print('\nImport app: FAILED')
    import traceback
    traceback.print_exc()
    sys.exit(1)

print('\nAll checks done.')
