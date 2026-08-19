from pathlib import Path
import sqlite3, sys

ROOT=Path(__file__).resolve().parent
FIXED=Path(r'C:\SAAS - DOWNTOWN\hnt_foodservice_v3.db')
DB=FIXED if FIXED.exists() else ROOT/'hnt_foodservice_v3.db'

print('HNT FOODSERVICE BI V11.3 - VALIDADOR DF-e/XML')
print('='*78)
print('Banco esperado:',DB)
print('App:',ROOT/'app.py')
print('Pasta XML:',ROOT/'xmls')
print('Pasta certificados:',ROOT/'certificados')

if DB.exists():
    c=sqlite3.connect(DB)
    c.row_factory=sqlite3.Row
    tables={r['name'] for r in c.execute("select name from sqlite_master where type='table'")}
    for t in ['dfe_docs','settings','invoices','invoice_items','mappings','movements','cost_master','cost_history']:
        print(f'{t}:', 'OK' if t in tables else 'AUSENTE / será criado se previsto pela migração')
    if 'dfe_docs' in tables:
        cols={r['name'] for r in c.execute("pragma table_info(dfe_docs)")}
        for col in ['recipient_cnpj','invoice_id','last_query_at','import_error','xml_sha256','full_xml','source_kind']:
            print(f'dfe_docs.{col}:', 'OK' if col in cols else 'será criado ao abrir V11.3')
    if 'settings' in tables:
        keys={r['key']:r['value'] for r in c.execute("select key,value from settings")}
        for k in ['cnpj','uf','ambiente','ult_nsu','pfx_path']:
            print(f'{k}:', keys.get(k,'NÃO CONFIGURADO'))
    c.close()
else:
    print('ATENÇÃO: banco não encontrado agora. Confirme o caminho antes de operar.')

backup=DB.with_name('hnt_foodservice_v3_BACKUP_PRE_V11_3.db')
print('Backup pré V11.3:', 'OK' if backup.exists() else 'será tentado na primeira abertura')

print('='*78)
print('VALIDAÇÃO FINALIZADA.')
input('ENTER para sair...')
