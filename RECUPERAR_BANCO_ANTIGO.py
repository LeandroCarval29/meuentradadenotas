from pathlib import Path
from datetime import datetime
import sqlite3, shutil, sys

ROOT=Path(__file__).resolve().parent
TARGET=ROOT/'hnt_foodservice_v3.db'

def stats(path):
    try:
        c=sqlite3.connect(path)
        products=c.execute("select count(*) from products").fetchone()[0] if c.execute("select count(*) from sqlite_master where type='table' and name='products'").fetchone()[0] else 0
        invoices=c.execute("select count(*) from invoices").fetchone()[0] if c.execute("select count(*) from sqlite_master where type='table' and name='invoices'").fetchone()[0] else 0
        c.close()
        return products,invoices
    except Exception:
        return -1,-1

bases=[ROOT.parent,ROOT.parent.parent]
found=[]
seen=set()
for base in bases:
    if not base.exists(): continue
    patterns=['*/hnt_foodservice_v3.db','*/*/hnt_foodservice_v3.db']
    for pattern in patterns:
        for p in base.glob(pattern):
            try:rp=p.resolve()
            except Exception:rp=p
            if rp==TARGET.resolve() or rp in seen:continue
            seen.add(rp);found.append(p)

found=sorted(found,key=lambda p:p.stat().st_mtime if p.exists() else 0,reverse=True)

print('RECUPERAÇÃO DE BANCO HNT - V10.2')
print('='*75)
if TARGET.exists():
    ps,ns=stats(TARGET)
    print(f'Banco atual: {TARGET}')
    print(f'Produtos: {ps} | Notas: {ns} | Tamanho: {TARGET.stat().st_size/1024/1024:.2f} MB')
else:
    print('A V10.2 ainda não possui banco de dados.')

print('\nBancos encontrados em versões anteriores:')
if not found:
    print('Nenhum banco anterior encontrado automaticamente.')
    print('Você também pode copiar manualmente o arquivo hnt_foodservice_v3.db para esta pasta.')
    input('\nPressione ENTER para sair...')
    sys.exit(0)

for i,p in enumerate(found,1):
    ps,ns=stats(p)
    stamp=datetime.fromtimestamp(p.stat().st_mtime).strftime('%d/%m/%Y %H:%M')
    print(f'[{i}] Produtos={ps} | Notas={ns} | {p.stat().st_size/1024/1024:.2f} MB | {stamp}')
    print(f'    {p}')

print('\n[0] Cancelar')
choice=input('\nDigite o número do banco que deseja usar na V10.2: ').strip()
try:n=int(choice)
except Exception:n=0
if n<1 or n>len(found):
    print('Operação cancelada.')
    input('Pressione ENTER para sair...')
    sys.exit(0)

source=found[n-1]
if TARGET.exists():
    backup=ROOT/f"hnt_foodservice_v3_BACKUP_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
    shutil.copy2(TARGET,backup)
    print(f'Backup do banco atual criado: {backup.name}')

shutil.copy2(source,TARGET)
ps,ns=stats(TARGET)
print('\nBANCO RECUPERADO COM SUCESSO.')
print(f'Produtos: {ps} | Notas: {ns}')
print(f'Destino: {TARGET}')
input('\nPressione ENTER para sair...')
