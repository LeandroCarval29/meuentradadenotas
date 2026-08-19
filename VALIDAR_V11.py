from pathlib import Path
import sqlite3, sys

FIXED=Path(r'C:\SAAS - DOWNTOWN\hnt_foodservice_v3.db')
ROOT=Path(__file__).resolve().parent
DB=FIXED if FIXED.exists() else ROOT/'hnt_foodservice_v3.db'

print('HNT FOODSERVICE BI V11 - VALIDACAO')
print('='*70)
print('Banco:',DB)
if not DB.exists():
    print('ERRO: banco nao encontrado.')
    input('ENTER para sair...')
    sys.exit(1)

c=sqlite3.connect(DB);c.row_factory=sqlite3.Row
tables={r['name'] for r in c.execute("select name from sqlite_master where type='table'")}
needed=['products','invoices','invoice_items','movements','inventory','sales_daily',
        'loose_purchases','category_settings','controlled_products',
        'production_recipes','production_recipe_items','production_output','sushi_control_daily']
for t in needed:
    print(f'{t}:', 'OK' if t in tables else 'SERÁ CRIADA AO ABRIR A V11')

for t in ['products','invoices','invoice_items','movements','sales_daily']:
    if t in tables:
        print(f'{t} registros:',c.execute(f"select count(*) n from {t}").fetchone()['n'])

if 'sales_daily' in tables:
    r=c.execute("""select coalesce(sum(case when upper(source)='3S' then gross_sales else net_store end),0) v,
                          coalesce(sum(tickets),0) t
                   from sales_daily""").fetchone()
    print('Venda consolidada acumulada:',round(float(r['v'] or 0),2))
    print('Clientes/tickets acumulados:',int(r['t'] or 0))

c.close()
print('='*70)
print('IMPORTANTE: a V11 usa diretamente C:\\SAAS - DOWNTOWN\\hnt_foodservice_v3.db quando ele existir.')
input('ENTER para sair...')
