from pathlib import Path
import sqlite3, sys
ROOT=Path(__file__).resolve().parent
DB=ROOT/'hnt_foodservice_v3.db'
print('HNT FoodService BI V10.1 - Validação de Entidades')
print('='*60)
if not DB.exists():
    print('Banco ainda não existe.')
    sys.exit(0)
c=sqlite3.connect(DB);c.row_factory=sqlite3.Row
checks=[
 ('Itens NF sem nota',"select count(*) n from invoice_items ii left join invoices i on i.id=ii.invoice_id where i.id is null"),
 ('Itens NF com produto inexistente',"select count(*) n from invoice_items ii left join products p on p.id=ii.product_id where ii.product_id is not null and p.id is null"),
 ('Movimentos com produto inexistente',"select count(*) n from movements m left join products p on p.id=m.product_id where p.id is null"),
 ('Movimentos NF sem nota',"select count(*) n from movements m left join invoices i on i.id=m.invoice_id where m.invoice_id is not null and i.id is null"),
 ('Custos com produto inexistente',"select count(*) n from cost_history ch left join products p on p.id=ch.product_id where p.id is null"),
 ('NF ENTRADA divergente',"select count(*) n from invoices i where upper(i.status)='ENTRADA' and (select count(*) from invoice_items ii where ii.invoice_id=i.id)!=(select count(*) from movements m where m.invoice_id=i.id and m.type='ENTRY')")
]
for name,q in checks:
    try:n=int(c.execute(q).fetchone()['n'] or 0);print(f'{name}:', 'OK' if n==0 else f'REVISAR ({n})')
    except Exception as e:print(name+': ERRO -',e)
try:
    v=c.execute("select count(*) n from sqlite_master where type='view' and name='v_stock_position'").fetchone()['n']
    print('View de estoque:', 'OK' if v else 'será criada ao abrir V10.1')
except Exception as e:print('View de estoque:',e)
c.close()
print('='*60)
