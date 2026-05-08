import py_compile, glob, os

os.chdir(r'D:\AI_Project\Surprise\Interview-Practice-App\backend')

errors = []
count = 0
for f in glob.glob('app/**/*.py', recursive=True):
    count += 1
    try:
        py_compile.compile(f, doraise=True)
    except py_compile.PyCompileError as e:
        errors.append(str(e))

if errors:
    for e in errors:
        print(f'FAIL: {e}')
else:
    print(f'All {count} files passed syntax check')
