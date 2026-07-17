"""Full Drive sync with new folder structure for all companies."""
from app.drive_service import get_drive_service, get_shared_parent_folder, create_empresa_structure
from portal.shared.supabase_db import get_supabase_admin
from portal.Admin.dashboard import background_sync_all_to_drive

sb = get_supabase_admin()
empresas = sb.table('empresas').select('id, nombre').execute().data

service = get_drive_service()
parent_id = get_shared_parent_folder(service)

for emp in empresas:
    nombre = emp['nombre']
    emp_id = emp['id']
    print(f'Syncing: {nombre}...')
    estructura = create_empresa_structure(service, nombre, parent_id)
    background_sync_all_to_drive(emp_id, nombre, estructura, service)
    print(f'  Done: {nombre}')

print('ALL DONE - All companies synced to new structure!')
