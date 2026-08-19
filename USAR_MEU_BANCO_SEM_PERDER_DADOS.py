from pathlib import Path
from datetime import datetime
import shutil, sqlite3, sys

ROOT=Path(__file__).resolve().parent
TARGET=ROOT/'hnt_foodservice_v3.db'
print('HNT V10.5 - USAR MEU BANCO SEM PERDER DADOS')
print('='*65)
base=ROOT.parent
found=[]
for p in base.glob('*/hnt_foodservice_v3.db'):
    if p.resolve()!=TARGET.resolve():
        found.append(p)
found=sorted(found,key=lambda p:p.stat().st_mtime,reverse=True)
if not found:
    print('Nenhum banco anterior encontrado automaticamente.')
    print('Copie manualmente hnt_foodservice_v3.db da versão atual para esta pasta.')
    input('ENTER para sair...')
    sys.exit(0)
for i,p in enumerate(found,1):
    try:
        c=sqlite3.connect(p); prod=c.execute("select count(*) from products").fetchone()[0]; inv=c.execute("select count(*) from invoices").fetchone()[0]; c.close()
    except Exception: prod=inv=-1
    print(f'[{i}] Produtos={prod} | Notas={inv} | {p}')
print('[0] Cancelar')
try:choice=int(input('Escolha o banco: ').strip())
except Exception:choice=0
if choice<1 or choice>len(found):sys.exit(0)
source=found[choice-1]
if TARGET.exists():
    backup=ROOT/f"hnt_foodservice_v3_BACKUP_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
    shutil.copy2(TARGET,backup)
    print('Backup criado:',backup.name)
shutil.copy2(source,TARGET)
print('Banco copiado sem apagar os dados históricos.')
input('ENTER para sair...')
