from pathlib import Path
import sqlite3, sys
FIXED=Path(r'C:\SAAS - DOWNTOWN\hnt_foodservice_v3.db')
ROOT=Path(__file__).resolve().parent
DB=FIXED if FIXED.exists() else ROOT/'hnt_foodservice_v3.db'
print('HNT V11.1 - VALIDACAO CONTROLE DE PRODUCAO')
print('='*72)
print('Banco:',DB)
if not DB.exists():
    print('ERRO: banco nao encontrado.')
    input('ENTER para sair...')
    sys.exit(1)
c=sqlite3.connect(DB);c.row_factory=sqlite3.Row
tables={r['name'] for r in c.execute("select name from sqlite_master where type='table'")}
required=['products','invoices','invoice_items','mappings','movements','cost_master',
          'controlled_products','production_recipes','production_recipe_items',
          'production_output','production_usage_actual','sushi_control_daily',
          'category_settings','category_alias_audit']
for t in required:
    print(f'{t}:', 'OK' if t in tables else 'SERÁ CRIADA/MIGRADA AO ABRIR O SISTEMA')
if 'products' in tables:
    print('Produtos:',c.execute("select count(*) n from products").fetchone()['n'])
if 'mappings' in tables:
    print('Associações fornecedor/SKU:',c.execute("select count(*) n from mappings").fetchone()['n'])
if 'sushi_control_daily' in tables:
    print('Fechamentos produção:',c.execute("select count(*) n from sushi_control_daily").fetchone()['n'])
c.close()
print('='*72)
print('A V11.1 usa o mesmo banco em C:\\SAAS - DOWNTOWN quando ele existir.')
input('ENTER para sair...')
