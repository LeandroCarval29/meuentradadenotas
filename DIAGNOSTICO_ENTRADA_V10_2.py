from pathlib import Path
import sqlite3, sys
ROOT=Path(__file__).resolve().parent
DB=ROOT/'hnt_foodservice_v3.db'
print('HNT FoodService BI V10.2 - Diagnóstico Entrada NF / Produtos')
print('='*70)
if not DB.exists():
    print('ERRO: banco hnt_foodservice_v3.db não encontrado nesta pasta.')
    sys.exit(1)
c=sqlite3.connect(DB); c.row_factory=sqlite3.Row
try:
    p=c.execute("""select count(*) total,
        sum(case when coalesce(active,1)=1 then 1 else 0 end) ativos,
        sum(case when coalesce(active,1)=0 then 1 else 0 end) inativos from products""").fetchone()
    print(f"PRODUTOS: total={p['total'] or 0} | ativos={p['ativos'] or 0} | inativos={p['inativos'] or 0}")
    inv=c.execute("select count(*) n from invoices").fetchone()['n']
    print('NOTAS:',inv)
    pend=c.execute("""select count(*) n from invoice_items ii join invoices i on i.id=ii.invoice_id
                      where upper(i.status)<>'ENTRADA' and ii.product_id is null""").fetchone()['n']
    print('ITENS PENDENTES DE ASSOCIAÇÃO:',pend)
    ent=c.execute("select count(*) n from invoices where upper(status)='ENTRADA'").fetchone()['n']
    print('NOTAS EM ENTRADA:',ent)
    mov=c.execute("select count(*) n from movements where type='ENTRY'").fetchone()['n']
    print('MOVIMENTOS DE ENTRADA:',mov)
    bad=c.execute("""select count(*) n from invoices i where upper(i.status)='ENTRADA'
                     and (select count(*) from invoice_items ii where ii.invoice_id=i.id) !=
                         (select count(*) from movements m where m.invoice_id=i.id and m.type='ENTRY')""").fetchone()['n']
    print('DIVERGÊNCIAS NF x ESTOQUE:',bad)
finally:
    c.close()
print('='*70)
