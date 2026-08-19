from pathlib import Path
import sqlite3, ast, re
ROOT=Path(__file__).resolve().parent
app=ROOT/'app.py'
s=app.read_text(encoding='utf-8')
ast.parse(s)
checks={
 'tpAmb no request':'<tpAmb>{tp}</tpAmb>' in s,
 'diagnostico SEFAZ':'Diagnóstico SEFAZ — conexão, schema e consulta por chave' in s,
 'teste por chave':'TESTAR CONSULTA POR CHAVE' in s,
 'aba Importar Mix removida do st.tabs':"'Importar Mix',\n        'Itens / Filtros'" not in s,
 'controle proteínas preservado':"elif page=='Controle Produção Proteínas':" in s,
}
con=sqlite3.connect(ROOT/'hnt_foodservice_v3.db')
integrity=con.execute('pragma integrity_check').fetchone()[0]
prod=con.execute('select count(*) from products').fetchone()[0]
inv=con.execute('select count(*) from invoices').fetchone()[0]
con.close()
print('AST: OK')
for k,v in checks.items(): print(k,':','OK' if v else 'FALHOU')
print('DB integrity:',integrity)
print('Produtos:',prod,'Notas:',inv)
if integrity!='ok' or not all(checks.values()): raise SystemExit(1)
print('VALIDAÇÃO FINAL: OK')
