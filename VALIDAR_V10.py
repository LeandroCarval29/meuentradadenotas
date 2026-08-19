from pathlib import Path
import sqlite3, sys
ROOT=Path(__file__).resolve().parent
DB=ROOT/'hnt_foodservice_v3.db'
print('HNT FoodService BI V10 - Validação Local')
print('='*50)
if not DB.exists():
    print('BANCO: ainda não existe. Será criado na primeira abertura.')
    sys.exit(0)
c=sqlite3.connect(DB);c.row_factory=sqlite3.Row
tables={r['name'] for r in c.execute("select name from sqlite_master where type='table'")}
needed={'products','suppliers','invoices','invoice_items','movements','cost_history','cost_master','sales_daily'}
missing=sorted(needed-tables)
print('TABELAS:', 'OK' if not missing else 'FALTANDO '+', '.join(missing))
if {'invoices','invoice_items','movements'}.issubset(tables):
    bad=c.execute("""select count(*) n from invoices i
        where upper(i.status)='ENTRADA'
          and (select count(*) from invoice_items ii where ii.invoice_id=i.id) !=
              (select count(*) from movements m where m.invoice_id=i.id and m.type='ENTRY')""").fetchone()['n']
    print('NF ENTRADA x MOVIMENTOS:', 'OK' if bad==0 else f'ATENÇÃO: {bad} divergência(s)')
if 'sales_daily' in tables:
    n=c.execute('select count(*) n from sales_daily').fetchone()['n']
    print('VENDAS DIÁRIAS:',n)
c.close()
print('='*50)
print('Validação concluída.')
