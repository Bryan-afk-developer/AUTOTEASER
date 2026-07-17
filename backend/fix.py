from portal.shared.supabase_db import get_supabase_admin
sb = get_supabase_admin()
docs_resp = sb.table('documentos_expediente').select('*').like('tipo_documento', 'ec_%').execute()
from collections import defaultdict
grouped = defaultdict(list)
for doc in (docs_resp.data or []):
    if doc.get('cuenta_bancaria_id'):
        grouped[doc['cuenta_bancaria_id']].append(doc)

for cuenta_id, docs in grouped.items():
    print(f'Cuenta: {cuenta_id}, Docs: {len(docs)}')
    valid_docs = [d for d in docs if d.get('nombre_archivo') and '-' in d['nombre_archivo']]
    valid_docs.sort(key=lambda x: x['nombre_archivo'])
    
    for doc in valid_docs:
        sb.table('documentos_expediente').update({'tipo_documento': doc['tipo_documento'] + '_tmp'}).eq('id', doc['id']).execute()
        
    for i, doc in enumerate(valid_docs, 1):
        new_clave = f'ec_{cuenta_id}_{i}'
        name = doc['nombre_archivo']
        print(f'  -> {new_clave} ({name})')
        sb.table('documentos_expediente').update({'tipo_documento': new_clave}).eq('id', doc['id']).execute()

print('Done!')
