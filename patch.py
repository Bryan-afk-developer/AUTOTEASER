import os, glob
path = 'backend/portal/Cliente/*.py'
for file in glob.glob(path):
    with open(file, 'r', encoding='utf-8') as f:
        content = f.read()
    new_content = content.replace('.eq("user_id", user_info["user_id"])', '.eq("id", user_info["empresa_id"])')
    if new_content != content:
        with open(file, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print('Patched', file)
