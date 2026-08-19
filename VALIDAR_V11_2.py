from pathlib import Path
import sqlite3, sys, pandas as pd

FIXED=Path(r'C:\SAAS - DOWNTOWN\hnt_foodservice_v3.db')
ROOT=Path(__file__).resolve().parent
DB=FIXED if FIXED.exists() else ROOT/'hnt_foodservice_v3.db'

print('HNT V11.2 - VALIDACAO CONTROLE DE PRODUCAO PROTEINAS')
print('='*78)
print('Banco:',DB)

if not DB.exists():
    print('ATENCAO: banco nao encontrado neste caminho.')
    print('Abra a V11.2 somente depois de confirmar qual banco deve ser usado.')
else:
    c=sqlite3.connect(DB)
    c.row_factory=sqlite3.Row
    tables={r['name'] for r in c.execute("select name from sqlite_master where type='table'")}
    required=[
        'products','controlled_products','production_recipes','production_recipe_items',
        'production_output','sushi_control_daily',
        'protein_sales_imports','protein_sales_rows','protein_menu_catalog',
        'protein_technical_sheets','protein_mapping_audit'
    ]
    for t in required:
        print(f'{t}:', 'OK' if t in tables else 'SERÁ CRIADA/MIGRADA AO ABRIR A V11.2')

    for t,label in [
        ('products','Produtos'),
        ('protein_sales_imports','Mix importados'),
        ('protein_menu_catalog','Itens catálogo'),
        ('protein_technical_sheets','Fichas técnicas')
    ]:
        if t in tables:
            try:print(f'{label}:',c.execute(f"select count(*) n from {t}").fetchone()['n'])
            except Exception as ex:print(f'{label}: erro ao contar - {ex}')
    c.close()

initial=ROOT/'dados_iniciais'/'Mix_Produtos_Canal_Venda.xlsx'
print('-'*78)
print('Arquivo inicial incluído:',initial)
if initial.exists():
    try:
        raw=pd.read_excel(initial,sheet_name=0,header=None,nrows=20)
        print('Leitura XLSX inicial: OK')
    except Exception as ex:
        print('Leitura XLSX inicial: ERRO',ex)
else:
    print('Arquivo inicial: NÃO ENCONTRADO')

mapping=ROOT/'dados_iniciais'/'MAPEAMENTO_INICIAL_GRUPOS_PROTEINAS.json'
print('Mapeamento inicial JSON:', 'OK' if mapping.exists() else 'NÃO ENCONTRADO')

backup=DB.with_name('hnt_foodservice_v3_BACKUP_PRE_V11_2.db') if DB else None
if DB.exists():
    print('Backup pré V11.2:', 'OK' if backup.exists() else 'será tentado na primeira abertura da V11.2')

print('='*78)
print('VALIDAÇÃO FINALIZADA.')
input('ENTER para sair...')
