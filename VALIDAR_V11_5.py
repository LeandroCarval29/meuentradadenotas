from pathlib import Path
import ast, sqlite3

ROOT=Path(__file__).resolve().parent
APP=ROOT/'app.py'
FIXED=Path(r'C:\SAAS - DOWNTOWN\hnt_foodservice_v3.db')
ENV_DATA=__import__('os').environ.get('HNT_DATA_DIR','')
DB=Path(__import__('os').environ.get('HNT_DB_PATH','')) if __import__('os').environ.get('HNT_DB_PATH') else (
    Path(ENV_DATA)/'hnt_foodservice_v3.db' if ENV_DATA else (FIXED if FIXED.exists() else ROOT/'hnt_foodservice_v3.db')
)

print('HNT FOODSERVICE BI V11.5 - VALIDADOR')
print('='*78)
print('App:',APP)
print('Banco:',DB)
source=APP.read_text(encoding='utf-8')
ast.parse(source)
print('Sintaxe/AST: OK')

features=[
    'create table if not exists app_users',
    'def authenticate_user',
    'Usuários & Acessos',
    'HNT_DATA_DIR',
    'HNT_DB_PATH',
    '@st.cache_data(ttl=12',
    'ix_products_active_category_name',
    'BACKUP_PRE_V11_5'
]
for f in features:
    print(f,':','OK' if f in source else 'AUSENTE')

if DB.exists():
    c=sqlite3.connect(DB)
    tables={r[0] for r in c.execute("select name from sqlite_master where type='table'")}
    print('Tabela app_users:', 'OK' if 'app_users' in tables else 'será criada ao abrir V11.5')
    c.close()
else:
    print('Banco ainda não encontrado neste caminho.')

print('railway.toml:', 'OK' if (ROOT/'railway.toml').exists() else 'AUSENTE')
print('.gitignore:', 'OK' if (ROOT/'.gitignore').exists() else 'AUSENTE')
print('='*78)
input('ENTER para sair...')
