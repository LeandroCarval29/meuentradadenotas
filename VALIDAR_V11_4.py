from pathlib import Path
import sqlite3, ast

ROOT=Path(__file__).resolve().parent
APP=ROOT/'app.py'
FIXED=Path(r'C:\SAAS - DOWNTOWN\hnt_foodservice_v3.db')
DB=FIXED if FIXED.exists() else ROOT/'hnt_foodservice_v3.db'

print('HNT FOODSERVICE BI V11.4 - VALIDADOR')
print('='*78)
print('App:',APP)
print('Banco:',DB)

source=APP.read_text(encoding='utf-8')
ast.parse(source)
print('Sintaxe app.py: OK')

required=[
    'def product_invoice_cost_history',
    'def duplicate_category_groups',
    'def merge_category_group',
    "elif page=='Extrato de Itens':",
    "elif page=='Extrato de Custos':",
    'Alerta de Custo',
    'REABRIR NF E CORRIGIR',
    'UNIFICAR CATEGORIAS E CORRIGIR REFERÊNCIAS'
]
for item in required:
    print(item,':','OK' if item in source else 'AUSENTE')

if DB.exists():
    c=sqlite3.connect(DB)
    c.row_factory=sqlite3.Row
    tables={r['name'] for r in c.execute("select name from sqlite_master where type='table'")}
    for t in ['products','invoices','invoice_items','movements','cost_history','cost_master',
              'category_settings','loose_purchases','controlled_products','correction_audit']:
        print(t,':','OK' if t in tables else 'AUSENTE / conferir migração anterior')
    c.close()
else:
    print('ATENÇÃO: banco não encontrado neste caminho agora.')

backup=DB.with_name('hnt_foodservice_v3_BACKUP_PRE_V11_4.db')
print('Backup pré V11.4:', 'OK' if backup.exists() else 'será tentado na primeira abertura')
print('='*78)
input('ENTER para sair...')
