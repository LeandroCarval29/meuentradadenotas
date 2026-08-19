import os
import shutil
import hashlib
import streamlit as st
import streamlit.components.v1 as components
import sqlite3, io, re, base64, gzip, unicodedata, os, subprocess, tempfile, json, json, difflib, hmac, secrets
from pathlib import Path
from datetime import datetime, timedelta, date
import pandas as pd
import requests
import plotly.express as px
import math
import calendar
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.graphics.barcode import createBarcodeDrawing
from reportlab.graphics import renderPDF, renderSVG
from reportlab.lib.utils import ImageReader
from lxml import etree
from requests_pkcs12 import post as pkcs12_post
from cryptography.hazmat.primitives.serialization import pkcs12
from catalog import CATALOG

ROOT=Path(__file__).resolve().parent
ENV_DATA_DIR=str(os.environ.get('HNT_DATA_DIR','') or '').strip()
ENV_DB_PATH=str(os.environ.get('HNT_DB_PATH','') or '').strip()
DATA_DIR=Path(ENV_DATA_DIR) if ENV_DATA_DIR else ROOT
DATA_DIR.mkdir(parents=True,exist_ok=True)
FIXED_DB=Path(r'C:\SAAS - DOWNTOWN\hnt_foodservice_v3.db')
if ENV_DB_PATH:
    DB=Path(ENV_DB_PATH)
elif ENV_DATA_DIR:
    DB=DATA_DIR/'hnt_foodservice_v3.db'
elif FIXED_DB.exists():
    DB=FIXED_DB
else:
    DB=ROOT/'hnt_foodservice_v3.db'
DB.parent.mkdir(parents=True,exist_ok=True)

# V11: backup único antes das migrações aditivas.
try:
    if DB.exists():
        _pre_v11=DB.with_name('hnt_foodservice_v3_BACKUP_PRE_V11.db')
        if not _pre_v11.exists():
            shutil.copy2(DB,_pre_v11)
except Exception:
    pass

# V11.2: backup adicional antes das tabelas de Mix/Fichas Técnicas.
V112_BACKUP_WARNING=''
try:
    if DB.exists():
        _pre_v112=DB.with_name('hnt_foodservice_v3_BACKUP_PRE_V11_2.db')
        if not _pre_v112.exists():
            shutil.copy2(DB,_pre_v112)
except Exception as _backup_ex:
    V112_BACKUP_WARNING=str(_backup_ex)

# V11.3: backup antes da evolução DF-e/XML automático.
V113_BACKUP_WARNING=''
try:
    if DB.exists():
        _pre_v113=DB.with_name('hnt_foodservice_v3_BACKUP_PRE_V11_3.db')
        if not _pre_v113.exists():
            shutil.copy2(DB,_pre_v113)
except Exception as _backup_ex:
    V113_BACKUP_WARNING=str(_backup_ex)

# V11.4: backup antes da evolução dos extratos críticos e unificação de categorias.
V114_BACKUP_WARNING=''
try:
    if DB.exists():
        _pre_v114=DB.with_name('hnt_foodservice_v3_BACKUP_PRE_V11_4.db')
        if not _pre_v114.exists():
            shutil.copy2(DB,_pre_v114)
except Exception as _backup_ex:
    V114_BACKUP_WARNING=str(_backup_ex)

# V11.5: backup antes de usuários, performance e hospedagem.
V115_BACKUP_WARNING=''
try:
    if DB.exists():
        _pre_v115=DB.with_name('hnt_foodservice_v3_BACKUP_PRE_V11_5.db')
        if not _pre_v115.exists():
            shutil.copy2(DB,_pre_v115)
except Exception as _backup_ex:
    V115_BACKUP_WARNING=str(_backup_ex)

# V11.5.1: backup antes da nova regra de custo médio trimestral.
V1151_BACKUP_WARNING=''
try:
    if DB.exists():
        _pre_v1151=DB.with_name('hnt_foodservice_v3_BACKUP_PRE_V11_5_1.db')
        if not _pre_v1151.exists():
            shutil.copy2(DB,_pre_v1151)
except Exception as _backup_ex:
    V1151_BACKUP_WARNING=str(_backup_ex)

TEMPLATES=ROOT/'templates'
CERT_DIR=DATA_DIR/'certificados'
XML_DIR=DATA_DIR/'xmls'
CERT_DIR.mkdir(exist_ok=True); XML_DIR.mkdir(exist_ok=True)
SEFAZ_PROD='https://www1.nfe.fazenda.gov.br/NFeDistribuicaoDFe/NFeDistribuicaoDFe.asmx'
SEFAZ_HOM='https://hom1.nfe.fazenda.gov.br/NFeDistribuicaoDFe/NFeDistribuicaoDFe.asmx'
SEFAZ_EVENT_PROD='https://www.nfe.fazenda.gov.br/NFeRecepcaoEvento4/NFeRecepcaoEvento4.asmx'
SEFAZ_EVENT_HOM='https://hom1.nfe.fazenda.gov.br/NFeRecepcaoEvento4/NFeRecepcaoEvento4.asmx'
DAYS=['SEGUNDA','TERÇA','QUARTA','QUINTA','SEXTA','SÁBADO','DOMINGO']
LOSS_CAUSES=['Validade vencida','Quebra/avaria','Erro de produção','Erro de armazenamento','Descongelamento inadequado','Contaminação','Sobra de produção','Descarte operacional','Furto/desvio','Divergência de inventário','Qualidade do fornecedor','Erro de porcionamento','Erro de pedido','Outro']

WEIGHABLE_CATEGORY_TOKENS=['HORTIFRUTI','PROTEIN','PEIX','FRANGO','LATIC']

def db():
    # SQLite otimizado para uso local do ERP.
    c=sqlite3.connect(DB, timeout=30.0)
    c.row_factory=sqlite3.Row
    c.execute('PRAGMA busy_timeout=30000')
    c.execute('PRAGMA foreign_keys=ON')
    c.execute('PRAGMA synchronous=NORMAL')
    c.execute('PRAGMA temp_store=MEMORY')
    c.execute('PRAGMA cache_size=-64000')
    try:c.execute('PRAGMA mmap_size=268435456')
    except Exception:pass
    return c

@st.cache_data(ttl=10,show_spinner=False)
def _decimal_places_cached():
    try:
        c=db();r=c.execute("select value from settings where key='decimal_places'").fetchone();c.close()
        n=int(r['value']) if r else 3
        return max(0,min(3,n))
    except Exception:
        return 3

def decimal_places():
    return _decimal_places_cached()

def num_format(decimals=None):
    n=decimal_places() if decimals is None else max(0,min(3,int(decimals)))
    return '%.'+str(n)+'f'

def round_entry(value):
    try:return round(float(value),decimal_places())
    except Exception:return 0.0

def brl(value):
    try: s=f'{float(value):,.2f}'
    except Exception: return 'R$ 0,00'
    return 'R$ '+s.replace(',', 'X').replace('.', ',').replace('X','.')

def brl6(value):
    try: s=f'{float(value):,.6f}'
    except Exception: return 'R$ 0,000000'
    return 'R$ '+s.replace(',', 'X').replace('.', ',').replace('X','.')

def short_date(value):
    try:return pd.to_datetime(value).strftime('%d/%m/%y')
    except Exception:return str(value or '')

def month_week(value):
    d=pd.to_datetime(value).date()
    day=d.day
    # Regra operacional HNT sem sobreposição:
    # 1-7 = 1ª | 8-14 = 2ª | 15-21 = 3ª | 22-fim do mês = 4ª.
    # Os limites 14 e 21 ficam na semana anterior para que nenhum dia seja contado duas vezes.
    return '1ª semana' if day<=7 else ('2ª semana' if day<=14 else ('3ª semana' if day<=21 else '4ª semana'))

def fixed_month_week_ranges(a,b):
    """Quebra qualquer período em semanas fixas do mês conforme regra operacional HNT."""
    a=pd.to_datetime(a).date(); b=pd.to_datetime(b).date()
    if b<a:return []
    out=[]
    cur=date(a.year,a.month,1)
    while cur<=b:
        last_day=calendar.monthrange(cur.year,cur.month)[1]
        month_end=date(cur.year,cur.month,last_day)
        specs=[('1ª semana',1,7),('2ª semana',8,14),('3ª semana',15,21),('4ª semana',22,last_day)]
        for label,d1,d2 in specs:
            start=max(a,date(cur.year,cur.month,d1))
            end=min(b,date(cur.year,cur.month,d2))
            if start<=end:
                out.append({
                    'Mês':f'{cur.month:02d}/{cur.year}',
                    'Semana':label,
                    'Início':start,
                    'Fim':end
                })
        if cur.month==12:cur=date(cur.year+1,1,1)
        else:cur=date(cur.year,cur.month+1,1)
    return out

def app_log(module,action,details=''):
    try:
        c=db();cfg={r['key']:r['value'] for r in c.execute('select * from settings').fetchall()}
        auth=st.session_state.get('_auth_user') or {}
        uname=auth.get('full_name') or auth.get('username') or cfg.get('nome_usuario','Operador')
        c.execute('insert into app_logs(log_date,user_name,module,action,details,device) values(?,?,?,?,?,?)',
          (datetime.now().isoformat(timespec='seconds'),uname,module,action,str(details),cfg.get('tipo_dispositivo','Computador')))
        c.commit();c.close()
    except Exception:pass

def ean13(code):
    base=('290'+str(code).zfill(9))[-12:]; sm=sum(int(ch)*(1 if i%2==0 else 3) for i,ch in enumerate(base)); return base+str((10-sm%10)%10)

def infer_brand(name):
    n=(name or '').upper()
    brands=['COCA-COLA','SPRITE','FANTA','SCHWEPPES','DEL VALLE','POWERADE','MONSTER','RED BULL','PEPSI','GATORADE','GUARANÁ ANTARCTICA','GUARANA ANTARCTICA','H2OH!','LIPTON','LEÃO','LEAO','MATTE LEÃO','MATTE LEAO','FEEL GOOD','HEINEKEN']
    for b in brands:
        if b in n:
            return b.title().replace('Coca-Cola'.title(),'Coca-Cola').replace('Pepsi'.title(),'Pepsi').replace('H2Oh!','H2OH!')
    return ''

def init():
    c=db()
    try: c.execute('PRAGMA journal_mode=WAL')
    except Exception: pass
    c.executescript('''
    create table if not exists products(id integer primary key,code integer unique,internal_barcode text unique,name text,category text,subcategory text,unit text,active integer default 1,notes text default '');
    create table if not exists product_barcodes(id integer primary key,product_id integer,barcode text unique,description text);
    create table if not exists suppliers(id integer primary key,cnpj text unique,legal_name text,trade_name text,ie text,address text,phone text default '',email text default '',active integer default 1);
    create table if not exists invoices(id integer primary key,access_key text unique,number text,series text,issue_date text,entry_date text,supplier_id integer,total real,status text default 'PENDENTE',notes text default '',source text default 'XML');
    create table if not exists invoice_items(id integer primary key,invoice_id integer,supplier_code text,barcode text,description text,ncm text,cfop text,xml_unit text,xml_qty real,xml_unit_value real,xml_total real,product_id integer,multiplier real default 1,conversion real default 1,converted_qty real default 0,converted_unit_cost real default 0);
    create table if not exists mappings(id integer primary key,supplier_id integer,supplier_code text,supplier_barcode text,supplier_description text,product_id integer,multiplier real,conversion real,unique(supplier_id,supplier_code));
    create table if not exists movements(id integer primary key,product_id integer,movement_date text,type text,qty real,unit_cost real,reference text,notes text);
    create table if not exists losses(id integer primary key,product_id integer,loss_date text,qty real,unit_cost real,cause text,notes text);
    create table if not exists inventory(id integer primary key,inventory_date text,product_id integer,counted_qty real,avg_cost_3m real,total_value real,notes text);
    create table if not exists sales(id integer primary key,sale_date text,store text,net_sales real,gross_sales real,service real,delivery real,notes text);
    create table if not exists purchase_schedule(id integer primary key,product_id integer,order_day text,supply_group text,frequency text,target_stock real,min_stock real,active integer default 1,notes text,unique(product_id,order_day,supply_group));
    create table if not exists counts(id integer primary key,count_date text,product_id integer,order_day text,supply_group text,counted_qty real,target_stock real,suggested_qty real,notes text);
    create table if not exists quotes(id integer primary key,quote_id text,quote_date text,product_id integer,supplier_id integer,qty real,purchase_unit text,conversion real,offer_price real,freight real,discount real,unit_cost real,lead_days integer,valid_until text,notes text);
    create table if not exists dfe_docs(id integer primary key,nsu text unique,schema text,access_key text,issuer_cnpj text,issuer_name text,issue_date text,total real,status text,xml_path text,received_at text);
    create table if not exists settings(key text primary key,value text);
    create table if not exists cost_master(id integer primary key,product_id integer unique,current_cost real,updated_at text,notes text);
    create table if not exists stock_policy(id integer primary key,product_id integer unique,lead_days real default 7,review_days real default 7,service_factor real default 1.65,notes text);
    create table if not exists app_logs(id integer primary key,log_date text,user_name text,module text,action text,details text,device text);
    create unique index if not exists ux_sales_day_store on sales(sale_date,store);
    ''')
    # Migração V4.1: campo Marca no cadastro mestre.
    cols=[r['name'] for r in c.execute("pragma table_info(products)").fetchall()]
    if 'brand' not in cols:
        c.execute("alter table products add column brand text default ''")
    # Seed e migração do catálogo: adiciona itens novos sem duplicar o cadastro existente.
    next_code=c.execute('select coalesce(max(code),100000)+1 x from products').fetchone()['x']
    for cat,sub,name,u in CATALOG:
        exists=c.execute('select id from products where category=? and subcategory=? and name=?',(cat,sub,name)).fetchone()
        if exists:
            continue
        code=next_code; next_code+=1
        bc=ean13(code)
        cur=c.execute('insert into products(code,internal_barcode,name,category,subcategory,unit,brand) values(?,?,?,?,?,?,?)',(code,bc,name,cat,sub,u,infer_brand(name)))
        c.execute('insert or ignore into product_barcodes(product_id,barcode,description) values(?,?,?)',(cur.lastrowid,bc,'Código interno'))
    # Preenche marcas reconhecíveis nos cadastros existentes sem sobrescrever marcas informadas pelo usuário.
    for r in c.execute("select id,name,brand from products where coalesce(brand,'')=''").fetchall():
        b=infer_brand(r['name'])
        if b: c.execute('update products set brand=? where id=?',(b,r['id']))

    # Controle de edição/reimportação de notas e ciclo de inventários
    for stmt in [
        "alter table invoices add column edit_status text default 'FECHADA'",
        "alter table movements add column invoice_id integer",
        "alter table movements add column inventory_session_id integer",
        "alter table inventory add column session_id integer",
        "alter table inventory add column row_status text default 'FECHADO'"
    ]:
        try:
            c.execute(stmt)
        except Exception:
            pass

    c.execute("""create table if not exists inventory_sessions(
        id integer primary key,
        inventory_date text not null,
        name text not null,
        status text default 'ABERTO',
        created_at text,
        closed_at text,
        notes text default ''
    )""")
    c.execute("""create table if not exists invoice_audit(
        id integer primary key,
        invoice_id integer,
        event_date text,
        action text,
        details text
    )""")

    # V4.3 Local Stable 5 - tabelas adicionais sem apagar dados existentes.
    c.execute("""create table if not exists supplier_catalog_items(
        id integer primary key,
        supplier_id integer not null,
        supplier_code text,
        barcode text,
        description text not null,
        unit text,
        pack_qty real default 1,
        supplier_price real default 0,
        product_id integer,
        multiplier real default 1,
        conversion real default 1,
        active integer default 1,
        source_file text,
        updated_at text,
        unique(supplier_id,supplier_code)
    )""")
    c.execute("""create table if not exists cost_history(
        id integer primary key,
        product_id integer not null,
        event_date text not null,
        cost real not null,
        source text,
        reference text,
        notes text
    )""")
    c.execute("""create table if not exists correction_audit(
        id integer primary key,
        event_date text,
        module text,
        record_id text,
        action text,
        before_json text,
        after_json text
    )""")
    for stmt in [
        "alter table dfe_docs add column recipient_cnpj text default ''",
        "alter table dfe_docs add column invoice_id integer",
        "alter table dfe_docs add column last_query_at text default ''",
        "alter table dfe_docs add column import_error text default ''",
        "alter table dfe_docs add column xml_sha256 text default ''",
        "alter table dfe_docs add column full_xml integer default 0",
        "alter table dfe_docs add column downloaded_at text default ''",
        "alter table dfe_docs add column source_kind text default ''",
        "alter table settings add column reserved text default ''"
    ]:
        try:c.execute(stmt)
        except Exception:pass


    c.executescript("""
    create table if not exists dfe_sync_log(
        id integer primary key,
        event_date text,
        mode text,
        access_key text,
        ult_nsu_before text,
        ult_nsu_after text,
        max_nsu text,
        cstat text,
        message text,
        docs_received integer default 0,
        success integer default 1
    );
    create index if not exists ix_dfe_sync_log_date on dfe_sync_log(event_date);
    create index if not exists ix_dfe_docs_invoice on dfe_docs(invoice_id);
    create index if not exists ix_dfe_docs_status on dfe_docs(status);
    """)

    # Vendas V6 - base diária consolidada por origem/marca/loja.
    c.execute("""create table if not exists sales_daily(
        id integer primary key,
        sale_date text not null,
        source text not null,
        brand text default '',
        store text default '',
        gross_sales real default 0,
        net_store real default 0,
        tips real default 0,
        tickets integer default 0,
        avg_ticket real default 0,
        notes text default '',
        import_file text default '',
        created_at text,
        unique(sale_date,source,brand,store)
    )""")


    for stmt in [
        "alter table sales_daily add column fees_commissions real default 0",
        "alter table sales_daily add column services_promotions real default 0",
        "alter table sales_daily add column credits_inflows real default 0"
    ]:
        try:c.execute(stmt)
        except Exception:pass


    # Índices para acelerar NF, estoque, consultas e custos.
    c.executescript("""
    create index if not exists ix_invoice_items_invoice on invoice_items(invoice_id);
    create index if not exists ix_invoice_items_product on invoice_items(product_id);
    create index if not exists ix_invoices_issue_status on invoices(issue_date,status);
    create index if not exists ix_invoices_supplier on invoices(supplier_id);
    create index if not exists ix_movements_product_date on movements(product_id,movement_date);
    create index if not exists ix_movements_type_date on movements(type,movement_date);
    create index if not exists ix_inventory_product_date on inventory(product_id,inventory_date);
    create index if not exists ix_losses_product_date on losses(product_id,loss_date);
    create index if not exists ix_salesdaily_date_source on sales_daily(sale_date,source);
    create index if not exists ix_dfe_access on dfe_docs(access_key);
    create index if not exists ix_mappings_supplier_code on mappings(supplier_id,supplier_code);
    create index if not exists ix_barcodes_product on product_barcodes(product_id);
    """)
    c.execute("""create table if not exists opening_stock_batches(
        id integer primary key,
        batch_date text not null,
        name text not null,
        status text default 'ABERTO',
        notes text default '',
        created_at text,
        closed_at text
    )""")
    c.execute("""create table if not exists opening_stock_items(
        id integer primary key,
        batch_id integer not null,
        product_id integer not null,
        qty real default 0,
        unit_cost real default 0,
        notes text default '',
        unique(batch_id,product_id)
    )""")
    c.execute("create index if not exists ix_opening_items_batch on opening_stock_items(batch_id)")

    for stmt in [
        "alter table mappings add column commercial_unit text default ''",
        "alter table mappings add column stock_unit text default ''",
        "alter table invoice_items add column commercial_unit text default ''",
        "alter table invoice_items add column stock_unit text default ''"
    ]:
        try:c.execute(stmt)
        except Exception:pass

    c.executescript("""
    create index if not exists ix_invoice_status_date on invoices(status,issue_date);
    create index if not exists ix_invoice_access on invoices(access_key);
    create index if not exists ix_invoice_item_invprod on invoice_items(invoice_id,product_id);
    create index if not exists ix_cost_history_prod_date on cost_history(product_id,event_date);
    create index if not exists ix_cost_master_product on cost_master(product_id);
    create index if not exists ix_salesdaily_key on sales_daily(sale_date,source,brand,store);
    create index if not exists ix_mov_invoice_type on movements(invoice_id,type);
    create index if not exists ix_inventory_session_product on inventory(session_id,product_id);
    """)


    # V10.1 - relações e consultas centrais.
    c.executescript("""
    create index if not exists ix_product_active_name on products(active,name);
    create index if not exists ix_product_code on products(code);
    create index if not exists ix_invitem_product_invoice on invoice_items(product_id,invoice_id);
    create index if not exists ix_move_product_type_date on movements(product_id,type,movement_date);
    create index if not exists ix_costhist_product_date_id on cost_history(product_id,event_date,id);
    create index if not exists ix_mapping_product on mappings(product_id);

    drop view if exists v_stock_position;
    create view v_stock_position as
    select
        p.id product_id,
        p.code code,
        p.name name,
        coalesce(p.brand,'') brand,
        p.category category,
        p.subcategory subcategory,
        p.unit unit,
        coalesce(sum(m.qty),0) balance,
        coalesce(
          nullif(cm.current_cost,0),
          (select m2.unit_cost from movements m2
             where m2.product_id=p.id and m2.type='ENTRY' and m2.unit_cost>0
             order by m2.movement_date desc,m2.id desc limit 1),
          0
        ) current_cost
    from products p
    left join movements m on m.product_id=p.id
    left join cost_master cm on cm.product_id=p.id
    where p.active=1
    group by p.id,p.code,p.name,p.brand,p.category,p.subcategory,p.unit,cm.current_cost;

    drop view if exists v_confirmed_purchases;
    create view v_confirmed_purchases as
    select i.id invoice_id,i.number invoice_number,i.issue_date,i.supplier_id,
           ii.id invoice_item_id,ii.product_id,ii.description,
           ii.converted_qty,ii.converted_unit_cost,ii.xml_total
    from invoices i
    join invoice_items ii on ii.invoice_id=i.id
    where upper(i.status)='ENTRADA';

    drop view if exists v_invoice_item_relations;
    create view v_invoice_item_relations as
    select ii.id invoice_item_id,ii.invoice_id,ii.supplier_code,ii.description,
           ii.product_id,p.code product_code,p.name product_name,p.unit product_unit,
           ii.xml_qty,ii.xml_total,ii.converted_qty,ii.converted_unit_cost
    from invoice_items ii
    left join products p on p.id=ii.product_id;
    """)

    c.execute("insert into settings(key,value) values('decimal_places','3') on conflict(key) do nothing")

    # V11 - módulos aditivos; não apaga nem recria dados existentes.
    c.executescript("""
    create table if not exists loose_purchases(
        id integer primary key,
        purchase_date text not null,
        supplier_name text default '',
        document_ref text default '',
        category text default '',
        description text default '',
        total real default 0,
        notes text default '',
        active integer default 1,
        created_at text,
        updated_at text
    );
    create index if not exists ix_loose_purchases_date on loose_purchases(purchase_date,active);

    create table if not exists category_settings(
        category text primary key,
        include_inventory integer default 1,
        include_purchase_reports integer default 1,
        include_cmv integer default 1,
        include_production integer default 0,
        updated_at text
    );

    create table if not exists controlled_products(
        product_id integer primary key,
        active integer default 1,
        target_yield_pct real default 0,
        variance_tolerance_pct real default 3,
        notes text default '',
        updated_at text
    );

    create table if not exists production_recipes(
        id integer primary key,
        name text not null unique,
        unit text default 'UN',
        active integer default 1,
        notes text default ''
    );

    create table if not exists production_recipe_items(
        id integer primary key,
        recipe_id integer not null,
        product_id integer not null,
        qty_per_unit real default 0,
        unique(recipe_id,product_id)
    );
    create index if not exists ix_recipe_items_product on production_recipe_items(product_id);

    create table if not exists production_output(
        id integer primary key,
        work_date text not null,
        recipe_id integer not null,
        qty_produced real default 0,
        notes text default '',
        unique(work_date,recipe_id)
    );
    create index if not exists ix_production_output_date on production_output(work_date);

    create table if not exists sushi_control_daily(
        id integer primary key,
        work_date text not null,
        product_id integer not null,
        central_raw_opening real default 0,
        purchases_raw real default 0,
        trim_loss real default 0,
        clean_output real default 0,
        central_raw_closing_actual real default 0,
        central_clean_opening real default 0,
        central_transfer_store real default 0,
        central_clean_closing_actual real default 0,
        store_opening real default 0,
        store_receipts real default 0,
        store_closing_actual real default 0,
        recorded_waste real default 0,
        manual_theoretical_usage real default 0,
        avg_cost real default 0,
        notes text default '',
        updated_at text,
        unique(work_date,product_id)
    );
    create index if not exists ix_sushi_daily_date_product on sushi_control_daily(work_date,product_id);
    """)

    # Inicializa configuração das categorias existentes sem alterar escolhas futuras.
    c.execute("""insert or ignore into category_settings(category,updated_at)
                 select distinct coalesce(category,'SEM CATEGORIA'),? from products""",
              (datetime.now().isoformat(timespec='seconds'),))


    # V11.1 - evolução aditiva do controle de produção e padrões de corte.
    for stmt in [
        "alter table production_recipe_items add column cut_grams real default 0",
        "alter table production_recipe_items add column cuts_per_output real default 0",
        "alter table production_recipe_items add column error_margin_pct real default 5",
        "alter table sushi_control_daily add column raw_to_cut real default 0",
        "alter table sushi_control_daily add column central_raw_other_loss real default 0",
        "alter table sushi_control_daily add column central_clean_loss real default 0"
    ]:
        try:c.execute(stmt)
        except Exception:pass

    c.executescript("""
    create table if not exists production_usage_actual(
        id integer primary key,
        work_date text not null,
        recipe_id integer not null,
        product_id integer not null,
        actual_qty_used real default 0,
        notes text default '',
        updated_at text,
        unique(work_date,recipe_id,product_id)
    );
    create index if not exists ix_prod_usage_date_product
        on production_usage_actual(work_date,product_id);

    create table if not exists category_alias_audit(
        id integer primary key,
        event_date text,
        old_category text,
        new_category text,
        products_affected integer default 0,
        notes text default ''
    );
    """)


    # V11.2 - Controle de Produção Proteínas + Mix de Vendas + Fichas Técnicas.
    for stmt in [
        "alter table controlled_products add column protein_family text default ''",
        "alter table controlled_products add column theoretical_source text default 'PRODUCTION'",
        "alter table protein_sales_rows add column context_family text default ''",
        "alter table protein_menu_catalog add column contexts text default ''"
    ]:
        try:c.execute(stmt)
        except Exception:pass

    c.executescript("""
    create table if not exists protein_sales_imports(
        id integer primary key,
        filename text not null,
        file_hash text not null,
        period_start text,
        period_end text,
        imported_at text,
        active integer default 1,
        row_count integer default 0,
        total_value real default 0,
        notes text default '',
        unique(file_hash,period_start,period_end)
    );
    create index if not exists ix_protein_sales_imports_period
        on protein_sales_imports(period_start,period_end,active);

    create table if not exists protein_sales_rows(
        id integer primary key,
        import_id integer not null,
        source_line integer,
        channel text,
        plu text,
        plu_item text,
        item_code text,
        item_name text,
        unit_price real default 0,
        qty_sold real default 0,
        total_sold real default 0,
        family text default '',
        context_family text default '',
        protein_suggestions text default '',
        confidence text default '',
        group_key text default '',
        parent_name text default '',
        is_component integer default 0
    );
    create index if not exists ix_protein_sales_rows_import on protein_sales_rows(import_id);
    create index if not exists ix_protein_sales_rows_code on protein_sales_rows(item_code);
    create index if not exists ix_protein_sales_rows_family on protein_sales_rows(family);

    create table if not exists protein_menu_catalog(
        id integer primary key,
        item_code text not null unique,
        item_name text not null,
        family text default '',
        contexts text default '',
        auto_proteins text default '',
        auto_confidence text default '',
        active integer default 1,
        notes text default '',
        updated_at text
    );

    create table if not exists protein_technical_sheets(
        id integer primary key,
        menu_item_id integer not null,
        protein_product_id integer not null,
        portion_qty real default 0,
        portion_unit text default 'G',
        error_margin_pct real default 5,
        source text default 'MANUAL',
        confidence text default 'VALIDADO',
        active integer default 1,
        notes text default '',
        updated_at text,
        unique(menu_item_id,protein_product_id)
    );
    create index if not exists ix_protein_technical_menu on protein_technical_sheets(menu_item_id);
    create index if not exists ix_protein_technical_product on protein_technical_sheets(protein_product_id);

    create table if not exists protein_mapping_audit(
        id integer primary key,
        event_date text,
        module text,
        entity_key text,
        action text,
        before_json text,
        after_json text
    );
    """)


    # V11.5 - usuários, acessos e índices de performance.
    c.executescript("""
    create table if not exists app_users(
        id integer primary key,
        username text not null unique,
        full_name text not null,
        email text default '',
        role text not null default 'OPERADOR',
        password_hash text not null,
        password_salt text not null,
        active integer default 1,
        allowed_modules text default '[]',
        failed_attempts integer default 0,
        locked_until text default '',
        must_change_password integer default 0,
        created_at text,
        updated_at text,
        last_login text
    );
    create index if not exists ix_app_users_username on app_users(username);
    create index if not exists ix_products_active_category_name on products(active,category,name);
    create index if not exists ix_products_code on products(code);
    create index if not exists ix_products_name on products(name);
    create index if not exists ix_products_category on products(category);
    create index if not exists ix_invoice_items_supplier_code on invoice_items(supplier_code);
    create index if not exists ix_movements_invoice on movements(invoice_id);
    create index if not exists ix_cost_history_product_event on cost_history(product_id,event_date);
    create index if not exists ix_invoice_items_product_invoice on invoice_items(product_id,invoice_id);
    create index if not exists ix_invoices_status_issue on invoices(status,issue_date);
    create index if not exists ix_loose_purchases_category_date on loose_purchases(category,purchase_date,active);
    create index if not exists ix_category_settings_category on category_settings(category);
    """)
    try:c.execute("PRAGMA optimize")
    except Exception:pass

    c.commit(); c.close()
init()

STANDARD_TEMPLATES={
    'Produtos':['Código','Nome','Marca','Categoria','Subcategoria','Unidade Estoque','Barcode Fornecedor','Observações'],
    'Fornecedores':['CNPJ','Razão Social','Fantasia','IE','Endereço','Telefone','E-mail'],
    'Vendas':['Data','Origem','Marca','Venda Bruta/Base','Gorjeta','Líquido Loja','Clientes/Tickets','Observações'],
    'Estoque Inicial':['Código Produto','Nome Produto','Categoria','Unidade','Quantidade Inicial','Custo Unitário','Observações'],
    'Inventário':['Data Inventário','Código Produto','Nome Produto','Categoria','Unidade','Quantidade Contada','Custo Unitário','Observações'],
    'Custos Médios':['Código Produto','Produto','Custo Médio','Observações'],
    'Retiradas':['Data','Código Produto','Quantidade','Referência','Observações'],
    'Perdas':['Data','Código Produto','Quantidade','Causa','Observações'],
    'Cotações':['Data','Código Produto','CNPJ Fornecedor','Quantidade','Preço Oferta','Frete','Desconto','Prazo Dias','Validade','Observações'],
    'Contagem & Compras':['Data','Código Produto','Quantidade Contada','Estoque Alvo','Dia Compra','Grupo','Observações'],
}

def standard_template_bytes(module):
    cols=STANDARD_TEMPLATES.get(module,[])
    if not cols:return None
    sample=pd.DataFrame(columns=cols)
    return df_to_xlsx_bytes(sample,f'MODELO_{module.upper().replace(" ","_")}')

def standard_template_button(module,key='stdtpl'):
    b=standard_template_bytes(module)
    if b:
        st.download_button('📥 BAIXAR PLANILHA PADRÃO XLSX',b,
            f'MODELO_{module.upper().replace(" ","_").replace("&","E")}.xlsx',
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',key=f'{key}_{module}')

def import_standard_costs(file):
    x=pd.read_excel(file);n=0;errs=[]
    for ix,r in x.iterrows():
        try:
            code=int(r['Código Produto']);c=db();pr=c.execute("select id from products where code=?",(code,)).fetchone();c.close()
            if not pr:raise ValueError('produto não encontrado')
            cost=_money(r['Custo Médio'])
            set_master_cost(pr['id'],cost,str(r.get('Observações','')),'IMPORTAÇÃO XLSX','Planilha Custos Médios');n+=1
        except Exception as e:errs.append(f'Linha {ix+2}: {e}')
    return n,errs

def import_standard_withdrawals(file):
    x=pd.read_excel(file);c=db();n=0;errs=[]
    for ix,r in x.iterrows():
        try:
            code=int(r['Código Produto']);pr=c.execute("select id from products where code=?",(code,)).fetchone()
            if not pr:raise ValueError('produto não encontrado')
            d=_date_br(r['Data']);q=abs(_money(r['Quantidade']));cost=current_cost(pr['id'],d)
            c.execute("insert into movements(product_id,movement_date,type,qty,unit_cost,reference,notes) values(?,?,?,?,?,?,?)",
                      (pr['id'],str(d)+'T12:00:00','WITHDRAWAL',-q,cost,str(r.get('Referência','')),str(r.get('Observações',''))));n+=1
        except Exception as e:errs.append(f'Linha {ix+2}: {e}')
    c.commit();c.close();return n,errs

def import_standard_losses(file):
    x=pd.read_excel(file);c=db();n=0;errs=[]
    for ix,r in x.iterrows():
        try:
            code=int(r['Código Produto']);pr=c.execute("select id from products where code=?",(code,)).fetchone()
            if not pr:raise ValueError('produto não encontrado')
            d=_date_br(r['Data']);q=abs(_money(r['Quantidade']));cost=current_cost(pr['id'],d)
            cause=str(r.get('Causa','Planilha'));notes=str(r.get('Observações',''))
            c.execute("insert into losses(product_id,loss_date,qty,unit_cost,cause,notes) values(?,?,?,?,?,?)",(pr['id'],str(d),q,cost,cause,notes))
            c.execute("insert into movements(product_id,movement_date,type,qty,unit_cost,reference,notes) values(?,?,?,?,?,?,?)",(pr['id'],str(d)+'T12:00:00','LOSS',-q,cost,cause,notes));n+=1
        except Exception as e:errs.append(f'Linha {ix+2}: {e}')
    c.commit();c.close();return n,errs

def template(name):
    p=TEMPLATES/name
    if p.exists(): st.download_button('Baixar modelo padrão',p.read_bytes(),file_name=name,mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')


def _norm_header(value):
    s=str(value or '').strip().lower()
    s=''.join(ch for ch in unicodedata.normalize('NFKD',s) if not unicodedata.combining(ch))
    s=re.sub(r'[^a-z0-9]+',' ',s)
    return re.sub(r'\s+',' ',s).strip()

def _money(value):
    if value is None or (isinstance(value,float) and pd.isna(value)):
        return 0.0
    if isinstance(value,(int,float)):
        return float(value)
    s=str(value).strip()
    if not s or s.lower()=='nan':
        return 0.0
    s=re.sub(r'(?i)r\$\s*','',s)
    s=s.replace('\u00a0','').replace(' ','')
    s=re.sub(r'[^0-9,\.\-]','',s)
    if not s:
        return 0.0
    if ',' in s and '.' in s:
        # pt-BR: 12.345,67
        if s.rfind(',') > s.rfind('.'):
            s=s.replace('.','').replace(',','.')
        else:
            s=s.replace(',','')
    elif ',' in s:
        s=s.replace('.','').replace(',','.')
    elif s.count('.')>1:
        parts=s.split('.'); s=''.join(parts[:-1])+'.'+parts[-1]
    try:
        return float(s)
    except Exception:
        raise ValueError(f'Valor monetário inválido: {value}')

def _date_br(value):
    if value is None or (isinstance(value,float) and pd.isna(value)):
        raise ValueError('Data vazia')
    if isinstance(value,(datetime,date,pd.Timestamp)):
        return pd.to_datetime(value).date()
    if isinstance(value,(int,float)) and 20000 < float(value) < 80000:
        return (pd.Timestamp('1899-12-30') + pd.to_timedelta(float(value),unit='D')).date()
    s=str(value).strip()
    # primeiro pt-BR, depois fallback do pandas
    d=pd.to_datetime(s,dayfirst=True,errors='coerce')
    if pd.isna(d):
        raise ValueError(f'Data inválida: {value}')
    return d.date()

SALES_ALIASES={
    'Data':['data','data venda','dt venda','dia','date'],
    'Loja':['loja','unidade','filial','estabelecimento','store','codigo loja','nome loja'],
    'Venda Líquida':['venda liquida','vendas liquidas','valor venda liquida','faturamento liquido','receita liquida','liquido','venda liquida r'],
    'Venda Bruta':['venda bruta','vendas brutas','valor venda bruta','faturamento bruto','receita bruta','bruto','venda bruta r'],
    'Serviço':['servico','taxa servico','taxa de servico','servico cobrado','service'],
    'Delivery':['delivery','venda delivery','vendas delivery','ifood','entrega'],
    'Observações':['observacoes','observacao','obs','comentario','notas']
}

def normalize_sales_sheet(df):
    # remove linhas/colunas totalmente vazias
    df=df.dropna(how='all').dropna(axis=1,how='all').copy()
    normcols={col:_norm_header(col) for col in df.columns}
    chosen={}
    for target,aliases in SALES_ALIASES.items():
        alias_norm=[_norm_header(x) for x in aliases]
        # exact
        match=next((c for c,n in normcols.items() if n in alias_norm),None)
        # contains fallback
        if match is None:
            match=next((c for c,n in normcols.items() if any(a and (a in n or n in a) for a in alias_norm)),None)
        if match is not None:
            chosen[target]=match
    if 'Data' not in chosen:
        raise ValueError('Não encontrei a coluna de DATA. Use o modelo padrão ou uma coluna como Data / Data Venda / Dia.')
    if 'Venda Líquida' not in chosen and 'Venda Bruta' not in chosen:
        raise ValueError('Não encontrei Venda Líquida nem Venda Bruta.')
    out=pd.DataFrame()
    out['Data']=df[chosen['Data']].apply(_date_br)
    out['Loja']=df[chosen['Loja']].astype(str).str.strip() if 'Loja' in chosen else 'GERAL'
    if 'Venda Líquida' in chosen:
        out['Venda Líquida']=df[chosen['Venda Líquida']].apply(_money)
    else:
        out['Venda Líquida']=df[chosen['Venda Bruta']].apply(_money)
    if 'Venda Bruta' in chosen:
        out['Venda Bruta']=df[chosen['Venda Bruta']].apply(_money)
    else:
        out['Venda Bruta']=out['Venda Líquida']
    out['Serviço']=df[chosen['Serviço']].apply(_money) if 'Serviço' in chosen else 0.0
    out['Delivery']=df[chosen['Delivery']].apply(_money) if 'Delivery' in chosen else 0.0
    out['Observações']=df[chosen['Observações']].fillna('').astype(str) if 'Observações' in chosen else ''
    out['Loja']=out['Loja'].replace({'nan':'GERAL','':'GERAL'})
    # elimina linhas sem venda e com data inválida já tratada
    return out.reset_index(drop=True),chosen

@st.cache_data(ttl=15,show_spinner=False)
def _products_cached(search=''):
    c=db(); q='select p.id,p.code Código,p.internal_barcode BarcodeInterno,p.name Produto,p.brand Marca,p.category Categoria,p.subcategory Subcategoria,p.unit Unidade,group_concat(pb.barcode, \' , \') Barcodes,p.notes Observações from products p left join product_barcodes pb on pb.product_id=p.id where coalesce(p.active,1)=1'; args=[]
    if search.strip():
        s='%'+search.strip()+'%'; q+=' and (cast(p.code as text) like ? or p.name like ? or p.brand like ? or p.category like ? or p.subcategory like ? or p.internal_barcode like ? or pb.barcode like ?)'; args=[s]*7
    q+=' group by p.id order by p.category,p.subcategory,p.name'
    d=pd.read_sql_query(q,c,params=args);c.close();return d

def products(search=''):
    return _products_cached(search.strip()).copy()

def clear_data_cache():
    try:st.cache_data.clear()
    except Exception:pass

def product_grid_base():
    d=products('')
    if d.empty:
        return pd.DataFrame(columns=['id','Código','Produto','Categoria','Subcategoria','Unidade'])
    invcats=allowed_categories('include_inventory')
    if invcats:
        d=d[d['Categoria'].astype(str).isin(invcats)]
    cols=['id','Código','Produto','Categoria','Subcategoria','Unidade']
    return d[[c for c in cols if c in d.columns]].copy()

def editable_count_grid(base,existing=None,qty_col='Quantidade',cost_col='Custo Unitário',
                        key='count_grid',lock_cost=False,cost_ref=None):
    df=base.copy()
    emap={}
    if existing is not None and not existing.empty:
        for _,r in existing.iterrows():
            pid=int(r['product_id']) if 'product_id' in r else int(r['id'])
            emap[pid]=r.to_dict()
        df[qty_col]=[float(emap.get(int(pid),{}).get('qty',emap.get(int(pid),{}).get('counted_qty',0)) or 0)
                     for pid in df['id']]
        if lock_cost:
            df[cost_col]=[float(current_cost(int(pid),cost_ref) or 0) for pid in df['id']]
        else:
            df[cost_col]=[float(emap.get(int(pid),{}).get('unit_cost',
                              emap.get(int(pid),{}).get('avg_cost_3m',current_cost(int(pid),cost_ref))) or 0)
                          for pid in df['id']]
        df['Observações']=[str(emap.get(int(pid),{}).get('notes','') or '') for pid in df['id']]
    else:
        df[qty_col]=0.0
        df[cost_col]=[float(current_cost(int(pid),cost_ref) or 0) for pid in df['id']]
        df['Observações']=''

    disabled_cols=['id','Código','Produto','Categoria','Subcategoria','Unidade']
    if lock_cost:
        disabled_cols.append(cost_col)

    return st.data_editor(
        df,
        use_container_width=True,
        hide_index=True,
        height=520,
        key=key,
        disabled=disabled_cols,
        column_config={
            qty_col:st.column_config.NumberColumn(qty_col,min_value=0.0,step=0.001,format=num_format()),
            cost_col:st.column_config.NumberColumn(cost_col,min_value=0.0,step=0.01,format='R$ %.2f',
                help='Custo médio ponderado do trimestre quando bloqueado.'),
            'Observações':st.column_config.TextColumn('Observações')
        }
    )


@st.cache_data(ttl=12,show_spinner=False)
def search_products_sql(search='',limit=500,include_inactive=False):
    q=str(search or '').strip()
    c=db()
    sql="""select p.id,p.code Código,p.name Produto,coalesce(p.brand,'') Marca,
                  coalesce(p.category,'') Categoria,coalesce(p.subcategory,'') Subcategoria,
                  coalesce(p.unit,'') Unidade,coalesce(p.active,1) Ativo,
                  coalesce((select sum(m.qty) from movements m where m.product_id=p.id),0) Saldo,
                  coalesce(nullif(cm.current_cost,0),
                    (select m2.unit_cost from movements m2
                     where m2.product_id=p.id and m2.type='ENTRY' and m2.unit_cost>0
                     order by m2.movement_date desc,m2.id desc limit 1),0) Custo
           from products p
           left join cost_master cm on cm.product_id=p.id
           where 1=1"""
    args=[]
    if not include_inactive:
        sql+=" and coalesce(p.active,1)=1"
    if q:
        like='%'+q+'%'
        sql+=""" and (
            cast(p.code as text) like ? or p.name like ? or coalesce(p.brand,'') like ?
            or coalesce(p.category,'') like ? or coalesce(p.subcategory,'') like ?
            or coalesce(p.internal_barcode,'') like ?
            or exists(select 1 from product_barcodes pb where pb.product_id=p.id and pb.barcode like ?)
        )"""
        args=[like]*7
    sql+=" order by coalesce(p.active,1) desc,coalesce(p.category,''),p.name limit ?"
    args.append(int(limit))
    df=pd.read_sql_query(sql,c,params=args)
    c.close()
    if not df.empty:
        cmap=periodic_cost_map(str(date.today()))
        df['Custo']=[float(cmap.get(int(pid),cost) or 0) for pid,cost in zip(df['id'],df['Custo'])]
    return df

def all_products_df(search='',limit=10000):
    """Todos os produtos de todas as categorias, incluindo inativos."""
    return search_products_sql(search,limit,include_inactive=True)

def product_categories_all():
    c=db()
    rows=c.execute("""select distinct trim(coalesce(category,'')) category
                      from products where trim(coalesce(category,''))<>''
                      order by lower(trim(category))""").fetchall()
    c.close()
    return [str(r['category']) for r in rows]

@st.cache_data(ttl=15,show_spinner=False)
def product_invoice_cost_history(pid):
    """Histórico fiscal de custo unitário convertido por NF, mesmo se a NF estiver PENDENTE."""
    c=db()
    df=pd.read_sql_query("""select
        i.id 'Nota ID',
        i.number NF,
        i.issue_date 'Data NF',
        i.entry_date 'Data Importação',
        i.status 'Status NF',
        i.source Origem,
        s.legal_name Fornecedor,
        s.cnpj 'CNPJ Fornecedor',
        ii.id 'Item NF ID',
        ii.description 'Item NF',
        ii.supplier_code 'SKU Fornecedor',
        coalesce(nullif(ii.commercial_unit,''),ii.xml_unit,'') 'Un. Comercial',
        coalesce(nullif(ii.stock_unit,''),p.unit,'') 'Un. Estoque',
        ii.xml_qty 'Qtd Fiscal',
        ii.converted_qty 'Qtd Estoque',
        ii.xml_total 'Valor Item',
        ii.converted_unit_cost 'Custo Unitário',
        ii.multiplier 'Fator Mult.',
        ii.conversion 'Fator Conv.'
        from invoice_items ii
        join invoices i on i.id=ii.invoice_id
        left join suppliers s on s.id=i.supplier_id
        left join products p on p.id=ii.product_id
        where ii.product_id=?
        order by date(substr(i.issue_date,1,10)),i.id,ii.id""",c,params=[int(pid)])
    c.close()
    if df.empty:
        return pd.DataFrame(columns=[
            'Nota ID','NF','Data NF','Data Importação','Status NF','Origem','Fornecedor','CNPJ Fornecedor',
            'Item NF ID','Item NF','SKU Fornecedor','Un. Comercial','Un. Estoque','Qtd Fiscal','Qtd Estoque',
            'Valor Item','Custo Unitário','Fator Mult.','Fator Conv.','Custo Anterior','Mediana 5 Anteriores',
            'Variação Anterior %','Variação Mediana %','Direção','Alerta de Custo','Diagnóstico'
        ])

    for col in ['Custo Unitário','Qtd Fiscal','Qtd Estoque','Valor Item','Fator Mult.','Fator Conv.']:
        df[col]=pd.to_numeric(df[col],errors='coerce').fillna(0.0)

    cfg=settings_dict()
    try:warn=float(cfg.get('cost_alert_warning_pct','25') or 25)
    except Exception:warn=25.0
    try:critical=float(cfg.get('cost_alert_critical_pct','50') or 50)
    except Exception:critical=50.0
    warn=max(1.0,warn);critical=max(warn,critical)

    prev=[];prev_costs=[]
    med5=[];varprev=[];varmed=[];direction=[];alerts=[];diagnostics=[]
    for _,r in df.iterrows():
        cost=float(r['Custo Unitário'] or 0)
        prior=prev_costs[-1] if prev_costs else None
        recent=[x for x in prev_costs[-5:] if x>0]
        median=float(pd.Series(recent).median()) if recent else None
        vp=((cost/prior)-1)*100 if prior and prior>0 and cost>0 else None
        vm=((cost/median)-1)*100 if median and median>0 and cost>0 else None
        diffs=[abs(x) for x in [vp,vm] if x is not None]
        peak=max(diffs) if diffs else 0
        if cost<=0:
            alert='CRÍTICO'
            diag='Custo unitário zerado/negativo. Revisar quantidade, valor e conversão da NF.'
        elif peak>=critical:
            alert='CRÍTICO'
            diag='Variação extrema frente ao histórico. Possível erro de unidade, fator de conversão, quantidade ou preço na NF.'
        elif peak>=warn:
            alert='ATENÇÃO'
            diag='Variação relevante de custo. Confirmar preço e conversões da NF.'
        else:
            alert='OK'
            diag='Sem desvio relevante pelos limites configurados.'
        if vp is None:dirn='—'
        elif vp>0:dirn='↑ SUBIU'
        elif vp<0:dirn='↓ DESCEU'
        else:dirn='→ ESTÁVEL'
        prev.append(prior);med5.append(median);varprev.append(vp);varmed.append(vm)
        direction.append(dirn);alerts.append(alert);diagnostics.append(diag)
        if cost>0:prev_costs.append(cost)

    df['Custo Anterior']=prev
    df['Mediana 5 Anteriores']=med5
    df['Variação Anterior %']=varprev
    df['Variação Mediana %']=varmed
    df['Direção']=direction
    df['Alerta de Custo']=alerts
    df['Diagnóstico']=diagnostics
    return df

def product_noninvoice_cost_history(pid):
    c=db()
    df=pd.read_sql_query("""select event_date Data,cost Custo,source Fonte,
        coalesce(reference,'') Referência,coalesce(notes,'') Observações
        from cost_history
        where product_id=? and upper(coalesce(source,''))<>'NF-E'
        order by event_date,id""",c,params=[int(pid)])
    c.close()
    return df

def normalize_category_chain(value):
    """Normalização estrita de cadeia: ignora acentos, caixa, pontuação e espaços."""
    s=str(value or '').strip()
    s=''.join(ch for ch in unicodedata.normalize('NFKD',s) if not unicodedata.combining(ch))
    s=s.upper()
    s=re.sub(r'[^A-Z0-9]+','',s)
    return s

def duplicate_category_groups():
    c=db()
    vals=[str(r['category']) for r in c.execute("""
        select distinct category from products
        where trim(coalesce(category,''))<>'' order by category""").fetchall()]
    # Inclui categorias configuradas e compras avulsas que talvez não tenham produto atual.
    vals+= [str(r['category']) for r in c.execute("""
        select distinct category from category_settings
        where trim(coalesce(category,''))<>'' order by category""").fetchall()]
    vals+= [str(r['category']) for r in c.execute("""
        select distinct category from loose_purchases
        where trim(coalesce(category,''))<>'' order by category""").fetchall()]
    c.close()
    groups={}
    for v in vals:
        k=normalize_category_chain(v)
        if k:groups.setdefault(k,[])
        if k and v not in groups[k]:groups[k].append(v)
    return {k:sorted(v,key=lambda x:(len(x),x.lower())) for k,v in groups.items() if len(v)>1}

def merge_category_group(source_categories,canonical,notes='Unificação automática por cadeia equivalente'):
    canonical=str(canonical or '').strip()
    sources=[str(x or '').strip() for x in source_categories if str(x or '').strip()]
    sources=list(dict.fromkeys(sources))
    if not canonical:raise ValueError('Informe o nome canônico da categoria.')
    if not sources:raise ValueError('Nenhuma categoria selecionada.')
    c=db()
    try:
        c.execute('BEGIN IMMEDIATE')
        # Combina flags de todas as categorias envolvidas.
        allnames=list(dict.fromkeys(sources+[canonical]))
        marks=','.join('?' for _ in allnames)
        cfgs=c.execute(f"""select * from category_settings where category in ({marks})""",allnames).fetchall()
        flags=[1,1,1,0]
        if cfgs:
            flags=[
                max(int(r['include_inventory'] or 0) for r in cfgs),
                max(int(r['include_purchase_reports'] or 0) for r in cfgs),
                max(int(r['include_cmv'] or 0) for r in cfgs),
                max(int(r['include_production'] or 0) for r in cfgs)
            ]
        c.execute("""insert into category_settings(category,include_inventory,include_purchase_reports,
                     include_cmv,include_production,updated_at)
                     values(?,?,?,?,?,?)
                     on conflict(category) do update set
                     include_inventory=excluded.include_inventory,
                     include_purchase_reports=excluded.include_purchase_reports,
                     include_cmv=excluded.include_cmv,
                     include_production=excluded.include_production,
                     updated_at=excluded.updated_at""",
                  (canonical,*flags,datetime.now().isoformat(timespec='seconds')))

        total_products=0
        affected={}
        for old in sources:
            n=int(c.execute("select count(*) n from products where category=?",(old,)).fetchone()['n'] or 0)
            total_products+=n;affected[old]=n
            c.execute("update products set category=? where category=?",(canonical,old))
            c.execute("update loose_purchases set category=? where category=?",(canonical,old))
            if old!=canonical:
                c.execute("delete from category_settings where category=?",(old,))
            c.execute("""insert into category_alias_audit(event_date,old_category,new_category,products_affected,notes)
                         values(?,?,?,?,?)""",
                      (datetime.now().isoformat(timespec='seconds'),old,canonical,n,str(notes or '')))
        c.execute("""insert into correction_audit(event_date,module,record_id,action,before_json,after_json)
                     values(?,?,?,?,?,?)""",
                  (datetime.now().isoformat(timespec='seconds'),'CATEGORIA','|'.join(sources),
                   'UNIFICAR CADEIA EQUIVALENTE',
                   json.dumps({'categories':sources},ensure_ascii=False),
                   json.dumps({'canonical':canonical,'products':total_products,'by_source':affected},ensure_ascii=False)))
        c.commit();clear_data_cache()
        return {'products':total_products,'by_source':affected,'canonical':canonical}
    except Exception:
        c.rollback();raise
    finally:c.close()

def controlled_protein_info(pid):
    c=db()
    r=c.execute("""select cp.product_id,coalesce(cp.protein_family,'') protein_family,
        coalesce(cp.theoretical_source,'PRODUCTION') theoretical_source,
        coalesce(cp.target_yield_pct,0) target_yield_pct,
        coalesce(cp.variance_tolerance_pct,3) variance_tolerance_pct,
        coalesce(cp.notes,'') notes
        from controlled_products cp where cp.product_id=?""",(int(pid),)).fetchone()
    c.close()
    return dict(r) if r else None

def association_products(search='',limit=600):
    return search_products_sql(search,limit,include_inactive=True)



def association_candidates_for_item(item_id,limit=1200):
    c=db()
    item=c.execute("select supplier_code,barcode,description from invoice_items where id=?",(item_id,)).fetchone()
    df=pd.read_sql_query("""select p.id,p.code Código,p.name Produto,coalesce(p.brand,'') Marca,
        p.category Categoria,p.subcategory Subcategoria,p.unit Unidade,coalesce(p.active,1) Ativo,
        coalesce(v.balance,0) Saldo,coalesce(v.current_cost,0) Custo,p.internal_barcode
        from products p left join v_stock_position v on v.product_id=p.id
        order by coalesce(p.active,1) desc,p.name""",c)
    bars=pd.read_sql_query("select product_id,barcode from product_barcodes",c)
    c.close()
    if df.empty:return df

    desc=str(item['description'] or '').lower().strip() if item else ''
    barcode=str(item['barcode'] or '').strip() if item else ''
    supplier_code=str(item['supplier_code'] or '').strip() if item else ''

    bmap={}
    for _,r in bars.iterrows():
        bmap.setdefault(int(r['product_id']),set()).add(str(r['barcode'] or '').strip())

    scores=[];reasons=[]
    for _,r in df.iterrows():
        pid=int(r['id'])
        code=str(r['Código'] or '').strip()
        target=" ".join([
            str(r['Produto'] or '').lower(),
            str(r['Marca'] or '').lower(),
            str(r['Categoria'] or '').lower(),
            str(r['Subcategoria'] or '').lower()
        ])
        internal=str(r['internal_barcode'] or '').strip()
        allbars=bmap.get(pid,set()) | ({internal} if internal else set())
        score=0.0;reason=''
        if barcode and barcode in allbars:
            score=1000.0;reason='BARCODE'
        elif supplier_code and supplier_code==code:
            score=950.0;reason='CÓDIGO'
        else:
            ratio=difflib.SequenceMatcher(None,desc,target).ratio() if desc and target else 0
            dt=set(re.findall(r'\w+',desc))
            tt=set(re.findall(r'\w+',target))
            overlap=len(dt & tt)/max(1,len(dt)) if dt else 0
            score=ratio*100+overlap*150
            if overlap>=0.5:reason='NOME PARECIDO'
            elif ratio>=0.45:reason='POSSÍVEL'
        scores.append(score);reasons.append(reason)

    df['_score']=scores
    df['Sugestão']=reasons
    return df.sort_values(['_score','Ativo','Produto'],ascending=[False,False,True]).head(limit).reset_index(drop=True)

def stock_snapshot_df(search=''):
    q=str(search or '').strip()
    c=db()
    sql="""select p.id, p.code Código,p.name Produto,coalesce(p.brand,'') Marca,
                  coalesce(p.category,'') Categoria,coalesce(p.subcategory,'') Subcategoria,
                  coalesce(p.unit,'') Unidade,
                  coalesce((select sum(m.qty) from movements m where m.product_id=p.id),0) Saldo
           from products p where coalesce(p.active,1)=1"""
    args=[]
    if q:
        like='%'+q+'%'
        sql+=" and (cast(p.code as text) like ? or p.name like ? or coalesce(p.brand,'') like ? or coalesce(p.category,'') like ? or coalesce(p.subcategory,'') like ?)"
        args=[like]*5
    sql+=" order by coalesce(p.category,''),p.name"
    df=pd.read_sql_query(sql,c,params=args)
    c.close()
    if df.empty:
        return pd.DataFrame(columns=['Código','Produto','Marca','Categoria','Subcategoria','Unidade','Saldo','Custo Médio Vigente','Valor'])
    cmap=periodic_cost_map(str(date.today()))
    df['Custo Médio Vigente']=[float(cmap.get(int(pid),master_cost(int(pid))) or 0) for pid in df['id']]
    df['Valor']=pd.to_numeric(df['Saldo'],errors='coerce').fillna(0)*df['Custo Médio Vigente']
    return df.drop(columns=['id'])

def product_entity_summary(pid):
    c=db()
    row=c.execute("""select p.id,p.code,p.name,p.brand,p.category,p.subcategory,p.unit,
                            coalesce((select sum(m.qty) from movements m where m.product_id=p.id),0) balance
                     from products p where p.id=?""",(pid,)).fetchone()
    c.close()
    if not row:return None
    out=dict(row)
    out['current_cost']=current_cost(int(pid))
    return out

def pick_product(key,label='Produto',default=None):
    s=st.text_input('🔎 Código, nome, categoria, subcategoria ou barcode',key='search_'+key)
    d=search_products_sql(s,500)
    if d.empty:
        st.warning('Nenhum produto encontrado.')
        return None
    ids=d.id.tolist()
    ix=ids.index(default) if default in ids else 0
    return st.selectbox(
        label,ids,index=ix,key='pick_'+key,
        format_func=lambda x:f"{int(d.loc[d.id==x,'Código'].iloc[0])} | {d.loc[d.id==x,'Produto'].iloc[0]} | {d.loc[d.id==x,'Marca'].iloc[0]} | {d.loc[d.id==x,'Categoria'].iloc[0]} | Saldo {float(d.loc[d.id==x,'Saldo'].iloc[0]):.3f}"
    )

def balance(pid,at=None):
    c=db()
    if at:
        r=c.execute("select coalesce(sum(qty),0) q from movements where product_id=? and movement_date<=?",
                    (pid,str(at)+'T23:59:59')).fetchone()
    else:
        r=c.execute("select coalesce(balance,0) q from v_stock_position where product_id=?",(pid,)).fetchone()
    c.close()
    return float(r['q'] if r else 0)


def avg3m(pid,ref=None):
    """Compatibilidade legada: média ponderada móvel aproximada de 3 meses."""
    ref=ref or date.today()
    end=datetime.combine(ref,datetime.max.time())
    start=end-timedelta(days=92)
    c=db()
    r=c.execute("""select coalesce(sum(qty*unit_cost),0) v,coalesce(sum(qty),0) q
                   from movements
                   where product_id=? and type='ENTRY'
                     and movement_date between ? and ?
                     and qty>0 and unit_cost>0""",
                (pid,start.isoformat(),end.isoformat())).fetchone()
    if r['q'] and r['q']>0:
        out=float(r['v'])/float(r['q'])
    else:
        z=c.execute("""select unit_cost from movements
                       where product_id=? and type='ENTRY' and unit_cost>0 and movement_date<=?
                       order by movement_date desc,id desc limit 1""",
                    (pid,end.isoformat())).fetchone()
        out=float(z['unit_cost']) if z else 0
    c.close()
    return out

def quarter_bounds(ref=None):
    """Trimestres civis fixos: Jan-Mar, Abr-Jun, Jul-Set, Out-Dez."""
    d=pd.to_datetime(ref or date.today()).date()
    start_month=((d.month-1)//3)*3+1
    start=date(d.year,start_month,1)
    end_month=start_month+2
    last_day=calendar.monthrange(d.year,end_month)[1]
    end=date(d.year,end_month,last_day)
    return start,end

def periodic_quarter_cost(pid,ref=None,connection=None,carry_forward=True):
    """
    Média ponderada das ENTRADAS do trimestre civil vigente até a data de referência.
    Fórmula = Σ(qtd entrada × custo unitário) / Σ(qtd entrada).
    Ao virar o trimestre, inicia nova janela. Se ainda não houver entrada no novo
    trimestre, carrega o último custo trimestral válido como fallback.
    """
    refd=pd.to_datetime(ref or date.today()).date()
    qstart,qend=quarter_bounds(refd)
    enddt=datetime.combine(min(refd,qend),datetime.max.time()).isoformat()
    startdt=datetime.combine(qstart,datetime.min.time()).isoformat()

    own=connection is None
    c=connection or db()
    r=c.execute("""select coalesce(sum(qty*unit_cost),0) v,coalesce(sum(qty),0) q
                   from movements
                   where product_id=? and type='ENTRY'
                     and movement_date between ? and ?
                     and qty>0 and unit_cost>0""",
                (int(pid),startdt,enddt)).fetchone()
    qty=float(r['q'] or 0)
    if qty>0:
        out=float(r['v'] or 0)/qty
        if own:c.close()
        return out

    if carry_forward:
        # Procura o trimestre anterior mais recente que possua entradas.
        last=c.execute("""select movement_date
                          from movements
                          where product_id=? and type='ENTRY'
                            and qty>0 and unit_cost>0 and movement_date<?
                          order by movement_date desc,id desc limit 1""",
                       (int(pid),startdt)).fetchone()
        if last:
            lastd=pd.to_datetime(last['movement_date']).date()
            ps,pe=quarter_bounds(lastd)
            rr=c.execute("""select coalesce(sum(qty*unit_cost),0) v,coalesce(sum(qty),0) q
                            from movements
                            where product_id=? and type='ENTRY'
                              and movement_date between ? and ?
                              and qty>0 and unit_cost>0""",
                         (int(pid),
                          datetime.combine(ps,datetime.min.time()).isoformat(),
                          datetime.combine(pe,datetime.max.time()).isoformat())).fetchone()
            pq=float(rr['q'] or 0)
            if pq>0:
                out=float(rr['v'] or 0)/pq
                if own:c.close()
                return out
    if own:c.close()
    return 0.0

@st.cache_data(ttl=15,show_spinner=False)
def periodic_cost_map(ref=None):
    """Custo do trimestre mais recente com entradas para todos os produtos em uma única consulta."""
    refd=pd.to_datetime(ref or date.today()).date()
    c=db()
    df=pd.read_sql_query("""
        with qa as (
          select product_id,
                 cast(strftime('%Y',movement_date) as integer) yr,
                 cast((cast(strftime('%m',movement_date) as integer)-1)/3 as integer)+1 qtr,
                 sum(qty*unit_cost)/nullif(sum(qty),0) cost
          from movements
          where type='ENTRY' and qty>0 and unit_cost>0
            and date(substr(movement_date,1,10))<=date(?)
          group by product_id,yr,qtr
        ),
        ranked as (
          select product_id,cost,
                 row_number() over(partition by product_id order by yr desc,qtr desc) rn
          from qa
        )
        select product_id,cost from ranked where rn=1
    """,c,params=[str(refd)])
    c.close()
    return {int(r.product_id):float(r.cost or 0) for _,r in df.iterrows()}

def last_cost(pid,ref=None):
    ref=ref or date.today(); end=datetime.combine(ref,datetime.max.time()); c=db()
    z=c.execute("select unit_cost from movements where product_id=? and type='ENTRY' and unit_cost>0 and movement_date<=? order by movement_date desc limit 1",(pid,end.isoformat())).fetchone()
    out=float(z['unit_cost']) if z else 0; c.close(); return out


def master_cost(pid):
    c=db(); r=c.execute('select current_cost from cost_master where product_id=?',(pid,)).fetchone(); c.close()
    return float(r['current_cost']) if r and r['current_cost'] and float(r['current_cost'])>0 else 0.0

@st.cache_data(ttl=15,show_spinner=False)
def current_cost(pid,ref=None):
    # Regra principal V11.5.1: média ponderada do trimestre mais recente com entradas.
    refd=pd.to_datetime(ref or date.today()).date()
    q=float(periodic_cost_map(str(refd)).get(int(pid),0) or 0)
    if q>0:return q
    # Fallback apenas para produto sem entrada válida: custo inicial/manual.
    m=master_cost(pid)
    return m if m>0 else avg3m(pid,refd)

def recalc_master_cost_periodic(pid,ref=None,connection=None,note='Recalculado pela média ponderada trimestral'):
    own=connection is None
    c=connection or db()
    cost=periodic_quarter_cost(int(pid),ref,connection=c)
    if cost<=0:
        # fallback preserva custo manual/inicial apenas se não houver entrada válida.
        row=c.execute("select current_cost from cost_master where product_id=?",(int(pid),)).fetchone()
        cost=float(row['current_cost'] or 0) if row else 0.0
    c.execute("""insert into cost_master(product_id,current_cost,updated_at,notes)
                 values(?,?,?,?)
                 on conflict(product_id) do update set current_cost=excluded.current_cost,
                 updated_at=excluded.updated_at,notes=excluded.notes""",
              (int(pid),float(cost or 0),datetime.now().isoformat(timespec='seconds'),note))
    if own:
        c.commit();c.close()
    return float(cost or 0)

def set_master_cost(pid,value,notes='Ajuste manual',source='MANUAL',reference=''):
    value=float(value or 0)
    if value<=0: raise ValueError('Custo médio deve ser maior que zero.')
    now=datetime.now().isoformat(timespec='seconds')
    c=db(); c.execute("""insert into cost_master(product_id,current_cost,updated_at,notes) values(?,?,?,?)
    on conflict(product_id) do update set current_cost=excluded.current_cost,updated_at=excluded.updated_at,notes=excluded.notes""",
    (pid,value,now,notes)); c.commit(); c.close()
    record_cost_history(pid,value,source,reference,notes,now)

def daily_consumption_stats(pid,horizon=90):
    end=date.today(); start=end-timedelta(days=max(1,int(horizon))-1)
    c=db(); rows=c.execute("""select substr(movement_date,1,10) d,sum(case when qty<0 then -qty else 0 end) q
      from movements where product_id=? and type in ('WITHDRAWAL','LOSS') and substr(movement_date,1,10) between ? and ?
      group by substr(movement_date,1,10)""",(pid,str(start),str(end))).fetchall(); c.close()
    by={r['d']:float(r['q'] or 0) for r in rows}
    vals=[]
    for i in range((end-start).days+1): vals.append(by.get(str(start+timedelta(days=i)),0.0))
    if not vals:return 0.0,0.0
    avg=sum(vals)/len(vals)
    var=sum((x-avg)**2 for x in vals)/len(vals)
    return avg,math.sqrt(var)

def stock_metrics(pid,horizon=90,lead_days=None,review_days=None,service_factor=None):
    c=db(); pol=c.execute('select * from stock_policy where product_id=?',(pid,)).fetchone(); c.close()
    lead=float(lead_days if lead_days is not None else (pol['lead_days'] if pol else 7))
    review=float(review_days if review_days is not None else (pol['review_days'] if pol else 7))
    z=float(service_factor if service_factor is not None else (pol['service_factor'] if pol else 1.65))
    avg,std=daily_consumption_stats(pid,horizon)
    safety=max(0.0,z*std*math.sqrt(max(lead,1)))
    minimum=max(0.0,avg*lead+safety)
    standard=max(minimum,avg*(lead+review)+safety)
    maximum=max(standard,standard+avg*review)
    bal=balance(pid)
    days=(bal/avg) if avg>0 else None
    return {'avg_daily':avg,'std_daily':std,'lead_days':lead,'review_days':review,'safety':safety,'minimum':minimum,'standard':standard,'maximum':maximum,'days_stock':days}


def allowed_categories(flag='include_inventory'):
    if flag not in ('include_inventory','include_purchase_reports','include_cmv','include_production'):
        flag='include_inventory'
    c=db()
    rows=c.execute(f"select category from category_settings where coalesce({flag},1)=1 order by category").fetchall()
    c.close()
    return [str(r['category']) for r in rows]

def loose_purchases_value(a,b,categories=None):
    c=db()
    args=[str(a),str(b)]
    q="""select coalesce(sum(total),0) v from loose_purchases
         where active=1 and purchase_date between ? and ?"""
    if categories:
        q+=" and category in ("+','.join(['?']*len(categories))+")"
        args+=list(categories)
    r=c.execute(q,args).fetchone();c.close()
    return float(r['v'] or 0)

def sales_channel_summary(a,b):
    c=db()
    df=pd.read_sql_query("""select sale_date,source,
        case when upper(source)='3S' then gross_sales else net_store end considered,
        tickets
        from sales_daily where sale_date between ? and ?""",c,params=[str(a),str(b)])
    c.close()
    if df.empty:
        return {'balcao_sales':0,'balcao_clients':0,'balcao_ticket':0,
                'delivery_sales':0,'delivery_clients':0,'delivery_ticket':0,
                'total_sales':0,'total_clients':0,'total_ticket':0}
    isb=df['source'].astype(str).str.upper().eq('3S')
    bs=float(df.loc[isb,'considered'].sum());bc=int(df.loc[isb,'tickets'].sum())
    ds=float(df.loc[~isb,'considered'].sum());dc=int(df.loc[~isb,'tickets'].sum())
    ts=bs+ds;tc=bc+dc
    return {'balcao_sales':bs,'balcao_clients':bc,'balcao_ticket':bs/bc if bc else 0,
            'delivery_sales':ds,'delivery_clients':dc,'delivery_ticket':ds/dc if dc else 0,
            'total_sales':ts,'total_clients':tc,'total_ticket':ts/tc if tc else 0}

def _stock_qty_from_grams(grams,unit):
    g=float(grams or 0)
    u=str(unit or '').upper().strip()
    if u=='KG':return g/1000.0
    if u=='G':return g
    return g/1000.0

def production_theoretical_usage(work_date,product_id):
    c=db()
    rows=c.execute("""select po.qty_produced,pri.qty_per_unit,
                             coalesce(pri.cut_grams,0) cut_grams,
                             coalesce(pri.cuts_per_output,0) cuts_per_output,
                             p.unit
                      from production_output po
                      join production_recipe_items pri on pri.recipe_id=po.recipe_id
                      join products p on p.id=pri.product_id
                      where po.work_date=? and pri.product_id=?""",
                   (str(work_date),int(product_id))).fetchall()
    c.close()
    total=0.0
    for r in rows:
        if float(r['cut_grams'] or 0)>0 and float(r['cuts_per_output'] or 0)>0:
            per_output=_stock_qty_from_grams(
                float(r['cut_grams'])*float(r['cuts_per_output']),r['unit'])
        else:
            per_output=float(r['qty_per_unit'] or 0)
        total+=float(r['qty_produced'] or 0)*per_output
    return round_entry(total)

def production_cut_lines(work_date,product_id=None):
    c=db()
    args=[str(work_date)]
    where=""
    if product_id is not None:
        where=" and pri.product_id=?";args.append(int(product_id))
    df=pd.read_sql_query("""select po.work_date Data,po.recipe_id,pr.name Produção,
        pri.product_id,p.code Código,p.name Produto,p.unit Unidade,
        po.qty_produced 'Qtd Produzida',
        coalesce(pri.cut_grams,0) 'Gramatura Corte g',
        coalesce(pri.cuts_per_output,0) 'Unidades/Cortes',
        pri.qty_per_unit 'Qtd Padrão Direta',
        coalesce(pri.error_margin_pct,5) 'Margem %',
        coalesce(pua.actual_qty_used,0) 'Uso Real'
        from production_output po
        join production_recipes pr on pr.id=po.recipe_id
        join production_recipe_items pri on pri.recipe_id=po.recipe_id
        join products p on p.id=pri.product_id
        left join production_usage_actual pua
          on pua.work_date=po.work_date and pua.recipe_id=po.recipe_id and pua.product_id=pri.product_id
        where po.work_date=?"""+where+"""
        order by pr.name,p.name""",c,params=args)
    c.close()
    if df.empty:return df
    def expected(r):
        grams=float(r['Gramatura Corte g'] or 0)
        cuts=float(r['Unidades/Cortes'] or 0)
        if grams>0 and cuts>0:
            per=_stock_qty_from_grams(grams*cuts,r['Unidade'])
        else:
            per=float(r['Qtd Padrão Direta'] or 0)
        return round_entry(float(r['Qtd Produzida'] or 0)*per)
    df['Uso Teórico']=df.apply(expected,axis=1)
    df['Variação Corte']=df['Uso Real']-df['Uso Teórico']
    df['Cortes Totais']=df['Qtd Produzida']*df['Unidades/Cortes']
    df['Gramatura Real g']=df.apply(
        lambda r:(_grams_from_stock_qty(r['Uso Real'],r['Unidade'])/float(r['Cortes Totais']))
        if float(r['Uso Real'] or 0)>0 and float(r['Cortes Totais'] or 0)>0 else 0,axis=1)
    df['Erro %']=df.apply(
        lambda r:((float(r['Gramatura Real g'])-float(r['Gramatura Corte g']))/float(r['Gramatura Corte g'])*100)
        if float(r['Gramatura Corte g'] or 0)>0 and float(r['Gramatura Real g'] or 0)>0
        else ((float(r['Variação Corte'])/float(r['Uso Teórico'])*100)
              if float(r['Uso Teórico'] or 0)>0 and float(r['Uso Real'] or 0)>0 else 0),axis=1)
    df['Status Corte']=df.apply(
        lambda r:'SEM USO REAL' if float(r['Uso Real'] or 0)<=0
        else ('OK' if abs(float(r['Erro %']))<=float(r['Margem %'] or 0) else 'FORA DO PADRÃO'),
        axis=1)
    return df

def previous_sushi_closing(work_date,product_id):
    c=db()
    r=c.execute("""select central_raw_closing_actual,central_clean_closing_actual,store_closing_actual
                   from sushi_control_daily
                   where product_id=? and work_date<?
                   order by work_date desc limit 1""",(int(product_id),str(work_date))).fetchone()
    c.close()
    return dict(r) if r else {
        'central_raw_closing_actual':0,
        'central_clean_closing_actual':0,
        'store_closing_actual':0
    }

def prior_or_target_yield(work_date,product_id,target_yield=0):
    c=db()
    r=c.execute("""select raw_to_cut,clean_output from sushi_control_daily
                   where product_id=? and work_date<? and coalesce(raw_to_cut,0)>0
                   order by work_date desc limit 1""",(int(product_id),str(work_date))).fetchone()
    c.close()
    if r and float(r['raw_to_cut'] or 0)>0:
        return float(r['clean_output'] or 0)/float(r['raw_to_cut'] or 0)*100
    return float(target_yield or 0)

def sushi_control_metrics(row):
    raw_open=float(row.get('central_raw_opening',0) or 0)
    purchases=float(row.get('purchases_raw',0) or 0)
    raw_to_cut=float(row.get('raw_to_cut',0) or 0)
    raw_other_loss=float(row.get('central_raw_other_loss',0) or 0)
    trim=float(row.get('trim_loss',0) or 0)
    clean=float(row.get('clean_output',0) or 0)
    raw_close=float(row.get('central_raw_closing_actual',0) or 0)

    clean_open=float(row.get('central_clean_opening',0) or 0)
    transfer=float(row.get('central_transfer_store',0) or 0)
    clean_loss=float(row.get('central_clean_loss',0) or 0)
    clean_close=float(row.get('central_clean_closing_actual',0) or 0)

    store_open=float(row.get('store_opening',0) or 0)
    receipts=float(row.get('store_receipts',0) or 0)
    store_close=float(row.get('store_closing_actual',0) or 0)
    waste=float(row.get('recorded_waste',0) or 0)

    manual=float(row.get('manual_theoretical_usage',0) or 0)
    recipe=float(row.get('recipe_theoretical_usage',0) or 0)
    raw_cost=float(row.get('avg_cost',0) or 0)

    # CENTRAL BRUTO: não inferimos mais "quanto foi cortado".
    raw_available=raw_open+purchases
    raw_theoretical_close=raw_available-raw_to_cut-raw_other_loss
    raw_stock_variance=raw_close-raw_theoretical_close

    # Balanço do corte: entrada no corte deve virar produto limpo + perda registrada.
    cut_mass_variance=raw_to_cut-clean-trim
    yield_pct=(clean/raw_to_cut*100) if raw_to_cut>0 else 0

    # Custo efetivo do produto limpo considera o rendimento do dia;
    # se não houve corte, usa rendimento anterior/alvo passado no cálculo.
    cost_yield=float(row.get('cost_yield_pct',0) or 0)
    effective_yield=yield_pct if yield_pct>0 else cost_yield
    clean_cost=(raw_cost/(effective_yield/100.0)) if effective_yield>0 else raw_cost

    # CENTRAL LIMPO.
    clean_theoretical_close=clean_open+clean-transfer-clean_loss
    clean_stock_variance=clean_close-clean_theoretical_close

    # LOJA.
    gross_depletion=store_open+receipts-store_close
    actual_consumption=gross_depletion-waste
    theoretical_usage=recipe+manual
    store_theoretical_close=store_open+receipts-theoretical_usage-waste
    store_stock_variance=store_close-store_theoretical_close
    unexplained_usage=actual_consumption-theoretical_usage
    variance_pct=(unexplained_usage/theoretical_usage*100) if theoretical_usage>0 else 0

    known_loss_qty=trim+raw_other_loss+clean_loss+waste
    known_loss_cost=(trim+raw_other_loss)*raw_cost+(clean_loss+waste)*clean_cost

    return {
        'raw_available':raw_available,
        'central_raw_theoretical':raw_theoretical_close,
        'central_raw_variance':raw_stock_variance,
        'cut_mass_variance':cut_mass_variance,
        'yield_pct':yield_pct,
        'clean_cost':clean_cost,
        'central_clean_theoretical':clean_theoretical_close,
        'central_clean_variance':clean_stock_variance,
        'gross_depletion':gross_depletion,
        'actual_usage':actual_consumption,
        'theoretical_usage':theoretical_usage,
        'store_theoretical_close':store_theoretical_close,
        'store_stock_variance':store_stock_variance,
        'unexplained_variance':unexplained_usage,
        'variance_pct':variance_pct,
        'known_loss_qty':known_loss_qty,
        'known_loss_cost':known_loss_cost,
        'trim_loss_cost':trim*raw_cost,
        'store_waste_cost':waste*clean_cost,
        'unexplained_cost':unexplained_usage*clean_cost,
        'actual_usage_cost':actual_consumption*clean_cost,
        'theoretical_usage_cost':theoretical_usage*clean_cost
    }

def rename_merge_category(old_category,new_category,notes=''):
    old=str(old_category or '').strip()
    new=str(new_category or '').strip()
    if not old or not new:raise ValueError('Informe categoria atual e nova categoria.')
    if old==new:return 0
    c=db()
    try:
        c.execute('BEGIN IMMEDIATE')
        n=int(c.execute("select count(*) n from products where category=?",(old,)).fetchone()['n'] or 0)
        oldcfg=c.execute("select * from category_settings where category=?",(old,)).fetchone()
        newcfg=c.execute("select * from category_settings where category=?",(new,)).fetchone()
        if oldcfg:
            vals=[
                max(int(oldcfg['include_inventory'] or 0),int(newcfg['include_inventory'] or 0) if newcfg else 0),
                max(int(oldcfg['include_purchase_reports'] or 0),int(newcfg['include_purchase_reports'] or 0) if newcfg else 0),
                max(int(oldcfg['include_cmv'] or 0),int(newcfg['include_cmv'] or 0) if newcfg else 0),
                max(int(oldcfg['include_production'] or 0),int(newcfg['include_production'] or 0) if newcfg else 0)
            ]
        else:
            vals=[1,1,1,0]
        c.execute("""insert into category_settings(category,include_inventory,include_purchase_reports,
                     include_cmv,include_production,updated_at)
                     values(?,?,?,?,?,?)
                     on conflict(category) do update set
                     include_inventory=excluded.include_inventory,
                     include_purchase_reports=excluded.include_purchase_reports,
                     include_cmv=excluded.include_cmv,
                     include_production=excluded.include_production,
                     updated_at=excluded.updated_at""",
                  (new,*vals,datetime.now().isoformat(timespec='seconds')))
        c.execute("update products set category=? where category=?",(new,old))
        c.execute("update loose_purchases set category=? where category=?",(new,old))
        c.execute("delete from category_settings where category=?",(old,))
        c.execute("""insert into category_alias_audit(event_date,old_category,new_category,products_affected,notes)
                     values(?,?,?,?,?)""",
                  (datetime.now().isoformat(timespec='seconds'),old,new,n,str(notes or '')))
        c.execute("""insert into correction_audit(event_date,module,record_id,action,before_json,after_json)
                     values(?,?,?,?,?,?)""",
                  (datetime.now().isoformat(timespec='seconds'),'CATEGORIA',old,'RENOMEAR/MESCLAR',
                   json.dumps({'category':old},ensure_ascii=False),
                   json.dumps({'category':new,'products':n},ensure_ascii=False)))
        c.commit();clear_data_cache();return n
    except Exception:
        c.rollback();raise
    finally:c.close()


def _grams_from_stock_qty(qty,unit):
    q=float(qty or 0);u=str(unit or '').upper().strip()
    if u=='KG':return q*1000.0
    if u=='G':return q
    return q*1000.0

def product_entries_qty(work_date,product_id):
    c=db()
    r=c.execute("""select coalesce(sum(qty),0) q from movements
                   where product_id=? and type='ENTRY'
                     and date(substr(movement_date,1,10))=date(?)""",
                (int(product_id),str(work_date))).fetchone()
    c.close()
    return round_entry(float(r['q'] or 0))

def save_mapping_default(mapping_id,supplier_id,supplier_code,barcode,description,product_id,
                         multiplier,conversion,commercial_unit,stock_unit,apply_pending=True):
    c=db()
    try:
        c.execute('BEGIN IMMEDIATE')
        mult=round_entry(multiplier or 1);conv=round_entry(conversion or 1)
        if mult<=0 or conv<=0:raise ValueError('Multiplicação e conversão devem ser maiores que zero.')
        if mapping_id:
            c.execute("""update mappings set supplier_id=?,supplier_code=?,supplier_barcode=?,
                         supplier_description=?,product_id=?,multiplier=?,conversion=?,
                         commercial_unit=?,stock_unit=? where id=?""",
                      (int(supplier_id),str(supplier_code or '').strip(),str(barcode or '').strip(),
                       str(description or '').strip(),int(product_id),mult,conv,
                       str(commercial_unit or '').strip(),str(stock_unit or '').strip(),int(mapping_id)))
        else:
            c.execute("""insert into mappings(supplier_id,supplier_code,supplier_barcode,
                         supplier_description,product_id,multiplier,conversion,commercial_unit,stock_unit)
                         values(?,?,?,?,?,?,?,?,?)
                         on conflict(supplier_id,supplier_code) do update set
                         supplier_barcode=excluded.supplier_barcode,
                         supplier_description=excluded.supplier_description,
                         product_id=excluded.product_id,multiplier=excluded.multiplier,
                         conversion=excluded.conversion,commercial_unit=excluded.commercial_unit,
                         stock_unit=excluded.stock_unit""",
                      (int(supplier_id),str(supplier_code or '').strip(),str(barcode or '').strip(),
                       str(description or '').strip(),int(product_id),mult,conv,
                       str(commercial_unit or '').strip(),str(stock_unit or '').strip()))
        if barcode:
            c.execute("""insert or ignore into product_barcodes(product_id,barcode,description)
                         values(?,?,?)""",(int(product_id),str(barcode).strip(),'Associação / Conversão'))

        applied=0
        if apply_pending:
            rows=c.execute("""select ii.id,ii.xml_qty,ii.xml_total
                              from invoice_items ii join invoices i on i.id=ii.invoice_id
                              where i.supplier_id=? and ii.supplier_code=?
                                and upper(i.status)<>'ENTRADA'""",
                           (int(supplier_id),str(supplier_code or '').strip())).fetchall()
            for r in rows:
                cq=round_entry(float(r['xml_qty'] or 0)*mult*conv)
                uc=round_entry(float(r['xml_total'] or 0)/cq) if cq else 0
                c.execute("""update invoice_items set product_id=?,multiplier=?,conversion=?,
                             commercial_unit=?,stock_unit=?,converted_qty=?,converted_unit_cost=?
                             where id=?""",
                          (int(product_id),mult,conv,str(commercial_unit or '').strip(),
                           str(stock_unit or '').strip(),cq,uc,int(r['id'])))
                applied+=1
        now=datetime.now().isoformat(timespec='seconds')
        c.execute("""insert into correction_audit(event_date,module,record_id,action,before_json,after_json)
                     values(?,?,?,?,?,?)""",
                  (now,'ASSOCIAÇÃO/CONVERSÃO',str(mapping_id or f'{supplier_id}:{supplier_code}'),
                   'SALVAR DEFAULT','{}',
                   json.dumps({'supplier_id':supplier_id,'supplier_code':supplier_code,
                               'product_id':product_id,'multiplier':mult,'conversion':conv,
                               'commercial_unit':commercial_unit,'stock_unit':stock_unit,
                               'pending_applied':applied},ensure_ascii=False)))
        c.commit();clear_data_cache();return applied
    except Exception:
        c.rollback();raise
    finally:c.close()

def propagate_next_opening(work_date,product_id,raw_close,clean_close,store_close,connection=None):
    own=connection is None
    c=connection or db()
    nxt=c.execute("""select id,work_date from sushi_control_daily
                     where product_id=? and work_date>?
                     order by work_date asc limit 1""",(int(product_id),str(work_date))).fetchone()
    if nxt:
        c.execute("""update sushi_control_daily set
                     central_raw_opening=?,central_clean_opening=?,store_opening=?,updated_at=?
                     where id=?""",
                  (round_entry(raw_close),round_entry(clean_close),round_entry(store_close),
                   datetime.now().isoformat(timespec='seconds'),int(nxt['id'])))
    if own:
        c.commit();c.close()
    return int(nxt['id']) if nxt else None

def relink_after_deleted_closing(work_date,product_id,connection=None):
    own=connection is None
    c=connection or db()
    nxt=c.execute("""select id,work_date from sushi_control_daily
                     where product_id=? and work_date>?
                     order by work_date asc limit 1""",(int(product_id),str(work_date))).fetchone()
    if nxt:
        prev=c.execute("""select central_raw_closing_actual,central_clean_closing_actual,store_closing_actual
                          from sushi_control_daily
                          where product_id=? and work_date<?
                          order by work_date desc limit 1""",(int(product_id),str(nxt['work_date']))).fetchone()
        raw=float(prev['central_raw_closing_actual'] or 0) if prev else 0
        clean=float(prev['central_clean_closing_actual'] or 0) if prev else 0
        store=float(prev['store_closing_actual'] or 0) if prev else 0
        c.execute("""update sushi_control_daily set central_raw_opening=?,central_clean_opening=?,
                     store_opening=?,updated_at=? where id=?""",
                  (raw,clean,store,datetime.now().isoformat(timespec='seconds'),int(nxt['id'])))
    if own:
        c.commit();c.close()


# ==============================================================
# V11.2 - MIX DE VENDAS / PROTEÍNAS / FICHAS TÉCNICAS
# ==============================================================

def _norm_menu_text(value):
    import unicodedata,re
    s=str(value or '')
    s=''.join(ch for ch in unicodedata.normalize('NFKD',s) if not unicodedata.combining(ch))
    return re.sub(r'\s+',' ',s.upper()).strip()

def _clean_excel_code(value):
    if value is None or (isinstance(value,float) and pd.isna(value)):return ''
    if isinstance(value,float) and float(value).is_integer():return str(int(value))
    s=str(value).strip()
    if s.endswith('.0'):
        try:return str(int(float(s)))
        except Exception:pass
    return s

def protein_names_from_text(value):
    """Somente proteínas. Não inclui molhos, toppings, arroz, nori, cream cheese etc."""
    n=_norm_menu_text(value)
    out=[]
    def add(x):
        if x not in out:out.append(x)
    if 'LOMBO' in n and 'ATUM' in n:add('Lombo Atum')
    if any(k in n for k in ['SALMAO','SALMON','SALMOM','SALMA']):add('Salmão')
    if ('ATUM' in n or 'TUNA' in n) and 'Lombo Atum' not in out:add('Atum')
    if 'CAMARAO' in n or 'SHRIMP' in n or re.search(r'\bEBI\b',n):add('Camarão')
    if 'POLVO' in n:add('Polvo')
    if 'TILAPIA' in n:add('Tilápia')
    if 'HADDOCK' in n:add('Haddock')
    if 'PEIXE BR' in n or 'CEVICHE' in n:add('Peixe Branco / Ceviche')
    if 'LULA' in n:add('Lula')
    if 'KANI' in n:add('Kani')
    if 'FRANGO' in n or 'CHICKEN' in n or 'POLLO' in n:add('Frango')
    if re.search(r'\bPORK\b',n) or 'PORCO' in n:add('Pork')
    if 'FILE MIGNON' in n or 'FILÉ MIGNON' in str(value or '').upper() or re.search(r'\bCARNE\b',n):
        add('Carne / Filé Mignon')
    return out

def market_protein_inference(value):
    """
    Sugestões de mercado. Nunca são tratadas como ficha técnica validada.
    Retorna (proteínas, confiança, justificativa).
    """
    n=_norm_menu_text(value)
    explicit=protein_names_from_text(value)
    if explicit:
        return explicit,'CONFIRMADO NO NOME','Proteína identificada nominalmente no item.'
    if any(k in n for k in ['PHILADELPHIA','PHILADELFIA','FILADELPHIA','FILADELFIA']):
        return ['Salmão'],'INFERÊNCIA FORTE - VALIDAR','No sushi brasileiro, Philadelphia/Filadélfia costuma usar salmão + cream cheese; validar a ficha.'
    if 'CALIFORNIA' in n:
        return ['Kani'],'INFERÊNCIA MÉDIA - VALIDAR','California costuma utilizar kani; validar a ficha técnica desta operação.'
    return [],'REVISAR MANUALMENTE','O nome não permite determinar uma proteína com segurança.'

def menu_family_from_text(value):
    n=_norm_menu_text(value)
    if 'RODIZIO' in n or 'RDZ' in n:return 'Rodízio'
    if 'POKE' in n:return 'Poke Kauai'
    if any(k in n for k in ['SUSHI','SASHIM','TEMAK','URAMAK','HOSS','NIGIR','JOY','HAND ROLL',
                            'RLS -','ROLL','JAPA','JP RDZ','NIPPON','GUIOSA','HARUMAKI',
                            'MISSOSHIRO','YAKISOBA','BRISA','BATERA','HARU']):
        return 'Sushi / Japonês'
    if protein_names_from_text(value):return 'Peixaria / Proteínas'
    return 'Outros'

def parse_protein_sales_mix_xlsx(file_obj):
    """Lê o formato Mix de Produtos por canal de venda (FL/FC/TS/TT)."""
    raw=pd.read_excel(file_obj,sheet_name=0,header=None,dtype=object)
    rows=[]
    channel=''
    header=None
    for idx,series in raw.iterrows():
        vals=series.tolist()
        first=_clean_excel_code(vals[0]) if vals else ''
        if first in ('FL','FC','TS','TT') and all(pd.isna(x) for x in vals[1:]):
            channel=first;continue
        if first=='PLU':
            header=[str(x).strip() if not pd.isna(x) else '' for x in vals]
            continue
        if not channel or not header or all(pd.isna(x) for x in vals):continue
        plu=_clean_excel_code(vals[0])
        if not plu or plu=='PLU':continue
        rec={header[i]:vals[i] if i<len(vals) else None for i in range(len(header))}
        plu_item=_clean_excel_code(rec.get('PLU (Itens)')) or '-'
        name=str(rec.get('Nome do Item') or '').strip()
        if not name:continue
        try:unit_price=float(rec.get('Preço padrão R$') or 0)
        except Exception:unit_price=0.0
        try:qty=float(rec.get('Unidades vendidas') or 0)
        except Exception:qty=0.0
        try:total=float(rec.get('Total vendido R$') or 0)
        except Exception:total=0.0
        item_code=plu_item if plu_item not in ('','-') else plu
        suggestions,confidence,_reason=market_protein_inference(name)
        family=menu_family_from_text(name)
        rows.append({
            'source_line':int(idx)+1,'channel':channel,'plu':plu,'plu_item':plu_item,
            'item_code':item_code,'item_name':name,'unit_price':round_entry(unit_price),
            'qty_sold':round_entry(qty),'total_sold':round_entry(total),'family':family,
            'context_family':family,
            'protein_suggestions':' | '.join(suggestions),'confidence':confidence,
            'group_key':f'{channel}:{plu}','parent_name':'','is_component':0 if plu_item=='-' else 1
        })
    # Descobre um nome principal do grupo quando houver linha principal.
    mains={}
    for r in rows:
        if not r['is_component']:
            mains.setdefault(r['group_key'],[]).append(r['item_name'])
    for r in rows:
        names=mains.get(r['group_key'],[])
        r['parent_name']=' / '.join(dict.fromkeys(names)) if names else '(sem linha principal explícita)'
        group_family=menu_family_from_text(r['parent_name']) if names else 'Outros'
        r['context_family']=group_family if group_family!='Outros' else r['family']
    return pd.DataFrame(rows)

def import_protein_sales_mix(file_obj,filename,period_start=None,period_end=None,notes=''):
    data=file_obj.getvalue() if hasattr(file_obj,'getvalue') else file_obj.read()
    if hasattr(file_obj,'seek'):file_obj.seek(0)
    file_hash=hashlib.sha256(data).hexdigest()
    if hasattr(file_obj,'seek'):file_obj.seek(0)
    df=parse_protein_sales_mix_xlsx(file_obj)
    if df.empty:raise ValueError('Nenhuma linha reconhecida no arquivo.')
    c=db()
    try:
        c.execute('BEGIN IMMEDIATE')
        old=c.execute("""select id from protein_sales_imports
                         where file_hash=? and coalesce(period_start,'')=coalesce(?,'')
                           and coalesce(period_end,'')=coalesce(?,'')""",
                      (file_hash,str(period_start) if period_start else None,str(period_end) if period_end else None)).fetchone()
        if old:raise ValueError(f'Este arquivo/período já foi importado (ID {old["id"]}).')
        cur=c.execute("""insert into protein_sales_imports(
            filename,file_hash,period_start,period_end,imported_at,active,row_count,total_value,notes)
            values(?,?,?,?,?,1,?,?,?)""",
            (str(filename),file_hash,str(period_start) if period_start else None,
             str(period_end) if period_end else None,datetime.now().isoformat(timespec='seconds'),
             int(len(df)),round_entry(df['total_sold'].sum()),str(notes or '')))
        import_id=int(cur.lastrowid)
        for _,r in df.iterrows():
            c.execute("""insert into protein_sales_rows(
                import_id,source_line,channel,plu,plu_item,item_code,item_name,unit_price,qty_sold,total_sold,
                family,context_family,protein_suggestions,confidence,group_key,parent_name,is_component)
                values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (import_id,int(r['source_line']),r['channel'],r['plu'],r['plu_item'],r['item_code'],
                 r['item_name'],round_entry(r['unit_price']),round_entry(r['qty_sold']),round_entry(r['total_sold']),
                 r['family'],r['context_family'],r['protein_suggestions'],r['confidence'],r['group_key'],r['parent_name'],int(r['is_component'])))
            existing=c.execute("select id from protein_menu_catalog where item_code=?",(r['item_code'],)).fetchone()
            if existing:
                _old=c.execute("select contexts from protein_menu_catalog where item_code=?",(r['item_code'],)).fetchone()
                _ctx=set(x.strip() for x in str(_old['contexts'] or '').split('|') if x.strip()) if _old else set()
                _ctx.add(str(r['context_family'] or r['family']))
                c.execute("""update protein_menu_catalog set item_name=?,family=?,contexts=?,auto_proteins=?,
                             auto_confidence=?,updated_at=? where item_code=?""",
                          (r['item_name'],r['family'],' | '.join(sorted(_ctx)),r['protein_suggestions'],r['confidence'],
                           datetime.now().isoformat(timespec='seconds'),r['item_code']))
            else:
                c.execute("""insert into protein_menu_catalog(
                    item_code,item_name,family,contexts,auto_proteins,auto_confidence,active,updated_at)
                    values(?,?,?,?,?,?,1,?)""",
                    (r['item_code'],r['item_name'],r['family'],r['context_family'],r['protein_suggestions'],r['confidence'],
                     datetime.now().isoformat(timespec='seconds')))
        c.commit();clear_data_cache();return import_id,len(df),float(df['total_sold'].sum())
    except Exception:
        c.rollback();raise
    finally:c.close()

def protein_imports_df(active_only=False):
    c=db()
    where="where active=1" if active_only else ""
    df=pd.read_sql_query(f"""select id ID,filename Arquivo,period_start 'De',period_end 'Até',
        imported_at Importado,row_count Linhas,total_value 'Valor Linhas',active Ativo,notes Observações
        from protein_sales_imports {where} order by id desc""",c)
    c.close();return df

def protein_groups_df(import_id,only_relevant=True):
    c=db()
    q="""select group_key 'Grupo',channel Canal,plu PLU,
        max(parent_name) 'Nome Principal',
        count(*) Linhas,sum(is_component) Componentes,
        round(sum(qty_sold),3) 'Qtd Linhas',round(sum(total_sold),2) 'Valor Linhas',
        group_concat(distinct family) 'Famílias Item',
        group_concat(distinct context_family) 'Contextos',
        group_concat(distinct nullif(protein_suggestions,'')) 'Proteínas Sugeridas'
        from protein_sales_rows where import_id=?"""
    params=[int(import_id)]
    if only_relevant:
        q+=" and (family<>'Outros' or context_family<>'Outros' or protein_suggestions<>'')"
    q+=" group by group_key,channel,plu order by sum(total_sold) desc,sum(qty_sold) desc"
    df=pd.read_sql_query(q,c,params=params)
    c.close()
    if not df.empty:
        df['Status Proteína']=df['Proteínas Sugeridas'].fillna('').apply(
            lambda x:'ALINHAMENTO SUGERIDO' if str(x).strip() else 'ALINHAR MANUALMENTE')
    return df

def protein_catalog_df(search='',families=None,only_unmapped=False,limit=4000):
    c=db();args=[];where=["pmc.active=1"]
    if search:
        where.append("(pmc.item_name like ? or pmc.item_code like ?)")
        like=f'%{search}%';args.extend([like,like])
    if families:
        clauses=[]
        for fam in families:
            clauses.append("(pmc.family=? or pmc.contexts like ?)")
            args.extend([fam,f'%{fam}%'])
        where.append("("+ " or ".join(clauses) +")")
    if only_unmapped:
        where.append("not exists(select 1 from protein_technical_sheets pts where pts.menu_item_id=pmc.id and pts.active=1)")
    q=f"""select pmc.id ID,pmc.item_code Código,pmc.item_name Item,pmc.family Família,
        pmc.contexts Contextos,pmc.auto_proteins 'Proteína Sugerida',pmc.auto_confidence Confiança,
        (select count(*) from protein_technical_sheets pts where pts.menu_item_id=pmc.id and pts.active=1) 'Fichas Ativas'
        from protein_menu_catalog pmc where {' and '.join(where)}
        order by case when pmc.auto_proteins<>'' then 0 else 1 end,pmc.family,pmc.item_name limit ?"""
    args.append(int(limit));df=pd.read_sql_query(q,c,params=args);c.close();return df

def protein_product_options():
    p=search_products_sql('',5000,include_inactive=False)
    if p.empty:return [],{},{}
    labels=[];to_id={};to_label={}
    for _,r in p.iterrows():
        try:code=str(int(r['Código']))
        except Exception:code=str(r['Código'] or '')
        label=f"{code} | {r['Produto']} | {r['Unidade']}"
        labels.append(label);to_id[label]=int(r['id']);to_label[int(r['id'])]=label
    return labels,to_id,to_label

def save_protein_technical_sheet(menu_item_id,product_id,portion_qty,portion_unit,error_margin_pct=5,
                                 source='MANUAL',confidence='VALIDADO',notes=''):
    c=db()
    try:
        c.execute('BEGIN IMMEDIATE')
        before=c.execute("""select * from protein_technical_sheets
                            where menu_item_id=? and protein_product_id=?""",
                         (int(menu_item_id),int(product_id))).fetchone()
        c.execute("""insert into protein_technical_sheets(
            menu_item_id,protein_product_id,portion_qty,portion_unit,error_margin_pct,
            source,confidence,active,notes,updated_at)
            values(?,?,?,?,?,?,?,1,?,?)
            on conflict(menu_item_id,protein_product_id) do update set
            portion_qty=excluded.portion_qty,portion_unit=excluded.portion_unit,
            error_margin_pct=excluded.error_margin_pct,source=excluded.source,
            confidence=excluded.confidence,active=1,notes=excluded.notes,updated_at=excluded.updated_at""",
            (int(menu_item_id),int(product_id),round_entry(portion_qty),str(portion_unit).upper(),
             round_entry(error_margin_pct),str(source),str(confidence),str(notes or ''),
             datetime.now().isoformat(timespec='seconds')))
        after=c.execute("""select * from protein_technical_sheets
                           where menu_item_id=? and protein_product_id=?""",
                        (int(menu_item_id),int(product_id))).fetchone()
        c.execute("""insert into protein_mapping_audit(event_date,module,entity_key,action,before_json,after_json)
                     values(?,?,?,?,?,?)""",
                  (datetime.now().isoformat(timespec='seconds'),'FICHA TÉCNICA PROTEÍNA',
                   f'{menu_item_id}:{product_id}','SALVAR',
                   json.dumps(dict(before),ensure_ascii=False) if before else '{}',
                   json.dumps(dict(after),ensure_ascii=False) if after else '{}'))
        c.commit();clear_data_cache()
    except Exception:
        c.rollback();raise
    finally:c.close()

def technical_sheets_df(search=''):
    c=db();like=f'%{search}%'
    df=pd.read_sql_query("""select pts.id ID,pmc.item_code Código,pmc.item_name Item,pmc.family Família,
        p.id product_id,p.code 'Código SKU',p.name Proteína,p.unit 'Unidade Estoque',
        pts.portion_qty 'Porção',pts.portion_unit 'Unidade Porção',
        pts.error_margin_pct 'Margem %',pts.source Fonte,pts.confidence Confiança,pts.notes Observações
        from protein_technical_sheets pts
        join protein_menu_catalog pmc on pmc.id=pts.menu_item_id
        join products p on p.id=pts.protein_product_id
        where pts.active=1 and (?='' or pmc.item_name like ? or p.name like ? or pmc.item_code like ?)
        order by pmc.item_name,p.name""",c,params=[search,like,like,like])
    c.close();return df

def portion_to_stock_qty(portion_qty,portion_unit,stock_unit):
    q=float(portion_qty or 0);pu=str(portion_unit or '').upper();su=str(stock_unit or '').upper()
    if pu=='G' and su=='KG':return q/1000.0
    if pu=='KG' and su=='G':return q*1000.0
    return q

def protein_sales_cmv_df(import_id):
    c=db()
    sales=pd.read_sql_query("""select psr.id,psr.item_code,psr.item_name,psr.channel,psr.qty_sold,psr.total_sold,
        pmc.id menu_item_id
        from protein_sales_rows psr
        join protein_menu_catalog pmc on pmc.item_code=psr.item_code
        where psr.import_id=?""",c,params=[int(import_id)])
    sheets=pd.read_sql_query("""select pts.menu_item_id,pts.protein_product_id,p.code,p.name Proteína,p.unit,
        pts.portion_qty,pts.portion_unit
        from protein_technical_sheets pts join products p on p.id=pts.protein_product_id
        where pts.active=1""",c)
    imp=c.execute("select period_end from protein_sales_imports where id=?",(int(import_id),)).fetchone()
    c.close()
    if sales.empty or sheets.empty:return pd.DataFrame()
    _end=(imp['period_end'] if imp and imp['period_end'] else date.today().isoformat())
    try:end_date=date.fromisoformat(str(_end)[:10])
    except Exception:end_date=date.today()
    rows=[]
    grouped=sheets.groupby('menu_item_id')
    for _,sr in sales.iterrows():
        mid=int(sr['menu_item_id'])
        if mid not in grouped.groups:continue
        gs=grouped.get_group(mid)
        line_costs=[]
        for _,ts in gs.iterrows():
            stock_qty_per=portion_to_stock_qty(ts['portion_qty'],ts['portion_unit'],ts['unit'])
            theo_qty=float(sr['qty_sold'] or 0)*stock_qty_per
            cost=current_cost(int(ts['protein_product_id']),end_date)
            theo_cost=theo_qty*float(cost or 0)
            line_costs.append((ts,theo_qty,cost,theo_cost))
        total_protein_cost=sum(x[3] for x in line_costs)
        for ts,theo_qty,cost,theo_cost in line_costs:
            attributed=(float(sr['total_sold'] or 0)*(theo_cost/total_protein_cost)
                        if total_protein_cost>0 else 0)
            rows.append({
                'Canal':sr['channel'],'Item':sr['item_name'],'Proteína':ts['Proteína'],
                'Qtd Vendida':float(sr['qty_sold'] or 0),'Venda Item':float(sr['total_sold'] or 0),
                'Consumo Teórico':theo_qty,'Unidade Estoque':ts['unit'],'Custo Médio':float(cost or 0),
                'CMV Proteína':theo_cost,'Venda Atribuída Proteína':attributed,
                'CMV %':(theo_cost/attributed*100 if attributed else 0)
            })
    return pd.DataFrame(rows)

def protein_sales_cmv_summary(import_id):
    df=protein_sales_cmv_df(import_id)
    if df.empty:return df
    out=df.groupby(['Proteína','Unidade Estoque'],as_index=False).agg({
        'Qtd Vendida':'sum','Venda Item':'sum','Consumo Teórico':'sum',
        'CMV Proteína':'sum','Venda Atribuída Proteína':'sum'
    })
    out['CMV %']=out.apply(lambda r:r['CMV Proteína']/r['Venda Atribuída Proteína']*100
                          if r['Venda Atribuída Proteína'] else 0,axis=1)
    return out.sort_values('CMV Proteína',ascending=False)

def daily_sales_mix_theoretical_usage(work_date,product_id):
    """Só usa importações de UM DIA para não diluir um relatório agregado em fechamentos diários."""
    c=db()
    imports=c.execute("""select id from protein_sales_imports
                         where active=1 and period_start=? and period_end=?""",
                      (str(work_date),str(work_date))).fetchall()
    c.close()
    total=0.0
    for imp in imports:
        df=protein_sales_cmv_df(int(imp['id']))
        if df.empty:continue
        # precisa identificar a proteína pelo produto interno; cálculo detalhado acima agrega por nome.
        c=db()
        pname=c.execute("select name from products where id=?",(int(product_id),)).fetchone();c.close()
        if pname:
            total+=float(df.loc[df['Proteína']==pname['name'],'Consumo Teórico'].sum())
    return round_entry(total)

def inventory_value_at_category(d,categories=None):
    # V4.1: valoriza a última contagem de cada item pelo CUSTO VIGENTE.
    # Assim, ajustes na Central de Custos Médios repercutem no estoque e no CMV de inventário.
    c=db(); args=[str(d)]; cat_sql=''
    if categories:
        cat_sql=' and p.category in ('+','.join(['?']*len(categories))+')'; args += list(categories)
    q="""select i.product_id,i.counted_qty from inventory i
    join products p on p.id=i.product_id
    where i.id=(
        select i2.id from inventory i2
        where i2.product_id=i.product_id and i2.inventory_date<=?
          and (i2.session_id is null or coalesce(i2.row_status,'FECHADO')='FECHADO')
        order by i2.inventory_date desc,i2.id desc limit 1
    )
    and (i.session_id is null or coalesce(i.row_status,'FECHADO')='FECHADO')"""+cat_sql
    rows=c.execute(q,args).fetchall(); c.close()
    total=0.0
    for r in rows:
        total += float(r['counted_qty'] or 0) * current_cost(int(r['product_id']),d)
    return total

def purchases_value(a,b,categories=None):
    c=db();args=[str(a),str(b)];cat_sql=''
    if categories:
        cat_sql=' and p.category in ('+','.join(['?']*len(categories))+')';args+=list(categories)
    q="""select coalesce(sum(ii.xml_total),0) v
         from invoice_items ii join invoices i on i.id=ii.invoice_id
         join products p on p.id=ii.product_id
         where upper(i.status)='ENTRADA'
           and date(substr(i.issue_date,1,10)) between date(?) and date(?)"""+cat_sql
    nf=float(c.execute(q,args).fetchone()['v'] or 0);c.close()
    return nf+loose_purchases_value(a,b,categories)

def cogs_inventory(a,b,categories=None):
    # estoque inicial é a última contagem conhecida anterior ao início; estoque final é a última conhecida até o fim
    opening=inventory_value_at_category(a-timedelta(days=1),categories)
    closing=inventory_value_at_category(b,categories)
    purchases=purchases_value(a,b,categories)
    return opening,purchases,closing,opening+purchases-closing



def _excel_date(value):
    if value is None or (isinstance(value,float) and pd.isna(value)):return None
    if isinstance(value,(datetime,date,pd.Timestamp)):return pd.to_datetime(value).date()
    if isinstance(value,(int,float)) and not isinstance(value,bool):
        try:return (pd.Timestamp('1899-12-30')+pd.to_timedelta(float(value),unit='D')).date()
        except Exception:pass
    try:return pd.to_datetime(value,dayfirst=True,errors='raise').date()
    except Exception:return None

def _num(value):
    if value is None or (isinstance(value,float) and pd.isna(value)):return 0.0
    if isinstance(value,(int,float)) and not isinstance(value,bool):return float(value)
    s=str(value).strip()
    if not s or s.lower()=='nan':return 0.0
    s=re.sub(r'(?i)r\$\s*','',s).replace('\u00a0','').replace(' ','')
    s=re.sub(r'[^0-9,\.\-]','',s)
    if not s:return 0.0
    if ',' in s and '.' in s:
        if s.rfind(',')>s.rfind('.'):s=s.replace('.','').replace(',','.')
        else:s=s.replace(',','')
    elif ',' in s:s=s.replace('.','').replace(',','.')
    elif s.count('.')>1:
        p=s.split('.');s=''.join(p[:-1])+'.'+p[-1]
    try:return float(s)
    except:return 0.0

def _clean_brand_from_filename(name):
    stem=Path(str(name or '')).stem.strip()
    aliases={'Venda_3s':'3S','Geral_99':'99','Frango Frito':'Frango Frito',
             'ZChicken':'Z Chicken','Bowls':'Bowls','Mex':'Mex','Poke':'Poke'}
    return aliases.get(stem,stem)

def _upsert_sales_daily(rows,import_file='',overwrite=False):
    c=db();n=0;skipped=0
    for r in rows:
        if not r.get('sale_date'):continue
        tickets=max(0,int(round(float(r.get('tickets',0) or 0))))
        gross=float(r.get('gross_sales',0) or 0);net=float(r.get('net_store',0) or 0)
        considered=gross if str(r.get('source','')).upper()=='3S' else net
        avg=float(r.get('avg_ticket',0) or 0) or (considered/tickets if tickets else 0)
        vals=(str(r['sale_date']),str(r.get('source','')).upper(),str(r.get('brand','') or ''),
              str(r.get('store','') or ''),gross,net,float(r.get('tips',0) or 0),tickets,avg,
              str(r.get('notes','') or ''),str(import_file or ''),datetime.now().isoformat(timespec='seconds'),
              float(r.get('fees_commissions',0) or 0),float(r.get('services_promotions',0) or 0),float(r.get('credits_inflows',0) or 0))
        exists=c.execute("""select id from sales_daily where sale_date=? and source=? and brand=? and store=?""",
                         vals[:4]).fetchone()
        if exists and not overwrite:
            skipped+=1;continue
        if exists:
            c.execute("""update sales_daily set gross_sales=?,net_store=?,tips=?,tickets=?,avg_ticket=?,notes=?,
                import_file=?,created_at=?,fees_commissions=?,services_promotions=?,credits_inflows=? where id=?""",
                (vals[4],vals[5],vals[6],vals[7],vals[8],vals[9],vals[10],vals[11],vals[12],vals[13],vals[14],exists['id']))
        else:
            c.execute("""insert into sales_daily(sale_date,source,brand,store,gross_sales,net_store,tips,tickets,avg_ticket,
                notes,import_file,created_at,fees_commissions,services_promotions,credits_inflows)
                values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",vals)
        n+=1
    c.commit();c.close()
    st.session_state['_sales_import_skipped']=skipped
    return n

def parse_sales_3s(file):
    raw=pd.read_excel(file,header=None)
    hdr=None
    for i,row in raw.iterrows():
        vals=[_norm_header(v) for v in row.tolist()]
        if 'id loja' in vals and 'data' in vals and 'tickets' in vals:
            hdr=i;break
    if hdr is None:raise ValueError('Cabeçalho do relatório 3S não localizado.')
    df=pd.read_excel(file,header=hdr).dropna(how='all')
    rows=[]
    for _,r in df.iterrows():
        d=_excel_date(r.get('Data'))
        if not d:continue
        tickets=int(round(_num(r.get('Tickets'))))
        total_bruto=_num(r.get('Total Bruto'))
        tips=_num(r.get('Total Gorjeta'))
        # REGRA CORRETA: BALCÃO 3S = TOTAL BRUTO - GORJETA.
        sale_no_tip=total_bruto-tips
        store=str(r.get('Loja','') or '').strip()
        rows.append({'sale_date':d,'source':'3S','brand':'BALCÃO 3S','store':store,
                     'gross_sales':sale_no_tip,'net_store':sale_no_tip,'tips':tips,
                     'tickets':tickets,'avg_ticket':(sale_no_tip/tickets if tickets else 0),
                     'fees_commissions':0,'services_promotions':0,'credits_inflows':sale_no_tip,
                     'notes':'3S / Balcão: venda considerada = Total Bruto - Total Gorjeta.'})
    return rows,'3S'

def parse_sales_99(file):
    df=pd.read_excel(file)
    required={'Data','Nome do estabelecimento','Receita total de vendas','Receita total'}
    if not required.issubset(set(df.columns)):
        raise ValueError('Formato Geral_99 não reconhecido.')
    rows=[]
    for _,r in df.iterrows():
        d=_excel_date(r.get('Data'))
        if not d:continue
        store=str(r.get('Nome do estabelecimento','') or '').strip()
        gross=_num(r.get('Receita total de vendas'))
        net=_num(r.get('Receita total'))
        tickets=int(round(_num(r.get('Total de vendas realizadas'))))
        # 99 tem sua própria apuração: Receita total é o líquido disponibilizado pela plataforma.
        rows.append({'sale_date':d,'source':'99','brand':store,'store':store,
                     'gross_sales':gross,'net_store':net,'tips':0,'tickets':tickets,
                     'avg_ticket':(net/tickets if tickets else 0),
                     'fees_commissions':net-gross,'services_promotions':0,
                     'credits_inflows':gross,
                     'notes':'99 / Delivery: venda considerada no consolidado = Receita total (líquido loja).'})
    return rows,'99'

def parse_sales_ifood(file,brand_hint=''):
    df=pd.read_excel(file)
    req={'valor','pedido_associado_ifood','data_criacao_pedido_associado',
         'valor_cesta_final','impacto_no_repasse','tipo_lancamento','descricao_lancamento'}
    if not req.issubset(set(df.columns)):
        raise ValueError('Formato de conciliação iFood não reconhecido.')
    brand=brand_hint or _clean_brand_from_filename(getattr(file,'name','iFood'))
    df=df.copy()
    df['_date']=pd.to_datetime(df['data_criacao_pedido_associado'],errors='coerce',utc=True).dt.tz_convert(None).dt.date
    df=df[df['_date'].notna()].copy()
    df['_valor']=df['valor'].apply(_num)
    df['_order']=df['pedido_associado_ifood'].astype(str)

    rows=[]
    for d,g in df.groupby('_date'):
        valid_orders=g[~g['_order'].isin(['','nan','None','32'])].copy()
        tickets=int(valid_orders['_order'].nunique())

        # Venda bruta delivery: valor da cesta UMA VEZ por pedido.
        gross=0.0
        if not valid_orders.empty:
            for oid,og in valid_orders.groupby('_order'):
                vals=[_num(v) for v in og['valor_cesta_final'].tolist() if _num(v)>0]
                gross += vals[0] if vals else 0.0

        # Quanto fica na loja: SOMENTE movimentos que efetivamente impactam o repasse.
        impact=g[g['impacto_no_repasse'].astype(str).str.upper().eq('SIM')].copy()
        net=float(impact['_valor'].sum())

        credits=0.0;fees=0.0;services=0.0
        for _,rr in impact.iterrows():
            v=float(rr['_valor'] or 0)
            tipo=_norm_header(rr.get('tipo_lancamento',''))
            desc=_norm_header(rr.get('descricao_lancamento',''))
            if 'entrada financeira' in desc:
                credits += v
            elif tipo in ('cobranca','retencao','reembolso'):
                fees += v
            else:
                # Subsídios do iFood, ressarcimentos, anúncios e demais ajustes que impactam repasse.
                services += v

        rows.append({'sale_date':d,'source':'IFOOD','brand':brand,'store':brand,
                     'gross_sales':gross,'net_store':net,'tips':0,'tickets':tickets,
                     'avg_ticket':(net/tickets if tickets else 0),
                     'fees_commissions':fees,'services_promotions':services,
                     'credits_inflows':credits,
                     'notes':'iFood / Delivery: consolidado usa líquido = soma de valor somente onde impacto_no_repasse = SIM.'})
    return rows,'IFOOD'

def detect_and_parse_sales(file):
    name=str(getattr(file,'name',''))
    pos=file.tell() if hasattr(file,'tell') else None
    try:raw=pd.read_excel(file,header=None,nrows=15)
    finally:
        try:file.seek(pos if pos is not None else 0)
        except Exception:pass
    vals=' '.join(_norm_header(v) for v in raw.fillna('').astype(str).values.flatten().tolist())
    if 'vendas diarias dia de negocio' in vals or ('total gorjeta' in vals and 'total bruto' in vals):
        return parse_sales_3s(file)
    if 'nome do estabelecimento' in vals and 'receita total de vendas' in vals:
        return parse_sales_99(file)
    return parse_sales_ifood(file,_clean_brand_from_filename(name))

def sales_period_df(a,b):
    c=db()
    df=pd.read_sql_query("""select id,sale_date Data,source Origem,brand Marca,store Loja,
        gross_sales 'Venda Bruta / Base',net_store 'Líquido Loja',tips Gorjeta,tickets Clientes,
        avg_ticket 'Ticket Médio',fees_commissions 'Taxas/Comissões',
        services_promotions 'Serviços/Promoções/Ajustes',credits_inflows 'Entradas/Créditos',
        notes Observações,import_file Arquivo
        from sales_daily where sale_date between ? and ?
        order by sale_date,source,brand""",c,params=[str(a),str(b)])
    c.close()
    if not df.empty:
        df['Data_dt']=pd.to_datetime(df['Data'])
        pt={0:'Segunda',1:'Terça',2:'Quarta',3:'Quinta',4:'Sexta',5:'Sábado',6:'Domingo'}
        df['Dia da Semana']=df['Data_dt'].dt.dayofweek.map(pt)
        # A métrica que vale para o acumulado:
        df['Venda Considerada']=df.apply(
            lambda r:float(r['Venda Bruta / Base'] or 0) if str(r['Origem']).upper()=='3S'
            else float(r['Líquido Loja'] or 0),axis=1)
    return df

def consolidated_sales_value(a,b):
    c=db()
    r=c.execute("""select coalesce(sum(case when upper(source)='3S' then gross_sales else net_store end),0) v
                   from sales_daily where sale_date between ? and ?""",(str(a),str(b))).fetchone()
    c.close();return float(r['v'] or 0)

def simple_sales_from_excel(file):
    raw=pd.read_excel(file)
    raw=raw.dropna(how='all').dropna(axis=1,how='all')
    if raw.empty: raise ValueError('Planilha vazia.')
    return raw


def df_to_xml_bytes(df, root_name='dados', row_name='item'):
    root=etree.Element(root_name)
    for _,row in df.iterrows():
        el=etree.SubElement(root,row_name)
        for col,val in row.items():
            child=etree.SubElement(el,re.sub(r'[^A-Za-z0-9_]+','_',str(col)).strip('_') or 'campo')
            child.text='' if pd.isna(val) else str(val)
    return etree.tostring(root,pretty_print=True,xml_declaration=True,encoding='UTF-8')

def df_to_pdf_bytes(df,title='Relatório',max_rows=500):
    out=io.BytesIO(); c=canvas.Canvas(out,pagesize=A4); pw,ph=A4
    c.setTitle(title); c.setFont('Helvetica-Bold',13); c.drawString(15*mm,ph-15*mm,title)
    y=ph-24*mm
    cols=list(df.columns); widths=[max(22*mm,min(55*mm,(pw-30*mm)/max(1,len(cols)))) for _ in cols]
    totalw=sum(widths)
    if totalw>pw-30*mm:
        scale=(pw-30*mm)/totalw; widths=[w*scale for w in widths]
    def header(y):
        x=15*mm;c.setFont('Helvetica-Bold',6.5)
        for col,w in zip(cols,widths):
            c.drawString(x,y,str(col)[:28]);x+=w
        c.line(15*mm,y-1.5*mm,pw-15*mm,y-1.5*mm)
        return y-5*mm
    y=header(y);c.setFont('Helvetica',6.2)
    for _,row in df.head(max_rows).iterrows():
        if y<15*mm:
            c.showPage(); y=ph-18*mm; y=header(y); c.setFont('Helvetica',6.2)
        x=15*mm
        for val,w in zip(row.tolist(),widths):
            txt='' if pd.isna(val) else str(val)
            c.drawString(x,y,txt[:35]);x+=w
        y-=4.2*mm
    c.save();out.seek(0);return out.getvalue()

def _is_money_col(name):
    n=_norm_header(name)
    keys=['valor','custo','preco','preço','venda','receita','liquido','líquido','bruto','faturamento',
          'repasse','gorjeta','frete','desconto','cmv','ticket medio','ticket médio','estoque r']
    return any(k in n for k in keys)

def _is_percent_col(name):
    n=_norm_header(name)
    return '%' in str(name) or 'percent' in n or 'participacao' in n or 'participação' in n or 'variacao' in n or 'variação' in n

def _coerce_excel_df(df):
    out=df.copy()
    for col in out.columns:
        # Converte strings BRL/percentuais em números reais somente em colunas financeiras.
        if _is_money_col(col):
            out[col]=out[col].apply(lambda v:_money(v) if isinstance(v,str) else v)
            out[col]=pd.to_numeric(out[col],errors='coerce').fillna(0.0)
        elif _is_percent_col(col):
            def pct(v):
                if isinstance(v,str):
                    s=v.strip().replace('%','').replace('.','').replace(',','.')
                    try:return float(s)/100.0
                    except:return None
                try:
                    x=float(v)
                    return x/100.0 if abs(x)>1.5 else x
                except:return None
            out[col]=out[col].apply(pct)
        elif 'data' in _norm_header(col):
            # Datas ficam como datetime quando possível.
            conv=pd.to_datetime(out[col],errors='coerce',dayfirst=True)
            if conv.notna().any():out[col]=conv
    return out

def df_to_xlsx_bytes(df,title='Relatório'):
    data=_coerce_excel_df(df)
    out=io.BytesIO()
    with pd.ExcelWriter(out,engine='xlsxwriter',datetime_format='dd/mm/yyyy',date_format='dd/mm/yyyy') as writer:
        data.to_excel(writer,index=False,sheet_name='Dados')
        wb=writer.book;ws=writer.sheets['Dados']
        fmt_header=wb.add_format({'bold':True,'font_color':'white','bg_color':'#1F2937','border':0,'align':'center','valign':'vcenter'})
        fmt_money=wb.add_format({'num_format':'R$ #,##0.00','align':'right'})
        fmt_num=wb.add_format({'num_format':'#,##0.00','align':'right'})
        fmt_int=wb.add_format({'num_format':'0','align':'right'})
        fmt_pct=wb.add_format({'num_format':'0.00%','align':'right'})
        fmt_date=wb.add_format({'num_format':'dd/mm/yyyy','align':'center'})
        fmt_text=wb.add_format({'valign':'top'})
        ws.freeze_panes(1,0)
        ws.set_row(0,28,fmt_header)
        for j,col in enumerate(data.columns):
            ws.write(0,j,str(col),fmt_header)
            series=data[col]
            width=min(42,max(11,len(str(col))+2, int(series.astype(str).str.len().quantile(.90))+2 if len(series) else 11))
            if _is_money_col(col):
                ws.set_column(j,j,max(width,14),fmt_money)
            elif _is_percent_col(col):
                ws.set_column(j,j,max(width,12),fmt_pct)
            elif pd.api.types.is_datetime64_any_dtype(series):
                ws.set_column(j,j,13,fmt_date)
            elif pd.api.types.is_integer_dtype(series):
                ws.set_column(j,j,max(width,10),fmt_int)
            elif pd.api.types.is_numeric_dtype(series):
                ws.set_column(j,j,max(width,12),fmt_num)
            else:
                ws.set_column(j,j,width,fmt_text)
        if len(data) and len(data.columns):
            ws.add_table(
                0,0,len(data),len(data.columns)-1,
                {
                    'name':'TabelaDados',
                    'style':'Table Style Medium 2',
                    'columns':[{'header':str(c)} for c in data.columns]
                }
            )
        # Aba de resumo básica e profissional
        rs=wb.add_worksheet('Resumo')
        rs.set_column('A:A',28);rs.set_column('B:B',20)
        titlefmt=wb.add_format({'bold':True,'font_size':16,'font_color':'#1F2937'})
        labfmt=wb.add_format({'bold':True,'bg_color':'#E5E7EB'})
        rs.write('A1',title,titlefmt);rs.write('A3','Registros',labfmt);rs.write_number('B3',len(data))
        rs.write('A4','Gerado em',labfmt);rs.write_datetime('B4',datetime.now(),wb.add_format({'num_format':'dd/mm/yyyy hh:mm'}))
    out.seek(0);return out.getvalue()

def export_buttons(df,base_name,key_prefix='exp'):
    if df is None or df.empty:
        return
    c1,c2,c3=st.columns(3)

    try:
        xlsx=df_to_xlsx_bytes(df,base_name)
        c1.download_button(
            '⬇️ XLSX FORMATADO',
            xlsx,
            f'{base_name}.xlsx',
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            key=key_prefix+'_xlsx'
        )
    except Exception as e:
        c1.warning(f'XLSX indisponível: {e}')

    pdf=None
    try:
        pdf=df_to_pdf_bytes(_coerce_excel_df(df),base_name)
        c2.download_button(
            '⬇️ PDF',
            pdf,
            f'{base_name}.pdf',
            'application/pdf',
            key=key_prefix+'_pdf'
        )
    except Exception as e:
        c2.warning(f'PDF indisponível: {e}')

    if c3.button('🖨️ IMPRIMIR',key=key_prefix+'_print'):
        if pdf is None:
            st.error('Não foi possível gerar o PDF para impressão.')
        else:
            try:
                direct_print_pdf(pdf,'Impressora padrão do Windows')
                confirm_success('Relatório enviado para a impressora padrão.')
            except Exception as e:
                st.error(f'Impressão direta indisponível: {e}. Use o PDF e imprima pelo visualizador.')

def label_pdf(rows,width_mm=60,height_mm=40,columns=3,gap_mm=2,margin_mm=5,copies=1,barcode_mode='Interno',logo_path=None):
    out=io.BytesIO(); canv=canvas.Canvas(out,pagesize=A4); page_w,page_h=A4
    w=float(width_mm)*mm; h=float(height_mm)*mm; gap=float(gap_mm)*mm; margin=float(margin_mm)*mm
    cols=max(1,int(columns)); rows_per_page=max(1,int((page_h-2*margin+gap)//(h+gap)))
    pos=0; expanded=[]
    for r in rows: expanded += [r]*max(1,int(copies))
    for r in expanded:
        col=pos%cols; rr=(pos//cols)%rows_per_page
        if pos>0 and pos%(cols*rows_per_page)==0: canv.showPage()
        x=margin+col*(w+gap); y=page_h-margin-h-rr*(h+gap); canv.rect(x,y,w,h)
        code=str(r.get('barcode') or r.get('internal_barcode') or r.get('code'))
        name=str(r.get('name',''))[:48]; origin=str(r.get('origin',''))[:45]; validity=str(r.get('validity',''))[:20]
        logo_w=0
        if logo_path and Path(logo_path).exists():
            try:
                canv.drawImage(ImageReader(str(logo_path)),x+2*mm,y+h-11*mm,width=9*mm,height=9*mm,preserveAspectRatio=True,mask='auto');logo_w=11*mm
            except Exception: logo_w=0
        canv.setFont('Helvetica-Bold',8);canv.drawString(x+2*mm+logo_w,y+h-5*mm,name)
        canv.setFont('Helvetica',6.2);canv.drawString(x+2*mm+logo_w,y+h-9*mm,f"Origem: {origin or '-'}")
        canv.drawString(x+2*mm,y+h-14*mm,f"Validade: {validity or '-'} | Cód. interno: {r.get('code')}")
        try:
            kind='EAN13' if code.isdigit() and len(code)==13 else 'Code128'
            drawing=createBarcodeDrawing(kind,value=code,barHeight=max(7*mm,h-24*mm),humanReadable=True)
            scale=min((w-4*mm)/drawing.width,(h-20*mm)/drawing.height)
            drawing.scale(scale,scale);renderPDF.draw(drawing,canv,x+2*mm,y+2*mm)
        except Exception:
            canv.setFont('Helvetica-Bold',9);canv.drawCentredString(x+w/2,y+5*mm,code)
        pos+=1
    canv.save();out.seek(0);return out.getvalue()

def label_print_html(rows,width_mm=60,height_mm=40,columns=3,copies=1,logo_data_uri=None):
    items=[]
    for r in rows:
        for _ in range(max(1,int(copies))):
            logo=('<img src="'+logo_data_uri+'" class="logo">') if logo_data_uri else ''
            code=str(r.get('barcode') or r.get('internal_barcode') or r.get('code'))
            item='<div class="label">'+logo+'<div class="name">'+str(r.get('name',''))+'</div><div>Origem: '+str(r.get('origin','-'))+'</div><div>Validade: '+str(r.get('validity','-'))+'</div><div>Cód.: '+str(r.get('code',''))+'</div><div class="barcode">'+code+'</div></div>'
            items.append(item)
    style='@page{margin:5mm}body{font-family:Arial;margin:0}.grid{display:grid;grid-template-columns:repeat(%s,%smm);gap:2mm}.label{width:%smm;height:%smm;border:1px solid #000;box-sizing:border-box;padding:2mm;font-size:8pt;overflow:hidden;position:relative}.name{font-weight:bold;font-size:9pt;margin-bottom:1mm}.barcode{font-family:monospace;font-size:10pt;font-weight:bold;margin-top:2mm;letter-spacing:1px}.logo{position:absolute;right:2mm;top:2mm;max-width:10mm;max-height:8mm}button{margin:10px;padding:8px 16px}@media print{button{display:none}}' % (int(columns),float(width_mm),float(width_mm),float(height_mm))
    return '<!doctype html><html><head><meta charset="utf-8"><style>'+style+'</style></head><body><button onclick="window.print()">ENVIAR PARA IMPRESSORA</button><div class="grid">'+''.join(items)+'</div></body></html>'

def product_picker_by_categories(key,categories=None,label='Produto',default=None):
    search=st.text_input('🔎 Código, nome, categoria, subcategoria ou barcode',key='catsearch_'+key)
    d=products(search)
    if categories:
        d=d[d['Categoria'].isin(categories)]
    if d.empty:
        st.warning('Nenhum produto encontrado para o filtro selecionado.'); return None
    ids=d.id.tolist(); ix=ids.index(default) if default in ids else 0
    return st.selectbox(label,ids,index=ix,key='catpick_'+key,format_func=lambda x:f"{int(d.loc[d.id==x,'Código'].iloc[0])} | {d.loc[d.id==x,'Produto'].iloc[0]} | {d.loc[d.id==x,'Categoria'].iloc[0]}")



def delete_invoice_item_safe(invoice_id,item_id):
    """
    Exclui UM item da NF em uma única transação.
    Se a NF já estava em ENTRADA, desfaz a entrada inteira antes da exclusão
    e deixa a NF PENDENTE/ABERTA para conferência e nova confirmação.
    """
    c=db()
    affected_products=set()
    try:
        c.execute('BEGIN IMMEDIATE')

        inv=c.execute("""select id,status,number,issue_date,access_key
                         from invoices where id=?""",(invoice_id,)).fetchone()
        if not inv:
            raise ValueError('Nota não encontrada.')

        item=c.execute("""select * from invoice_items
                          where id=? and invoice_id=?""",(item_id,invoice_id)).fetchone()
        if not item:
            raise ValueError('Item da nota não encontrado ou já excluído.')

        before=dict(item)

        # Se a nota já foi lançada, desfaz TODOS os movimentos desta NF primeiro.
        if str(inv['status']).upper()=='ENTRADA':
            rows=c.execute("""select distinct product_id from movements
                              where invoice_id=? and type='ENTRY'""",(invoice_id,)).fetchall()
            affected_products.update(int(r['product_id']) for r in rows if r['product_id'])

            deleted=c.execute("""delete from movements
                                 where invoice_id=? and type='ENTRY'""",(invoice_id,)).rowcount

            # Compatibilidade com movimentos de versões antigas, sem invoice_id.
            if not deleted:
                all_items=c.execute("select * from invoice_items where invoice_id=?",(invoice_id,)).fetchall()
                ref='NF '+str(inv['number'] or '')
                prefix=str(inv['issue_date'] or '')+'%'
                for it in all_items:
                    if not it['product_id']:
                        continue
                    affected_products.add(int(it['product_id']))
                    mov=c.execute("""select id from movements
                                     where type='ENTRY' and product_id=? and reference=?
                                       and movement_date like ?
                                       and abs(qty-?)<0.000001
                                       and abs(unit_cost-?)<0.000001
                                     order by id desc limit 1""",
                                  (it['product_id'],ref,prefix,
                                   float(it['converted_qty'] or 0),
                                   float(it['converted_unit_cost'] or 0))).fetchone()
                    if mov:
                        c.execute("delete from movements where id=?",(mov['id'],))

            # Remove históricos de custo gerados por ESTA NF.
            ref='NF '+str(inv['number'] or '')
            cost_rows=c.execute("""select distinct product_id from cost_history
                                   where source='NF-e' and reference=?""",(ref,)).fetchall()
            affected_products.update(int(r['product_id']) for r in cost_rows if r['product_id'])
            c.execute("""delete from cost_history
                         where source='NF-e' and reference=?""",(ref,))

        if item['product_id']:
            affected_products.add(int(item['product_id']))

        # Exclui somente o item selecionado.
        c.execute("""delete from invoice_items
                     where id=? and invoice_id=?""",(item_id,invoice_id))

        # A NF sempre fica aberta após qualquer exclusão de item.
        c.execute("""update invoices
                     set status='PENDENTE',edit_status='ABERTA'
                     where id=?""",(invoice_id,))

        if inv['access_key']:
            c.execute("""update dfe_docs set status='XML COMPLETO'
                         where access_key=?""",(inv['access_key'],))

        c.execute("""insert into invoice_audit(invoice_id,event_date,action,details)
                     values(?,?,?,?)""",
                  (invoice_id,datetime.now().isoformat(timespec='seconds'),
                   'EXCLUIR ITEM',
                   json.dumps({
                       'item_excluido':before,
                       'nota_reaberta':True,
                       'estoque_estornado':str(inv['status']).upper()=='ENTRADA'
                   },ensure_ascii=False,default=str)))

        # Recalcula custo vigente dos produtos afetados usando o último histórico restante.
        for pid in affected_products:
            last=c.execute("""select cost,event_date,reference
                              from cost_history
                              where product_id=?
                              order by event_date desc,id desc limit 1""",(pid,)).fetchone()
            if last:
                c.execute("""insert into cost_master(product_id,current_cost,updated_at,notes)
                             values(?,?,?,?)
                             on conflict(product_id) do update set
                             current_cost=excluded.current_cost,
                             updated_at=excluded.updated_at,
                             notes=excluded.notes""",
                          (pid,float(last['cost'] or 0),
                           datetime.now().isoformat(timespec='seconds'),
                           'Recalculado após exclusão de item da NF '+str(inv['number'])))
            else:
                c.execute("""update cost_master
                             set current_cost=0,updated_at=?,notes=?
                             where product_id=?""",
                          (datetime.now().isoformat(timespec='seconds'),
                           'Sem histórico após exclusão da NF '+str(inv['number']),pid))

        remaining=c.execute("""select count(*) n from invoice_items
                               where invoice_id=?""",(invoice_id,)).fetchone()['n']

        c.commit()
        return {
            'ok':True,
            'remaining':int(remaining),
            'reopened':str(inv['status']).upper()=='ENTRADA',
            'message':f'Item excluído. Restam {remaining} item(ns) na nota.'
        }
    except Exception:
        c.rollback()
        raise
    finally:
        c.close()


def delete_inventory_item_safe(session_id,product_id):
    c=db();s=c.execute("select status from inventory_sessions where id=?",(session_id,)).fetchone();c.close()
    if not s: raise ValueError('Inventário não encontrado.')
    if str(s['status']).upper()=='FECHADO':
        reopen_inventory_session(session_id)
    c=db();c.execute("delete from inventory where session_id=? and product_id=?",(session_id,product_id));c.commit();c.close()

def audit_invoice(iid,action,details=''):
    c=db()
    c.execute("insert into invoice_audit(invoice_id,event_date,action,details) values(?,?,?,?)",
              (iid,datetime.now().isoformat(timespec='seconds'),action,str(details)))
    c.commit();c.close()

def invoice_purchase_total(invoice_id):
    c=db();r=c.execute("select coalesce(sum(xml_total),0) v from invoice_items where invoice_id=?",(invoice_id,)).fetchone();c.close()
    return float(r['v'] or 0)

def validate_invoice_consistency(invoice_id):
    c=db()
    inv=c.execute("select * from invoices where id=?",(invoice_id,)).fetchone()
    if not inv:
        c.close();return {'ok':False,'errors':['Nota não encontrada.']}
    items=c.execute("select * from invoice_items where invoice_id=?",(invoice_id,)).fetchall()
    movs=c.execute("select * from movements where invoice_id=? and type='ENTRY'",(invoice_id,)).fetchall()
    c.close()
    errors=[]
    if not items:errors.append('Nota sem itens.')
    if any(not it['product_id'] for it in items):errors.append('Há item(ns) sem produto associado.')
    if any(float(it['converted_qty'] or 0)<=0 or float(it['converted_unit_cost'] or 0)<0 for it in items):
        errors.append('Há item(ns) com quantidade/custo convertido inválido.')
    if str(inv['status']).upper()=='ENTRADA' and len(movs)!=len(items):
        errors.append(f'NF em ENTRADA com {len(items)} itens e {len(movs)} movimentos.')
    return {'ok':not errors,'errors':errors,'items':len(items),'movements':len(movs),'status':inv['status']}

def repair_invoice_entry(invoice_id):
    c=db();inv=c.execute("select status from invoices where id=?",(invoice_id,)).fetchone();c.close()
    if not inv:raise ValueError('Nota não encontrada.')
    if str(inv['status']).upper()=='ENTRADA':reopen_invoice(invoice_id)
    return confirm_invoice_entry(invoice_id)

def confirm_invoice_entry(invoice_id):
    """NF -> relações -> estoque -> custo médio trimestral -> compras em UMA transação."""
    c=db()
    try:
        c.execute('BEGIN IMMEDIATE')
        inv=c.execute("""select id,number,issue_date,status,access_key,supplier_id,total
                         from invoices where id=?""",(invoice_id,)).fetchone()
        if not inv:
            raise ValueError('Nota não encontrada.')
        if str(inv['status']).upper()=='ENTRADA':
            return {'ok':False,'already':True,'message':'Nota já lançada no estoque.'}

        items=c.execute("""select ii.*,p.id valid_product,p.name product_name,p.unit product_unit
                           from invoice_items ii
                           left join products p on p.id=ii.product_id
                           where ii.invoice_id=? order by ii.id""",(invoice_id,)).fetchall()
        if not items:
            raise ValueError('A nota não possui itens.')

        missing=[it for it in items if not it['product_id'] or not it['valid_product']]
        if missing:
            names=', '.join(str(it['description'] or it['supplier_code']) for it in missing[:8])
            raise ValueError(f'Associe os produtos antes da entrada. Pendentes: {names}')

        invalid=[]
        for it in items:
            qty=float(it['converted_qty'] or 0)
            cost=float(it['converted_unit_cost'] or 0)
            total=float(it['xml_total'] or 0)
            if qty<=0 or cost<=0 or total<0:
                invalid.append(str(it['description'] or 'Item'))
        if invalid:
            raise ValueError('Quantidade/custo convertido inválido em: '+', '.join(invalid[:10]))

        c.execute("delete from movements where invoice_id=? and type='ENTRY'",(invoice_id,))
        ref='NF '+str(inv['number'] or '')
        c.execute("delete from cost_history where source='NF-e' and reference=?",(ref,))

        issue_date=str(inv['issue_date'] or date.today())[:10]
        movement_date=issue_date+'T12:00:00'
        now=datetime.now().isoformat(timespec='seconds')
        purchase_total=0.0
        affected=[]

        for it in items:
            pid=int(it['product_id'])
            qty=float(it['converted_qty'])
            incoming_cost=float(it['converted_unit_cost'])
            purchase_total += float(it['xml_total'] or 0)
            affected.append(pid)

            c.execute("""insert into movements(
                product_id,movement_date,type,qty,unit_cost,reference,notes,invoice_id)
                values(?,?,?,?,?,?,?,?)""",
                (pid,movement_date,'ENTRY',qty,incoming_cost,ref,
                 str(it['description'] or ''),invoice_id))

            stock_unit=str(it['stock_unit'] or '').strip()
            if stock_unit:
                c.execute("update products set unit=? where id=?",(stock_unit,pid))

        # Recalcula uma única vez por produto após inserir todas as linhas da NF.
        for pid in sorted(set(affected)):
            qstart,qend=quarter_bounds(issue_date)
            avg_cost=periodic_quarter_cost(pid,issue_date,connection=c,carry_forward=True)
            qrow=c.execute("""select coalesce(sum(qty),0) q,coalesce(sum(qty*unit_cost),0) v
                              from movements
                              where product_id=? and type='ENTRY'
                                and movement_date between ? and ?
                                and qty>0 and unit_cost>0""",
                           (pid,
                            datetime.combine(qstart,datetime.min.time()).isoformat(),
                            datetime.combine(min(pd.to_datetime(issue_date).date(),qend),datetime.max.time()).isoformat())).fetchone()
            qsum=float(qrow['q'] or 0)
            c.execute("""insert into cost_history(product_id,event_date,cost,source,reference,notes)
                         values(?,?,?,?,?,?)""",
                      (pid,movement_date,avg_cost,'NF-e',ref,
                       f"Média ponderada trimestral das entradas {qstart.strftime('%d/%m/%Y')} a "
                       f"{min(pd.to_datetime(issue_date).date(),qend).strftime('%d/%m/%Y')}; "
                       f"quantidade ponderada {qsum:.6f}; custo médio {avg_cost:.6f}"))
            c.execute("""insert into cost_master(product_id,current_cost,updated_at,notes)
                         values(?,?,?,?)
                         on conflict(product_id) do update set
                         current_cost=excluded.current_cost,updated_at=excluded.updated_at,notes=excluded.notes""",
                      (pid,avg_cost,now,
                       f'Média ponderada trimestral após {ref} | {qstart.strftime("%d/%m/%Y")} a {qend.strftime("%d/%m/%Y")}'))

        c.execute("update invoices set total=?,status='ENTRADA',edit_status='FECHADA' where id=?",
                  (purchase_total,invoice_id))
        if inv['access_key']:
            c.execute("update dfe_docs set status='ENTRADA' where access_key=?",(inv['access_key'],))

        c.execute("""insert into invoice_audit(invoice_id,event_date,action,details)
                     values(?,?,?,?)""",
            (invoice_id,now,'CONFIRMAR ENTRADA',
             json.dumps({'nota':inv['number'],'itens':len(items),'produtos':sorted(set(affected)),
                         'valor_compras':purchase_total,
                         'metodo_custo':'MÉDIA PONDERADA TRIMESTRAL DAS ENTRADAS'},ensure_ascii=False)))

        c.commit()
        clear_data_cache()
        return {'ok':True,'already':False,'items':len(items),'purchase_total':purchase_total,
                'message':f"Entrada gravada: {len(items)} item(ns), compras {brl(purchase_total)} e custo médio trimestral atualizado."}
    except Exception:
        c.rollback()
        raise
    finally:
        c.close()


def reverse_invoice_stock(iid):
    """Desfaz somente os movimentos de entrada desta nota."""
    c=db()
    inv=c.execute("select * from invoices where id=?",(iid,)).fetchone()
    if not inv:
        c.close();return 0
    # Novos movimentos têm invoice_id: reversão exata.
    rows=c.execute("select id from movements where invoice_id=? and type='ENTRY'",(iid,)).fetchall()
    ids=[r['id'] for r in rows]
    if ids:
        c.execute("delete from movements where invoice_id=? and type='ENTRY'",(iid,))
        c.commit();c.close();return len(ids)

    # Compatibilidade com entradas antigas: remove 1 movimento correspondente por item.
    items=c.execute("select * from invoice_items where invoice_id=?",(iid,)).fetchall()
    removed=0
    ref='NF '+str(inv['number'] or '')
    date_prefix=str(inv['issue_date'] or '')
    for it in items:
        m=c.execute("""select id from movements
                       where type='ENTRY' and product_id=? and reference=? and movement_date like ?
                       and abs(qty-?)<0.000001 and abs(unit_cost-?)<0.000001
                       order by id desc limit 1""",
                    (it['product_id'],ref,date_prefix+'%',float(it['converted_qty'] or 0),float(it['converted_unit_cost'] or 0))).fetchone()
        if m:
            c.execute("delete from movements where id=?",(m['id'],));removed+=1
    c.commit();c.close();return removed

def reopen_invoice(iid):
    c=db()
    inv=c.execute("select * from invoices where id=?",(iid,)).fetchone()
    if not inv:
        c.close();raise ValueError("Nota não encontrada.")
    ref='NF '+str(inv['number'] or '')
    affected=[r['product_id'] for r in c.execute(
        "select distinct product_id from invoice_items where invoice_id=? and product_id is not null",(iid,)
    ).fetchall()]
    c.close()

    if str(inv['status']).upper()=='ENTRADA':
        reverse_invoice_stock(iid)

    c=db()
    c.execute("delete from cost_history where source='NF-e' and reference=?",(ref,))
    for pid in affected:
        recalc_master_cost_periodic(
            int(pid),date.today(),connection=c,
            note='Recalculado pela média ponderada trimestral após reabertura da '+ref
        )
    c.execute("update invoices set status='PENDENTE',edit_status='ABERTA' where id=?",(iid,))
    if inv['access_key']:
        try:c.execute("update dfe_docs set status='XML COMPLETO' where access_key=?",(inv['access_key'],))
        except Exception:pass
    c.commit();c.close()
    audit_invoice(iid,'REABRIR','Entrada revertida, custo recalculado e nota liberada para alteração')

def close_invoice_edit(iid):
    c=db();c.execute("update invoices set edit_status='FECHADA' where id=?",(iid,));c.commit();c.close()
    audit_invoice(iid,'FECHAR EDIÇÃO','Nota bloqueada para alterações')

def delete_invoice_safe(iid):
    c=db();inv=c.execute("select * from invoices where id=?",(iid,)).fetchone();c.close()
    if not inv:return False
    ref='NF '+str(inv['number'] or '')
    c=db()
    affected=[r['product_id'] for r in c.execute(
        "select distinct product_id from invoice_items where invoice_id=? and product_id is not null",(iid,)
    ).fetchall()]
    c.close()
    reverse_invoice_stock(iid)
    c=db()
    c.execute("delete from cost_history where source='NF-e' and reference=?",(ref,))
    for pid in affected:
        recalc_master_cost_periodic(
            int(pid),date.today(),connection=c,
            note='Recalculado pela média ponderada trimestral após exclusão da '+ref
        )
    if inv['access_key']:
        try:c.execute("update dfe_docs set status='XML COMPLETO' where access_key=?",(inv['access_key'],))
        except Exception:pass
    c.execute("delete from invoice_items where invoice_id=?",(iid,))
    c.execute("delete from invoice_audit where invoice_id=?",(iid,))
    c.execute("delete from invoices where id=?",(iid,))
    c.commit();c.close()
    return True

def create_inventory_session(inv_date,name='',notes=''):
    c=db()
    sid=c.execute("""insert into inventory_sessions(inventory_date,name,status,created_at,notes)
                     values(?,?,?,?,?)""",
                  (str(inv_date),name or f"Inventário {inv_date}",'ABERTO',
                   datetime.now().isoformat(timespec='seconds'),notes)).lastrowid
    c.commit();c.close();return sid

def create_opening_batch(batch_date,name='',notes=''):
    c=db()
    bid=c.execute("""insert into opening_stock_batches(batch_date,name,status,notes,created_at)
                     values(?,?,'ABERTO',?,?)""",
                  (str(batch_date),name or f'Estoque Inicial {batch_date}',notes,datetime.now().isoformat(timespec='seconds'))).lastrowid
    c.commit();c.close();return bid

def get_opening_batch(bid):
    c=db();r=c.execute("select * from opening_stock_batches where id=?",(bid,)).fetchone();c.close();return r

def save_opening_item(bid,pid,qty,cost,notes=''):
    b=get_opening_batch(bid)
    if not b or str(b['status']).upper()!='ABERTO':raise ValueError('A contagem inicial precisa estar ABERTA.')
    if float(cost or 0)<=0:raise ValueError('Informe o custo unitário.')
    c=db()
    c.execute("""insert into opening_stock_items(batch_id,product_id,qty,unit_cost,notes)
                 values(?,?,?,?,?)
                 on conflict(batch_id,product_id) do update set qty=excluded.qty,unit_cost=excluded.unit_cost,notes=excluded.notes""",
              (bid,pid,float(qty or 0),float(cost),notes))
    c.commit();c.close()
    set_master_cost(pid,float(cost),f'Custo da contagem inicial #{bid}','ESTOQUE INICIAL',f'Estoque Inicial #{bid}')

def close_opening_batch(bid):
    b=get_opening_batch(bid)
    if not b:return
    if str(b['status']).upper()=='FECHADO':return
    c=db();rows=c.execute("select * from opening_stock_items where batch_id=?",(bid,)).fetchall();c.close()
    for r in rows:
        c=db()
        c.execute("""insert into movements(product_id,movement_date,type,qty,unit_cost,reference,notes)
                     values(?,?,?,?,?,?,?)""",
                  (r['product_id'],str(b['batch_date'])+'T00:00:00','OPENING',float(r['qty'] or 0),
                   float(r['unit_cost'] or 0),f'Estoque Inicial #{bid}',r['notes']))
        c.commit();c.close()
        record_cost_history(r['product_id'],r['unit_cost'],'ESTOQUE INICIAL',f'Estoque Inicial #{bid}',r['notes'],str(b['batch_date'])+'T00:00:00')
    c=db();c.execute("update opening_stock_batches set status='FECHADO',closed_at=? where id=?",(datetime.now().isoformat(timespec='seconds'),bid));c.commit();c.close()

def reopen_opening_batch(bid):
    c=db();c.execute("delete from movements where reference=? and type='OPENING'",(f'Estoque Inicial #{bid}',))
    c.execute("update opening_stock_batches set status='ABERTO',closed_at='' where id=?",(bid,));c.commit();c.close()

def delete_opening_batch(bid):
    reopen_opening_batch(bid)
    c=db();c.execute("delete from opening_stock_items where batch_id=?",(bid,));c.execute("delete from opening_stock_batches where id=?",(bid,));c.commit();c.close()

def get_inventory_session(sid):
    c=db();r=c.execute("select * from inventory_sessions where id=?",(sid,)).fetchone();c.close();return r

def save_inventory_count(sid,pid,qty,cost,notes=''):
    s=get_inventory_session(sid)
    if not s or str(s['status']).upper()!='ABERTO':
        raise ValueError("O inventário precisa estar ABERTO.")
    c=db()
    old=c.execute("select id from inventory where session_id=? and product_id=? order by id desc limit 1",(sid,pid)).fetchone()
    if old:
        c.execute("""update inventory set inventory_date=?,counted_qty=?,avg_cost_3m=?,total_value=?,notes=?,row_status='ABERTO'
                     where id=?""",(s['inventory_date'],qty,cost,qty*cost,notes,old['id']))
    else:
        c.execute("""insert into inventory(inventory_date,product_id,counted_qty,avg_cost_3m,total_value,notes,session_id,row_status)
                     values(?,?,?,?,?,?,?,'ABERTO')""",
                  (s['inventory_date'],pid,qty,cost,qty*cost,notes,sid))
    c.commit();c.close()

def reverse_inventory_session_adjustments(sid):
    c=db()
    n=c.execute("select count(*) n from movements where inventory_session_id=? and type='ADJUSTMENT'",(sid,)).fetchone()['n']
    c.execute("delete from movements where inventory_session_id=? and type='ADJUSTMENT'",(sid,))
    c.commit();c.close();return int(n or 0)

def close_inventory_session(sid):
    s=get_inventory_session(sid)
    if not s:raise ValueError("Inventário não encontrado.")
    if str(s['status']).upper()=='FECHADO':return
    c=db()
    try:
        c.execute('BEGIN IMMEDIATE')
        rows=c.execute("select * from inventory where session_id=? order by id",(sid,)).fetchall()
        for r in rows:
            pid=int(r['product_id'])
            balrow=c.execute("""select coalesce(sum(qty),0) q from movements
                                where product_id=? and movement_date<=?""",
                             (pid,str(s['inventory_date'])+'T23:59:59')).fetchone()
            bal=float(balrow['q'] or 0)
            diff=float(r['counted_qty'] or 0)-bal
            cost=float(r['avg_cost_3m'] or 0)
            if abs(diff)>1e-9:
                c.execute("""insert into movements(product_id,movement_date,type,qty,unit_cost,reference,inventory_session_id)
                             values(?,?,?,?,?,?,?)""",
                          (pid,str(s['inventory_date'])+'T23:00:00','ADJUSTMENT',diff,cost,f"Inventário #{sid}",sid))
            if cost>0:
                c.execute("""insert into cost_master(product_id,current_cost,updated_at,notes)
                             values(?,?,?,?)
                             on conflict(product_id) do update set current_cost=excluded.current_cost,
                             updated_at=excluded.updated_at,notes=excluded.notes""",
                          (pid,cost,datetime.now().isoformat(timespec='seconds'),f'Custo do Inventário #{sid}'))
                c.execute("""insert into cost_history(product_id,event_date,cost,source,reference,notes)
                             values(?,?,?,?,?,?)""",
                          (pid,str(s['inventory_date'])+'T23:00:00',cost,'INVENTÁRIO',f'Inventário #{sid}',
                           'Custo informado na contagem'))
        c.execute("update inventory_sessions set status='FECHADO',closed_at=? where id=?",
                  (datetime.now().isoformat(timespec='seconds'),sid))
        c.execute("update inventory set row_status='FECHADO' where session_id=?",(sid,))
        c.commit();clear_data_cache()
    except Exception:
        c.rollback();raise
    finally:
        c.close()


def reopen_inventory_session(sid):
    reverse_inventory_session_adjustments(sid)
    c=db()
    c.execute("update inventory_sessions set status='ABERTO',closed_at='' where id=?",(sid,))
    c.execute("update inventory set row_status='ABERTO' where session_id=?",(sid,))
    c.commit();c.close()

def delete_inventory_session(sid):
    reverse_inventory_session_adjustments(sid)
    c=db()
    c.execute("delete from inventory where session_id=?",(sid,))
    c.execute("delete from inventory_sessions where id=?",(sid,))
    c.commit();c.close()


def _norm_text(v):
    s=str(v or '').upper()
    s=''.join(ch for ch in unicodedata.normalize('NFKD',s) if not unicodedata.combining(ch))
    return re.sub(r'[^A-Z0-9]+',' ',s).strip()

def is_weighable_category(category):
    n=_norm_text(category)
    return any(tok in n for tok in WEIGHABLE_CATEGORY_TOKENS)

def supplier_barcode_for_product(pid):
    c=db()
    pr=c.execute("select internal_barcode from products where id=?",(pid,)).fetchone()
    if not pr:
        c.close();return ''
    # Prioriza código explicitamente vindo de fornecedor / GTIN externo.
    r=c.execute("""select barcode from product_barcodes
                   where product_id=? and barcode<>?
                   order by case
                     when upper(coalesce(description,'')) like '%FORNECEDOR%' then 0
                     when upper(coalesce(description,'')) like '%NF-E%' then 1
                     when upper(coalesce(description,'')) like '%GTIN%' then 2
                     else 3 end,id limit 1""",(pid,pr['internal_barcode'])).fetchone()
    c.close()
    return str(r['barcode']) if r else ''

def preferred_barcode_for_label(pid,manual_override=''):
    if manual_override and str(manual_override).strip():
        return str(manual_override).strip(),'MANUAL'
    c=db();pr=c.execute("select category,internal_barcode from products where id=?",(pid,)).fetchone();c.close()
    if not pr:return '',''
    if is_weighable_category(pr['category']):
        return str(pr['internal_barcode'] or ''),'INTERNO (PESÁVEL)'
    ext=supplier_barcode_for_product(pid)
    return ext,'FORNECEDOR'

def record_cost_history(pid,cost,source,reference='',notes='',event_date=None):
    try:cost=float(cost or 0)
    except Exception:return
    if cost<=0:return
    dt=event_date or datetime.now().isoformat(timespec='seconds')
    c=db()
    # Evita duplicação idêntica em reruns.
    ex=c.execute("""select id from cost_history where product_id=? and event_date=? and cost=? and source=? and reference=? limit 1""",
                 (pid,str(dt),cost,str(source),str(reference))).fetchone()
    if not ex:
        c.execute("""insert into cost_history(product_id,event_date,cost,source,reference,notes)
                     values(?,?,?,?,?,?)""",(pid,str(dt),cost,str(source),str(reference),str(notes)))
        c.commit()
    c.close()

def cost_timeline(pid):
    c=db()
    df=pd.read_sql_query("""select event_date Data,cost Custo,source Fonte,
                                   coalesce(reference,'') Referência,coalesce(notes,'') Observações
                            from cost_history where product_id=?
                            order by event_date,id""",c,params=[pid])
    if df.empty:
        df=pd.read_sql_query("""select movement_date Data,unit_cost Custo,'ENTRADA' Fonte,
                                       coalesce(reference,'') Referência,coalesce(notes,'') Observações
                                from movements
                                where product_id=? and type='ENTRY' and unit_cost>0
                                order by movement_date,id""",c,params=[pid])
    c.close()
    if df.empty:
        return pd.DataFrame(columns=['Data','Custo','Fonte','Referência','Observações','Variação %'])
    df['Custo']=pd.to_numeric(df['Custo'],errors='coerce').fillna(0.0)
    df['Data_dt']=pd.to_datetime(df['Data'],errors='coerce')
    df=df.sort_values('Data_dt').reset_index(drop=True)
    df['Variação %']=df['Custo'].pct_change()*100
    df['Data']=df['Data_dt'].dt.strftime('%d/%m/%Y %H:%M').fillna(df['Data'].astype(str))
    return df.drop(columns=['Data_dt'])


def upsert_supplier_item(supplier_id,supplier_code,description,barcode='',unit='',pack_qty=1,
                         supplier_price=0,product_id=None,multiplier=1,conversion=1,source_file=''):
    code=str(supplier_code or '').strip() or str(barcode or '').strip() or _norm_text(description)[:80]
    c=db()
    c.execute("""insert into supplier_catalog_items(
        supplier_id,supplier_code,barcode,description,unit,pack_qty,supplier_price,product_id,
        multiplier,conversion,source_file,updated_at)
        values(?,?,?,?,?,?,?,?,?,?,?,?)
        on conflict(supplier_id,supplier_code) do update set
        barcode=excluded.barcode,description=excluded.description,unit=excluded.unit,
        pack_qty=excluded.pack_qty,supplier_price=excluded.supplier_price,
        product_id=coalesce(excluded.product_id,supplier_catalog_items.product_id),
        multiplier=excluded.multiplier,conversion=excluded.conversion,
        source_file=excluded.source_file,updated_at=excluded.updated_at""",
        (supplier_id,code,str(barcode or ''),str(description or ''),str(unit or ''),
         float(pack_qty or 1),float(supplier_price or 0),product_id,float(multiplier or 1),
         float(conversion or 1),str(source_file or ''),datetime.now().isoformat(timespec='seconds')))
    item=c.execute("select id from supplier_catalog_items where supplier_id=? and supplier_code=?",
                   (supplier_id,code)).fetchone()
    c.commit();c.close()
    if product_id:
        c=db()
        c.execute("""insert into mappings(supplier_id,supplier_code,supplier_barcode,supplier_description,product_id,multiplier,conversion)
                     values(?,?,?,?,?,?,?)
                     on conflict(supplier_id,supplier_code) do update set
                     supplier_barcode=excluded.supplier_barcode,supplier_description=excluded.supplier_description,
                     product_id=excluded.product_id,multiplier=excluded.multiplier,conversion=excluded.conversion""",
                  (supplier_id,code,str(barcode or ''),str(description or ''),product_id,float(multiplier or 1),float(conversion or 1)))
        if barcode:
            c.execute("insert or ignore into product_barcodes(product_id,barcode,description) values(?,?,?)",
                      (product_id,str(barcode),'Fornecedor'))
        c.commit();c.close()
    return int(item['id']) if item else None

def import_supplier_table(file,supplier_id):
    df=pd.read_excel(file)
    df=df.dropna(how='all').dropna(axis=1,how='all')
    if df.empty:raise ValueError('Tabela vazia.')
    cols=list(df.columns); norm={_norm_header(c):c for c in cols}
    def pick(names,default=None):
        for n in names:
            k=_norm_header(n)
            if k in norm:return norm[k]
        return default
    ccode=pick(['código','codigo','sku','código fornecedor','codigo fornecedor','ref','referência','referencia'],cols[0] if cols else None)
    cdesc=pick(['descrição','descricao','produto','item','nome'],cols[1] if len(cols)>1 else None)
    cbar=pick(['barcode','gtin','ean','ean13','código barras','codigo barras'],None)
    cunit=pick(['unidade','und','un'],None)
    cprice=pick(['preço','preco','valor','custo','preço unitário','preco unitario'],None)
    cpack=pick(['embalagem','qtd embalagem','pack','conteúdo','conteudo'],None)
    n=0;errs=[]
    for ix,r in df.iterrows():
        try:
            desc=str(r.get(cdesc,'') if cdesc else '').strip()
            if not desc or desc.lower()=='nan':continue
            code=str(r.get(ccode,'') if ccode else '').strip()
            if code.lower()=='nan':code=''
            bar=str(r.get(cbar,'') if cbar else '').strip()
            if bar.lower()=='nan':bar=''
            unit=str(r.get(cunit,'') if cunit else '').strip()
            if unit.lower()=='nan':unit=''
            price=_money(r.get(cprice,0)) if cprice else 0
            pack=_money(r.get(cpack,1)) if cpack else 1
            upsert_supplier_item(supplier_id,code,desc,bar,unit,pack or 1,price,source_file=getattr(file,'name',''))
            n+=1
        except Exception as e:errs.append(f'Linha {ix+2}: {e}')
    return n,errs

def business_context_for_ai():
    c=db()
    try:
        today=date.today(); start=today.replace(day=1)
        sales=float(c.execute("select coalesce(sum(net_sales),0) v from sales where sale_date between ? and ?",(str(start),str(today))).fetchone()['v'] or 0)
        purchases=float(c.execute("""select coalesce(sum(ii.xml_total),0) v from invoice_items ii join invoices i on i.id=ii.invoice_id
                                    where i.status='ENTRADA' and i.issue_date between ? and ?""",(str(start),str(today))).fetchone()['v'] or 0)
        losses=float(c.execute("select coalesce(sum(qty*unit_cost),0) v from losses where loss_date between ? and ?",(str(start),str(today))).fetchone()['v'] or 0)
        pending=int(c.execute("select count(*) n from invoices where status='PENDENTE'").fetchone()['n'] or 0)
        topcats=pd.read_sql_query("""select p.category Categoria,sum(ii.xml_total) Compras
            from invoice_items ii join invoices i on i.id=ii.invoice_id join products p on p.id=ii.product_id
            where i.status='ENTRADA' and i.issue_date between ? and ?
            group by p.category order by Compras desc limit 12""",c,params=[str(start),str(today)])
        low=pd.read_sql_query("""select p.code,p.name,p.category,
            coalesce((select sum(m.qty) from movements m where m.product_id=p.id),0) Saldo
            from products p where p.active=1 order by Saldo asc limit 20""",c)
    finally:c.close()
    return {
        'periodo':f'{start} a {today}','vendas':sales,'compras':purchases,'perdas':losses,
        'notas_pendentes':pending,'compras_por_categoria':topcats.to_dict('records'),
        'menores_saldos':low.to_dict('records')
    }

def ask_free_ai(question):
    key=''
    try:key=st.secrets.get('GEMINI_API_KEY','')
    except Exception:key=''
    key=key or os.environ.get('GEMINI_API_KEY','')
    if not key:
        raise ValueError('Configure GEMINI_API_KEY nos Secrets do Streamlit Community Cloud.')
    model='gemini-2.5-flash'
    ctx=business_context_for_ai()
    prompt=f"""Você é o Assistente Gerencial do HNT FoodService BI.
Responda em português de forma objetiva. Use os dados do sistema abaixo quando a pergunta envolver operação.
Se a pergunta for geral, responda normalmente. Não invente dados operacionais ausentes.
DADOS DO SISTEMA:
{json.dumps(ctx,ensure_ascii=False,default=str)}
PERGUNTA:
{question}"""
    url=f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}'
    payload={'contents':[{'parts':[{'text':prompt}]}]}
    r=requests.post(url,json=payload,timeout=45)
    if r.status_code>=400:
        raise RuntimeError(f'Gemini API {r.status_code}: {r.text[:500]}')
    data=r.json()
    parts=data.get('candidates',[{}])[0].get('content',{}).get('parts',[])
    ans=''.join(p.get('text','') for p in parts).strip()
    return ans or 'A IA não retornou conteúdo.'

def entity_integrity_report():
    c=db()
    queries=[
        ('Itens NF sem nota',"select count(*) n from invoice_items ii left join invoices i on i.id=ii.invoice_id where i.id is null"),
        ('Itens NF com produto inexistente',"select count(*) n from invoice_items ii left join products p on p.id=ii.product_id where ii.product_id is not null and p.id is null"),
        ('Movimentos com produto inexistente',"select count(*) n from movements m left join products p on p.id=m.product_id where p.id is null"),
        ('Movimentos NF sem nota',"select count(*) n from movements m left join invoices i on i.id=m.invoice_id where m.invoice_id is not null and i.id is null"),
        ('Custos com produto inexistente',"select count(*) n from cost_history ch left join products p on p.id=ch.product_id where p.id is null"),
        ('NF ENTRADA divergente',"select count(*) n from invoices i where upper(i.status)='ENTRADA' and (select count(*) from invoice_items ii where ii.invoice_id=i.id)!=(select count(*) from movements m where m.invoice_id=i.id and m.type='ENTRY')")
    ]
    rows=[]
    for name,q in queries:
        n=int(c.execute(q).fetchone()['n'] or 0)
        rows.append([name,n,'OK' if n==0 else 'REVISAR'])
    c.close()
    return pd.DataFrame(rows,columns=['Relacionamento','Ocorrências','Status'])

def rebuild_missing_cost_master():
    c=db();n=0
    rows=c.execute("""select p.id from products p
                      left join cost_master cm on cm.product_id=p.id
                      where p.active=1 and (cm.product_id is null or coalesce(cm.current_cost,0)<=0)""").fetchall()
    for r in rows:
        last=c.execute("""select unit_cost from movements where product_id=? and type='ENTRY' and unit_cost>0
                          order by movement_date desc,id desc limit 1""",(r['id'],)).fetchone()
        if last:
            c.execute("""insert into cost_master(product_id,current_cost,updated_at,notes)
                         values(?,?,?,?)
                         on conflict(product_id) do update set current_cost=excluded.current_cost,
                         updated_at=excluded.updated_at,notes=excluded.notes""",
                      (r['id'],float(last['unit_cost']),datetime.now().isoformat(timespec='seconds'),'Reconstruído V10.1'))
            n+=1
    c.commit();c.close();clear_data_cache();return n

def system_health():
    checks=[]
    c=db()
    try:
        checks.append(('Banco de dados','OK',str(DB)))
        tables=['products','suppliers','invoices','invoice_items','movements','cost_history','cost_master','inventory','inventory_sessions','sales_daily']
        existing={r['name'] for r in c.execute("select name from sqlite_master where type='table'").fetchall()}
        missing=[t for t in tables if t not in existing]
        checks.append(('Tabelas principais','OK' if not missing else 'ERRO','Todas presentes' if not missing else 'Faltando: '+', '.join(missing)))
        orphans=c.execute("""select count(*) n from invoice_items ii left join invoices i on i.id=ii.invoice_id where i.id is null""").fetchone()['n']
        checks.append(('Itens de NF órfãos','OK' if orphans==0 else 'ATENÇÃO',str(orphans)))
        bad_entry=c.execute("""select count(*) n from invoices i
            where upper(i.status)='ENTRADA'
              and (select count(*) from invoice_items ii where ii.invoice_id=i.id) !=
                  (select count(*) from movements m where m.invoice_id=i.id and m.type='ENTRY')""").fetchone()['n']
        checks.append(('NF ENTRADA x movimentos','OK' if bad_entry==0 else 'ATENÇÃO',f'{bad_entry} nota(s) divergente(s)'))
        pending_assoc=c.execute("""select count(*) n from invoice_items ii join invoices i on i.id=ii.invoice_id
                                   where upper(i.status)<>'ENTRADA' and ii.product_id is null""").fetchone()['n']
        checks.append(('Itens pendentes de associação','OK' if pending_assoc==0 else 'PENDENTE',str(pending_assoc)))
        sales=c.execute("select count(*) n from sales_daily").fetchone()['n']
        checks.append(('Vendas diárias','OK',f'{sales} registro(s)'))
    finally:
        c.close()
    return pd.DataFrame(checks,columns=['Teste','Status','Detalhe'])

@st.cache_data(ttl=5,show_spinner=False)
def settings_dict():
    c=db();d={r['key']:r['value'] for r in c.execute('select key,value from settings')};c.close();return d

def supplier(cnpj,name='',trade='',ie='',address='',connection=None):
    own = connection is None
    c = connection or db()
    clean = re.sub(r'\D','',str(cnpj or ''))
    key = clean or str(cnpj or '').strip()
    r=c.execute('select id from suppliers where cnpj=?',(key,)).fetchone()
    if r:
        sid=r['id']
        c.execute("""update suppliers set
          legal_name=case when coalesce(legal_name,'')='' then ? else legal_name end,
          trade_name=case when coalesce(trade_name,'')='' then ? else trade_name end,
          ie=case when coalesce(ie,'')='' then ? else ie end,
          address=case when coalesce(address,'')='' then ? else address end
          where id=?""",(name,trade,ie,address,sid))
    else:
        sid=c.execute('insert into suppliers(cnpj,legal_name,trade_name,ie,address) values(?,?,?,?,?)',
                      (key,name or 'FORNECEDOR SEM RAZÃO SOCIAL',trade,ie,address)).lastrowid
    if own:
        c.commit(); c.close()
    return sid

NS={'n':'http://www.portalfiscal.inf.br/nfe'}
def tx(n,p,default=''):
    if n is None:return default
    v=n.findtext(p,namespaces=NS); return v if v is not None else default

def parse_nfe(raw):
    if not raw:
        raise ValueError('Arquivo XML vazio.')
    try:
        root=etree.fromstring(raw)
    except Exception as e:
        raise ValueError(f'XML inválido: {e}')

    inf=root.find('.//n:infNFe',NS)
    if inf is None and etree.QName(root).localname=='infNFe':
        inf=root
    if inf is None:
        raise ValueError('O arquivo não contém uma NF-e válida (infNFe não encontrado).')

    emit=inf.find('n:emit',NS)
    ide=inf.find('n:ide',NS)
    tot=inf.find('.//n:ICMSTot',NS)
    dest=inf.find('n:dest',NS)

    if emit is None or ide is None:
        raise ValueError('XML NF-e sem dados obrigatórios de emitente/identificação.')

    sup={
        'cnpj':tx(emit,'n:CNPJ') or tx(emit,'n:CPF'),
        'name':tx(emit,'n:xNome'),
        'trade':tx(emit,'n:xFant'),
        'ie':tx(emit,'n:IE'),
        'address':' | '.join(filter(None,[
            tx(emit,'n:enderEmit/n:xLgr'),
            tx(emit,'n:enderEmit/n:nro'),
            tx(emit,'n:enderEmit/n:xBairro'),
            tx(emit,'n:enderEmit/n:xMun'),
            tx(emit,'n:enderEmit/n:UF')
        ]))
    }

    dh=tx(ide,'n:dhEmi') or tx(ide,'n:dEmi')
    access=inf.get('Id','').replace('NFe','').strip()
    if not access:
        ch=root.findtext('.//n:protNFe/n:infProt/n:chNFe',namespaces=NS)
        access=(ch or '').strip()

    inv={
        'access_key':access,
        'number':tx(ide,'n:nNF'),
        'series':tx(ide,'n:serie'),
        'issue_date':dh[:10] if dh else None,
        'total':float(tx(tot,'n:vNF','0') or 0) if tot is not None else 0.0,
        'recipient_cnpj':(tx(dest,'n:CNPJ') or tx(dest,'n:CPF')) if dest is not None else ''
    }

    if not inv['number']:
        raise ValueError('Número da NF-e não encontrado no XML.')

    items=[]
    for det in inf.findall('n:det',NS):
        p=det.find('n:prod',NS)
        if p is None:
            continue
        bc=(tx(p,'n:cEAN') or '').strip()
        if bc.upper() in ('SEM GTIN','SEMGTIN'):
            bc=''
        qty=float(tx(p,'n:qCom','0') or 0)
        unit_value=float(tx(p,'n:vUnCom','0') or 0)
        total=float(tx(p,'n:vProd','0') or 0)
        items.append({
            'supplier_code':tx(p,'n:cProd'),
            'barcode':bc,
            'description':tx(p,'n:xProd'),
            'ncm':tx(p,'n:NCM'),
            'cfop':tx(p,'n:CFOP'),
            'xml_unit':tx(p,'n:uCom'),
            'xml_qty':qty,
            'xml_unit_value':unit_value,
            'xml_total':total
        })

    if not items:
        raise ValueError('A NF-e não possui itens de produto (det/prod).')

    return sup,inv,items

def auto_associate_invoice_items(invoice_id):
    """Reaplica mappings e barcodes conhecidos aos itens ainda sem produto."""
    c=db()
    try:
        c.execute('BEGIN IMMEDIATE')
        inv=c.execute("select supplier_id from invoices where id=?",(invoice_id,)).fetchone()
        if not inv:
            raise ValueError('Nota não encontrada.')
        sid=inv['supplier_id']
        pending=c.execute("""select * from invoice_items where invoice_id=? and product_id is null""",(invoice_id,)).fetchall()
        n=0
        for it in pending:
            match=None
            if it['supplier_code']:
                match=c.execute("""select product_id,multiplier,conversion,commercial_unit,stock_unit
                                   from mappings where supplier_id=? and supplier_code=?""",
                                (sid,it['supplier_code'])).fetchone()
            if not match and it['barcode']:
                pb=c.execute("""select product_id from product_barcodes where barcode=? order by id limit 1""",
                             (str(it['barcode']),)).fetchone()
                if pb:
                    match={'product_id':pb['product_id'],'multiplier':1.0,'conversion':1.0,
                           'commercial_unit':it['xml_unit'],'stock_unit':''}
            if match and match['product_id']:
                pid=int(match['product_id'])
                exists=c.execute("select id,unit from products where id=?",(pid,)).fetchone()
                if not exists:
                    continue
                mult=float(match['multiplier'] or 1)
                conv=float(match['conversion'] or 1)
                qty=float(it['xml_qty'] or 0)*mult*conv
                cost=float(it['xml_total'] or 0)/qty if qty else 0
                comm=(match['commercial_unit'] or it['xml_unit'] or '')
                stock=(match['stock_unit'] or exists['unit'] or '')
                c.execute("""update invoice_items set product_id=?,multiplier=?,conversion=?,
                             commercial_unit=?,stock_unit=?,converted_qty=?,converted_unit_cost=?
                             where id=?""",
                          (pid,mult,conv,comm,stock,qty,cost,it['id']))
                n+=1
        c.commit()
        return n
    except Exception:
        c.rollback();raise
    finally:
        c.close()

def associate_invoice_item(invoice_id,item_id,product_id,reactivate=True):
    """Associa um item à entidade Produto e persiste a regra fornecedor+SKU."""
    c=db()
    try:
        c.execute('BEGIN IMMEDIATE')
        inv=c.execute("select supplier_id from invoices where id=?",(invoice_id,)).fetchone()
        item=c.execute("select * from invoice_items where id=? and invoice_id=?",(item_id,invoice_id)).fetchone()
        prod=c.execute("select * from products where id=?",(product_id,)).fetchone()
        if not inv or not item or not prod:
            raise ValueError('Nota, item ou produto não encontrado.')
        if reactivate and int(prod['active'] if prod['active'] is not None else 1)==0:
            c.execute("update products set active=1 where id=?",(product_id,))
        mult=float(item['multiplier'] or 1)
        conv=float(item['conversion'] or 1)
        qty=float(item['xml_qty'] or 0)*mult*conv
        cost=float(item['xml_total'] or 0)/qty if qty else 0
        comm=str(item['commercial_unit'] or item['xml_unit'] or '')
        stock=str(item['stock_unit'] or prod['unit'] or '')
        c.execute("""update invoice_items set product_id=?,commercial_unit=?,stock_unit=?,
                     converted_qty=?,converted_unit_cost=? where id=?""",
                  (product_id,comm,stock,qty,cost,item_id))
        c.execute("""insert into mappings(
            supplier_id,supplier_code,supplier_barcode,supplier_description,product_id,
            multiplier,conversion,commercial_unit,stock_unit)
            values(?,?,?,?,?,?,?,?,?)
            on conflict(supplier_id,supplier_code) do update set
            supplier_barcode=excluded.supplier_barcode,
            supplier_description=excluded.supplier_description,
            product_id=excluded.product_id,
            multiplier=excluded.multiplier,
            conversion=excluded.conversion,
            commercial_unit=excluded.commercial_unit,
            stock_unit=excluded.stock_unit""",
            (inv['supplier_id'],str(item['supplier_code'] or ''),str(item['barcode'] or ''),
             str(item['description'] or ''),product_id,mult,conv,comm,stock))
        if item['barcode']:
            c.execute("insert or ignore into product_barcodes(product_id,barcode,description) values(?,?,?)",
                      (product_id,str(item['barcode']),'Fornecedor / NF-e'))
        c.commit();clear_data_cache()
        return True
    except Exception:
        c.rollback();raise
    finally:
        c.close()

def invoice_items_view(invoice_id):
    c=db()
    df=pd.read_sql_query("""select ii.id,
        ii.supplier_code 'Cód. Fornecedor',
        ii.description 'Item NF',
        ii.barcode Barcode,
        coalesce(nullif(ii.commercial_unit,''),ii.xml_unit) 'Un. Comercial',
        coalesce(nullif(ii.stock_unit,''),p.unit,'') 'Un. Estoque',
        ii.xml_qty 'Qtd Fiscal',
        ii.xml_total 'Valor Item',
        ii.multiplier 'Fator Mult.',
        ii.conversion 'Fator Conv.',
        ii.converted_qty 'Qtd Estoque',
        ii.converted_unit_cost 'Custo Unitário',
        p.id product_id,p.code 'Cód. Produto',p.name 'Produto Associado',
        case when p.id is null then 'PENDENTE' else 'OK' end Status
        from invoice_items ii
        left join products p on p.id=ii.product_id
        where ii.invoice_id=? order by ii.id""",c,params=[invoice_id])
    c.close()
    return df

def backfill_invoice_mappings_from_history():
    c=db()
    try:
        rows=c.execute("""select i.supplier_id,ii.supplier_code,ii.barcode,ii.description,
                                 ii.product_id,coalesce(ii.multiplier,1) multiplier,
                                 coalesce(ii.conversion,1) conversion,
                                 coalesce(nullif(ii.commercial_unit,''),ii.xml_unit,'') commercial_unit,
                                 coalesce(nullif(ii.stock_unit,''),p.unit,'') stock_unit,
                                 ii.id
                          from invoice_items ii
                          join invoices i on i.id=ii.invoice_id
                          join products p on p.id=ii.product_id
                          where ii.product_id is not null
                            and coalesce(ii.supplier_code,'')<>''
                          order by ii.id desc""").fetchall()
        seen=set();created=0;updated=0
        for r in rows:
            key=(int(r['supplier_id']),str(r['supplier_code']))
            if key in seen:continue
            seen.add(key)
            old=c.execute("select * from mappings where supplier_id=? and supplier_code=?",key).fetchone()
            if not old:
                c.execute("""insert into mappings(
                    supplier_id,supplier_code,supplier_barcode,supplier_description,product_id,
                    multiplier,conversion,commercial_unit,stock_unit)
                    values(?,?,?,?,?,?,?,?,?)""",
                    (r['supplier_id'],r['supplier_code'],str(r['barcode'] or ''),str(r['description'] or ''),
                     r['product_id'],float(r['multiplier'] or 1),float(r['conversion'] or 1),
                     str(r['commercial_unit'] or ''),str(r['stock_unit'] or '')))
                created+=1
            else:
                c.execute("""update mappings set
                    product_id=coalesce(product_id,?),
                    multiplier=case when multiplier is null or multiplier=0 then ? else multiplier end,
                    conversion=case when conversion is null or conversion=0 then ? else conversion end,
                    commercial_unit=coalesce(nullif(commercial_unit,''),?),
                    stock_unit=coalesce(nullif(stock_unit,''),?),
                    supplier_barcode=coalesce(nullif(supplier_barcode,''),?),
                    supplier_description=coalesce(nullif(supplier_description,''),?)
                    where id=?""",
                    (r['product_id'],float(r['multiplier'] or 1),float(r['conversion'] or 1),
                     str(r['commercial_unit'] or ''),str(r['stock_unit'] or ''),
                     str(r['barcode'] or ''),str(r['description'] or ''),old['id']))
                updated+=1
        c.commit()
        return {'created':created,'updated':updated,'scanned':len(seen)}
    except Exception:
        c.rollback();raise
    finally:
        c.close()

def invoice_product_options():
    """Lista completa para dropdown de associação, incluindo inativos."""
    c=db()
    df=pd.read_sql_query("""select id,code,name,coalesce(brand,'') brand,
        coalesce(category,'') category,coalesce(subcategory,'') subcategory,
        coalesce(unit,'') unit,coalesce(active,1) active
        from products order by coalesce(active,1) desc,name""",c)
    c.close()
    labels=['— NÃO ASSOCIADO —']
    label_to_id={'— NÃO ASSOCIADO —':None}
    id_to_label={}
    for _,r in df.iterrows():
        status='' if int(r['active'] or 0)==1 else ' [INATIVO]'
        label=f"{int(r['code'])} | {r['name']} | {r['category']} | {r['unit']}{status}"
        labels.append(label)
        label_to_id[label]=int(r['id'])
        id_to_label[int(r['id'])]=label
    return labels,label_to_id,id_to_label

def save_invoice_grid(invoice_id,grid,label_to_id,reactivate=True):
    """
    Salva descrição/valores/unidades/fatores + associação de TODOS os itens.
    Uma única transação. Não cria movimentos de estoque.
    """
    c=db()
    try:
        c.execute('BEGIN IMMEDIATE')
        inv=c.execute("select supplier_id,status from invoices where id=?",(invoice_id,)).fetchone()
        if not inv:
            raise ValueError('Nota não encontrada.')
        if str(inv['status']).upper()=='ENTRADA':
            raise ValueError('A nota já está em ENTRADA. Reabra antes de alterar.')

        sid=inv['supplier_id']
        pending=[]
        for _,r in grid.iterrows():
            item_id=int(r['id'])
            label=str(r['Produto Associado'] or '— NÃO ASSOCIADO —')
            pid=label_to_id.get(label)

            desc=str(r['Item NF'] or '').strip()
            barcode=str(r['Barcode'] or '').strip()
            comm=str(r['Un. Comercial'] or '').strip()
            stock=str(r['Un. Estoque'] or '').strip()
            qty=round_entry(r['Qtd Fiscal'] or 0)
            total=round_entry(r['Valor Item'] or 0)
            mult=round_entry(r['Fator Mult.'] or 1)
            conv=round_entry(r['Fator Conv.'] or 1)

            if qty<=0:
                raise ValueError(f'Quantidade fiscal inválida em: {desc}')
            if mult<=0 or conv<=0:
                raise ValueError(f'Fator inválido em: {desc}')

            converted=round_entry(qty*mult*conv)
            unit_cost=round_entry(total/converted) if converted else 0.0

            if not pid:
                pending.append(desc)

            prod=None
            if pid:
                prod=c.execute("select id,unit,active from products where id=?",(pid,)).fetchone()
                if not prod:
                    raise ValueError(f'Produto associado não existe mais: {desc}')
                if reactivate and int(prod['active'] if prod['active'] is not None else 1)==0:
                    c.execute("update products set active=1 where id=?",(pid,))
                if not stock:
                    stock=str(prod['unit'] or '')

            c.execute("""update invoice_items set
                         description=?,barcode=?,commercial_unit=?,stock_unit=?,
                         xml_qty=?,xml_total=?,multiplier=?,conversion=?,
                         converted_qty=?,converted_unit_cost=?,product_id=?
                         where id=? and invoice_id=?""",
                      (desc,barcode,comm,stock,qty,total,mult,conv,
                       converted,unit_cost,pid,item_id,invoice_id))

            item=c.execute("select supplier_code from invoice_items where id=?",(item_id,)).fetchone()

            if pid:
                c.execute("""insert into mappings(
                    supplier_id,supplier_code,supplier_barcode,supplier_description,
                    product_id,multiplier,conversion,commercial_unit,stock_unit)
                    values(?,?,?,?,?,?,?,?,?)
                    on conflict(supplier_id,supplier_code) do update set
                    supplier_barcode=excluded.supplier_barcode,
                    supplier_description=excluded.supplier_description,
                    product_id=excluded.product_id,
                    multiplier=excluded.multiplier,
                    conversion=excluded.conversion,
                    commercial_unit=excluded.commercial_unit,
                    stock_unit=excluded.stock_unit""",
                    (sid,str(item['supplier_code'] or ''),barcode,desc,pid,
                     mult,conv,comm,stock))

                if barcode:
                    c.execute("""insert or ignore into product_barcodes(product_id,barcode,description)
                                 values(?,?,?)""",
                              (pid,barcode,'Fornecedor / NF-e'))

                if stock:
                    c.execute("update products set unit=? where id=?",(stock,pid))

        total_note=float(c.execute(
            "select coalesce(sum(xml_total),0) v from invoice_items where invoice_id=?",
            (invoice_id,)
        ).fetchone()['v'] or 0)

        c.execute("""update invoices set total=?,edit_status='ABERTA'
                     where id=?""",(total_note,invoice_id))

        c.commit()
        clear_data_cache()
        return {'ok':True,'pending':pending,'total':total_note}
    except Exception:
        c.rollback()
        raise
    finally:
        c.close()


def import_nfe(raw,source='XML'):
    sup,inv,items=parse_nfe(raw)
    if not inv['access_key']:
        raise ValueError('Chave de acesso da NF-e não encontrada.')

    sid=supplier(sup['cnpj'],sup['name'],sup['trade'],sup['ie'],sup['address'])
    c=db()
    old=c.execute('select id,status from invoices where access_key=?',(inv['access_key'],)).fetchone()
    if old:
        c.close()
        return int(old['id']),False,'NF-e já existente no sistema.'

    try:
        iid=c.execute("""insert into invoices(
            access_key,number,series,issue_date,entry_date,supplier_id,total,status,source,edit_status)
            values(?,?,?,?,?,?,?,?,?,'ABERTA')""",
            (inv['access_key'],inv['number'],inv['series'],inv['issue_date'],
             datetime.now().isoformat(),sid,inv['total'],'PENDENTE',source)).lastrowid

        for it in items:
            m=c.execute('select * from mappings where supplier_id=? and supplier_code=?',
                        (sid,it['supplier_code'])).fetchone()
            pid=m['product_id'] if m else None
            if not pid and it['barcode']:
                _pb=c.execute("select product_id from product_barcodes where barcode=? order by id limit 1",(str(it['barcode']),)).fetchone()
                pid=_pb['product_id'] if _pb else None
            mult=float(m['multiplier'] or 1) if m else 1.0
            conv=float(m['conversion'] or 1) if m else 1.0
            cq=round_entry(float(it['xml_qty'] or 0)*mult*conv)
            uc=round_entry(float(it['xml_total'] or 0)/cq) if cq else 0.0

            comm=(m['commercial_unit'] if m and 'commercial_unit' in m.keys() and m['commercial_unit'] else it['xml_unit'])
            stock=(m['stock_unit'] if m and 'stock_unit' in m.keys() and m['stock_unit'] else '')
            c.execute("""insert into invoice_items(
                invoice_id,supplier_code,barcode,description,ncm,cfop,xml_unit,
                xml_qty,xml_unit_value,xml_total,product_id,multiplier,conversion,
                converted_qty,converted_unit_cost,commercial_unit,stock_unit)
                values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (iid,it['supplier_code'],it['barcode'],it['description'],it['ncm'],it['cfop'],
                 it['xml_unit'],it['xml_qty'],it['xml_unit_value'],it['xml_total'],
                 pid,mult,conv,cq,uc,comm,stock))

            if pid and it['barcode']:
                c.execute('insert or ignore into product_barcodes(product_id,barcode,description) values(?,?,?)',
                          (pid,it['barcode'],'Fornecedor / NF-e'))

        c.commit()
        return int(iid),True,f"NF-e {inv['number']} importada com {len(items)} item(ns)."
    except Exception:
        c.rollback()
        raise
    finally:
        c.close()

def import_nfe_id(raw,source='XML'):
    iid,_,_=import_nfe(raw,source)
    return iid

def confirmed_purchases_total(a,b):
    return purchases_value(a,b,None)


def period_stats(a,b):
    c=db()
    n=c.execute("select count(*) n from sales_daily where sale_date between ? and ?",(str(a),str(b))).fetchone()['n']
    c.close()
    sales=consolidated_sales_value(a,b) if n else 0.0
    if not n:
        c=db();sales=float(c.execute('select coalesce(sum(net_sales),0) v from sales where sale_date between ? and ?',(str(a),str(b))).fetchone()['v'] or 0);c.close()
    c=db()
    purchases=confirmed_purchases_total(a,b)
    losses=float(c.execute('select coalesce(sum(qty*unit_cost),0) v from losses where loss_date between ? and ?',(str(a),str(b))).fetchone()['v'] or 0)
    c.close()
    return sales,purchases,losses

def inventory_value_at(d):
    return inventory_value_at_category(d,None)

def accounting_cogs(a,b):
    opening,purchases,closing,cogs=cogs_inventory(a,b,None)
    return cogs


def _dfe_soap(dist_xml,url,pfx,password,timeout=60):
    """Chamada mTLS ao Web Service oficial NFeDistribuicaoDFe."""
    soap=f'''<?xml version="1.0" encoding="utf-8"?>
    <soap12:Envelope xmlns:soap12="http://www.w3.org/2003/05/soap-envelope">
      <soap12:Body>
        <nfeDistDFeInteresse xmlns="http://www.portalfiscal.inf.br/nfe/wsdl/NFeDistribuicaoDFe">
          <nfeDadosMsg>{dist_xml}</nfeDadosMsg>
        </nfeDistDFeInteresse>
      </soap12:Body>
    </soap12:Envelope>'''
    r=pkcs12_post(url,data=soap.encode('utf-8'),
                  headers={'Content-Type':'application/soap+xml; charset=utf-8'},
                  pkcs12_filename=str(pfx),pkcs12_password=password,timeout=timeout)
    r.raise_for_status()
    try:
        root=etree.fromstring(r.content)
    except Exception as ex:
        raise RuntimeError(f'Resposta inválida do SEFAZ: {ex}')
    cs=root.xpath("//*[local-name()='cStat']/text()")
    xm=root.xpath("//*[local-name()='xMotivo']/text()")
    u=root.xpath("//*[local-name()='ultNSU']/text()")
    m=root.xpath("//*[local-name()='maxNSU']/text()")
    docs=[]
    for el in root.xpath("//*[local-name()='docZip']"):
        try:
            raw=base64.b64decode((el.text or '').strip())
            xml=gzip.GzipFile(fileobj=io.BytesIO(raw)).read()
            docs.append((str(el.get('NSU') or ''),str(el.get('schema') or ''),xml))
        except Exception as ex:
            app_log('DF-e SEFAZ','Falha descompactação docZip',f"NSU {el.get('NSU')}: {ex}")
    return {
        'ultNSU':u[0] if u else '',
        'maxNSU':m[0] if m else '',
        'docs':docs,
        'cstat':cs[0] if cs else '',
        'message':xm[0] if xm else ''
    }

def _dfe_tpamb(hom):
    # distDFeInt exige tpAmb antes de cUFAutor. 1=Produção, 2=Homologação.
    return '2' if hom else '1'

def _dfe_status_ok(cstat):
    # 137 = nenhum documento localizado; 138 = documento(s) localizado(s).
    return str(cstat or '').strip() in ('137','138')

def _dfe_request_preview(cnpj,uf,ult,hom,access_key=''):
    clean=re.sub(r'\D','',cnpj or '')
    tp=_dfe_tpamb(hom)
    if access_key:
        key=re.sub(r'\D','',access_key or '')
        query=f'<consChNFe><chNFe>{key}</chNFe></consChNFe>'
    else:
        query=f'<distNSU><ultNSU>{str(ult or "0").zfill(15)}</ultNSU></distNSU>'
    return (f'<distDFeInt xmlns="http://www.portalfiscal.inf.br/nfe" versao="1.01">'
            f'<tpAmb>{tp}</tpAmb><cUFAutor>{str(uf).zfill(2)}</cUFAutor><CNPJ>{clean}</CNPJ>'
            f'{query}</distDFeInt>')

def dfe_sync(cnpj,uf,pfx,password,ult,hom):
    clean=re.sub(r'\D','',cnpj)
    if len(clean)!=14:raise ValueError('CNPJ deve possuir 14 dígitos.')
    url=SEFAZ_HOM if hom else SEFAZ_PROD
    dist=_dfe_request_preview(clean,uf,ult,hom)
    ret=_dfe_soap(dist,url,pfx,password)
    # Só avança ultNSU quando a resposta efetivamente trouxer um NSU.
    newult=ret['ultNSU'] if ret['ultNSU'] else str(ult or '000000000000000').zfill(15)
    return newult,ret['maxNSU'],ret['docs'],ret['cstat'],ret['message']

def dfe_query_key(cnpj,uf,pfx,password,access_key,hom):
    """Consulta pontual da chave, sem avançar o ultNSU salvo."""
    clean=re.sub(r'\D','',cnpj)
    key=re.sub(r'\D','',access_key or '')
    if len(clean)!=14:raise ValueError('CNPJ deve possuir 14 dígitos.')
    if len(key)!=44:raise ValueError('Chave NF-e deve possuir 44 dígitos.')
    url=SEFAZ_HOM if hom else SEFAZ_PROD
    dist=_dfe_request_preview(clean,uf,'000000000000000',hom,key)
    ret=_dfe_soap(dist,url,pfx,password)
    return ret['docs'],ret['cstat'],ret['message']

def _dfe_doc_meta(schema,xml):
    """Extrai metadados sem inventar campos ausentes."""
    access=issuer=name=issue=None
    total=0.0
    full_xml=0
    source_kind='OUTRO'
    status='DOCUMENTO'
    try:
        rt=etree.fromstring(xml)
        local=etree.QName(rt).localname
        ns='{http://www.portalfiscal.inf.br/nfe}'
        if 'resNFe' in str(schema) or local=='resNFe':
            access=rt.findtext(ns+'chNFe')
            issuer=rt.findtext(ns+'CNPJ') or rt.findtext(ns+'CPF')
            name=rt.findtext(ns+'xNome')
            issue=(rt.findtext(ns+'dhEmi') or '')[:10]
            total=float(rt.findtext(ns+'vNF') or 0)
            status='RESUMO'
            source_kind='NF-e RESUMO'
        elif 'procNFe' in str(schema) or local=='nfeProc':
            sup,inv,_items=parse_nfe(xml)
            access=inv['access_key'];issuer=sup['cnpj'];name=sup['name']
            issue=inv['issue_date'];total=inv['total']
            status='XML COMPLETO'
            full_xml=1
            source_kind='NF-e COMPLETA'
        elif 'resEvento' in str(schema) or local in ('resEvento','procEventoNFe'):
            access=(rt.xpath("string(.//*[local-name()='chNFe'])") or '').strip()
            issuer=(rt.xpath("string(.//*[local-name()='CNPJ'])") or '').strip()
            status='EVENTO'
            source_kind='EVENTO'
        else:
            access=(rt.xpath("string(.//*[local-name()='chNFe'])") or '').strip() or None
    except Exception:
        pass
    return {'access_key':access,'issuer_cnpj':issuer,'issuer_name':name,'issue_date':issue,
            'total':total,'status':status,'full_xml':full_xml,'source_kind':source_kind}

def save_dfe(docs,recipient_cnpj=''):
    """Salva todos os DF-e e importa automaticamente a NF-e completa como PENDENTE."""
    saved=0;full_count=0;imported=0;errors=[]
    clean_rec=re.sub(r'\D','',recipient_cnpj or '')
    for nsu,schema,xml in docs:
        safe_schema=re.sub(r'[^A-Za-z0-9_.-]+','_',str(schema or 'documento'))
        meta=_dfe_doc_meta(schema,xml)
        key_hint='_'+str(meta['access_key'])[-12:] if meta['access_key'] else ''
        nsu_key=str(nsu or hashlib.sha256(xml).hexdigest()[:15])
        filename=f'{nsu_key.zfill(15)}{key_hint}_{safe_schema}.xml'
        path=XML_DIR/filename
        path.write_bytes(xml)
        sha=hashlib.sha256(xml).hexdigest()
        invoice_id=None;import_error=''
        if meta['full_xml']:
            full_count+=1
            try:
                invoice_id=import_nfe_id(xml,'SEFAZ')
                imported+=1
            except Exception as ex:
                import_error=str(ex)
                errors.append(f"{meta['access_key'] or nsu_key}: {ex}")

        c=db()
        try:
            c.execute('''insert into dfe_docs(
                nsu,schema,access_key,issuer_cnpj,issuer_name,issue_date,total,status,xml_path,received_at,
                recipient_cnpj,invoice_id,last_query_at,import_error,xml_sha256,full_xml,source_kind)
                values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                on conflict(nsu) do update set
                schema=excluded.schema,
                access_key=coalesce(nullif(excluded.access_key,''),dfe_docs.access_key),
                issuer_cnpj=coalesce(nullif(excluded.issuer_cnpj,''),dfe_docs.issuer_cnpj),
                issuer_name=coalesce(nullif(excluded.issuer_name,''),dfe_docs.issuer_name),
                issue_date=coalesce(nullif(excluded.issue_date,''),dfe_docs.issue_date),
                total=case when excluded.total<>0 then excluded.total else dfe_docs.total end,
                status=case when excluded.full_xml=1 then 'XML COMPLETO' else excluded.status end,
                xml_path=excluded.xml_path,received_at=excluded.received_at,
                recipient_cnpj=case when excluded.recipient_cnpj<>'' then excluded.recipient_cnpj else dfe_docs.recipient_cnpj end,
                invoice_id=coalesce(excluded.invoice_id,dfe_docs.invoice_id),
                last_query_at=excluded.last_query_at,import_error=excluded.import_error,
                xml_sha256=excluded.xml_sha256,full_xml=max(coalesce(dfe_docs.full_xml,0),excluded.full_xml),
                source_kind=excluded.source_kind''',
                (nsu_key,schema,meta['access_key'],meta['issuer_cnpj'],meta['issuer_name'],
                 meta['issue_date'],meta['total'],meta['status'],str(path),datetime.now().isoformat(timespec='seconds'),
                 clean_rec,invoice_id,datetime.now().isoformat(timespec='seconds'),import_error,sha,
                 int(meta['full_xml']),meta['source_kind']))
            if meta['access_key'] and not invoice_id:
                inv=c.execute("select id from invoices where access_key=?",(meta['access_key'],)).fetchone()
                if inv:
                    c.execute("update dfe_docs set invoice_id=? where nsu=?",(int(inv['id']),nsu_key))
            c.commit()
            saved+=1
        finally:
            c.close()
    return {'saved':saved,'full_xml':full_count,'imported':imported,'errors':errors}

def dfe_log_sync(mode,access_key='',ult_before='',ult_after='',max_nsu='',cstat='',message='',docs_received=0,success=True):
    try:
        c=db()
        c.execute('''insert into dfe_sync_log(event_date,mode,access_key,ult_nsu_before,ult_nsu_after,max_nsu,
                     cstat,message,docs_received,success) values(?,?,?,?,?,?,?,?,?,?)''',
                  (datetime.now().isoformat(timespec='seconds'),mode,access_key,ult_before,ult_after,max_nsu,
                   cstat,message,int(docs_received or 0),1 if success else 0))
        c.commit();c.close()
    except Exception:pass

def dfe_requery_key(access_key,password=''):
    cfg=settings_dict();cnpj=cfg.get('cnpj','');uf=cfg.get('uf','33');pfx=resolve_sefaz_pfx()
    pwd=password or resolve_sefaz_password()
    hom=cfg.get('ambiente','Produção')=='Homologação'
    if not (cnpj and pfx and pwd):raise ValueError('Configure CNPJ, certificado PFX/P12 e senha.')
    docs,cstat,msg=dfe_query_key(cnpj,uf,pfx,pwd,access_key,hom)
    result=save_dfe(docs,cnpj)
    c=db();c.execute("update dfe_docs set last_query_at=? where access_key=?",
                     (datetime.now().isoformat(timespec='seconds'),str(access_key)));c.commit();c.close()
    dfe_log_sync('CONSULTA_CHAVE',access_key=access_key,cstat=cstat,message=msg,
                 docs_received=len(docs),success=True)
    return result,cstat,msg

def dfe_pending_df(cnpj=''):
    """Uma linha por chave NF-e; prefere XML completo e vincula a invoice quando existir."""
    clean=re.sub(r'\D','',cnpj or '')
    c=db()
    df=pd.read_sql_query("""
    with ranked as (
      select d.*,
             row_number() over(
               partition by coalesce(nullif(d.access_key,''),'NSU:'||d.nsu)
               order by coalesce(d.full_xml,0) desc,d.id desc
             ) rn
      from dfe_docs d
      where (?='' or coalesce(d.recipient_cnpj,'') in ('',?))
    )
    select r.id,r.nsu NSU,r.access_key Chave,r.issuer_name Emitente,r.issuer_cnpj CNPJ,
           r.issue_date Emissão,r.total Valor,r.status 'Status DF-e',r.schema Schema,
           r.xml_path 'Arquivo XML',r.full_xml 'XML Completo',r.invoice_id 'Nota ID',
           coalesce(i.status,'') 'Status Nota',coalesce(i.number,'') NF,
           r.last_query_at 'Última Consulta',r.import_error 'Erro Importação'
    from ranked r
    left join invoices i on i.id=coalesce(r.invoice_id,(select id from invoices ii where ii.access_key=r.access_key limit 1))
    where r.rn=1 and coalesce(i.status,'PENDENTE')<>'ENTRADA'
    order by coalesce(r.issue_date,'') desc,r.id desc
    """,c,params=[clean,clean])
    c.close()
    return df

def dfe_doc_bytes(doc_id):
    c=db();r=c.execute("select xml_path,access_key,schema from dfe_docs where id=?",(int(doc_id),)).fetchone();c.close()
    if not r:return None,None
    path=Path(str(r['xml_path'] or ''))
    if not path.exists():return None,None
    name=f"NFe_{r['access_key'] or doc_id}.xml" if 'procNFe' in str(r['schema']) else f"DFE_{r['access_key'] or doc_id}.xml"
    return path.read_bytes(),name

def dfe_entry_readiness(invoice_id):
    if not invoice_id:return {'ready':False,'pending':0,'invalid':0,'items':0}
    df=invoice_items_view(int(invoice_id))
    if df.empty:return {'ready':False,'pending':0,'invalid':0,'items':0}
    pending=int((df['Status']!='OK').sum())
    q=pd.to_numeric(df['Qtd Estoque'],errors='coerce').fillna(0)
    cost=pd.to_numeric(df['Custo Unitário'],errors='coerce').fillna(0)
    invalid=int(((q<=0)|(cost<=0)).sum())
    return {'ready':pending==0 and invalid==0,'pending':pending,'invalid':invalid,'items':len(df)}

def resolve_sefaz_pfx():
    cfg=settings_dict()
    pfx=cfg.get('pfx_path','')
    if pfx and Path(pfx).exists():
        return pfx
    # Community Cloud: o PFX pode ser guardado em Secrets como base64.
    try:b64=st.secrets.get('SEFAZ_PFX_BASE64','')
    except Exception:b64=''
    b64=b64 or os.environ.get('SEFAZ_PFX_BASE64','')
    if b64:
        path=CERT_DIR/'certificado_cloud.pfx'
        if not path.exists():
            path.write_bytes(base64.b64decode(b64))
        return str(path)
    return ''


def pfx_certificate_info(pfx_path,password):
    if not pfx_path or not Path(pfx_path).exists():
        raise ValueError('Certificado PFX/P12 não encontrado.')
    raw=Path(pfx_path).read_bytes()
    key,cert,chain=pkcs12.load_key_and_certificates(
        raw,(str(password).encode('utf-8') if password is not None else None)
    )
    if cert is None:raise ValueError('O PFX não contém certificado.')
    try:subject=cert.subject.rfc4514_string()
    except Exception:subject=''
    try:issuer=cert.issuer.rfc4514_string()
    except Exception:issuer=''
    try:
        expires=getattr(cert,'not_valid_after_utc',None) or cert.not_valid_after
        exp=expires.isoformat()
        days=(expires.replace(tzinfo=None)-datetime.now()).days
    except Exception:
        exp='';days=None
    return {'subject':subject,'issuer':issuer,'expires':exp,'days':days,'has_private_key':key is not None}

def resolve_sefaz_password():
    try:pw=st.secrets.get('SEFAZ_PFX_PASSWORD','')
    except Exception:pw=''
    return pw or os.environ.get('SEFAZ_PFX_PASSWORD','')

def auto_sync_sefaz_if_due(force=False):
    cfg=settings_dict()
    if str(cfg.get('sefaz_auto_sync','1'))!='1' and not force:return None
    cnpj=cfg.get('cnpj','');uf=cfg.get('uf','33');pfx=resolve_sefaz_pfx()
    try:pw=st.secrets.get('SEFAZ_PFX_PASSWORD','')
    except Exception:pw=''
    pw=pw or os.environ.get('SEFAZ_PFX_PASSWORD','')
    if not (cnpj and pfx and pw):
        return {'ok':False,'message':'Auto-sync aguardando CNPJ, PFX e senha configurados localmente.'}
    last=cfg.get('sefaz_last_sync','')
    if not force and last:
        try:
            delta=datetime.now()-datetime.fromisoformat(last)
            if delta.total_seconds()<3600:
                return {'ok':True,'skipped':True,'message':'Última consulta ocorreu há menos de 1 hora.'}
        except Exception:pass
    ult=cfg.get('ult_nsu','000000000000000')
    hom=cfg.get('ambiente','Produção')=='Homologação'
    try:
        newult,maxn,docs,cstat,xmotivo=dfe_sync(cnpj,uf,pfx,pw,ult,hom)
        saved=save_dfe(docs,cnpj)
        ok_status=_dfe_status_ok(cstat)
        dfe_log_sync('DIST_NSU',ult_before=ult,ult_after=newult,max_nsu=maxn or '',
                     cstat=cstat,message=xmotivo,docs_received=len(docs),success=ok_status)
        now=datetime.now().isoformat(timespec='seconds')
        c=db()
        for k,v in [('ult_nsu',newult),('sefaz_last_sync',now),('sefaz_last_cstat',cstat),('sefaz_last_message',xmotivo),('sefaz_last_maxnsu',maxn or '')]:
            c.execute("insert into settings(key,value) values(?,?) on conflict(key) do update set value=excluded.value",(k,str(v)))
        c.commit();c.close()
        if not ok_status:
            return {'ok':False,'count':len(docs),'saved':saved,'cstat':cstat,
                    'message':f'cStat {cstat}: {xmotivo}','ult':newult,'max':maxn}
        return {'ok':True,'count':len(docs),'saved':saved,'cstat':cstat,'message':xmotivo,'ult':newult,'max':maxn}
    except Exception as e:
        dfe_log_sync('DIST_NSU',ult_before=ult,cstat='',message=str(e),docs_received=0,success=False)
        c=db()
        c.execute("insert into settings(key,value) values('sefaz_last_error',?) on conflict(key) do update set value=excluded.value",(str(e),))
        c.commit();c.close()
        return {'ok':False,'message':str(e)}

def assistant(q):
    x=q.lower();c=db()
    try:
        if 'consumo' in x:return 'Produtos de maior consumo',pd.read_sql_query("select p.code Código,p.name Produto,p.category Categoria,sum(-m.qty) Consumo,sum((-m.qty)*m.unit_cost) Valor from movements m join products p on p.id=m.product_id where m.type in ('WITHDRAWAL','LOSS') group by p.id order by Consumo desc limit 50",c)
        if 'perda' in x:return 'Perdas por causa',pd.read_sql_query('select cause Causa,sum(qty) Quantidade,sum(qty*unit_cost) Valor from losses group by cause order by Valor desc',c)
        if 'fornecedor' in x or 'cotação' in x or 'cotacao' in x:return 'Cotações por fornecedor',pd.read_sql_query('select p.name Produto,s.legal_name Fornecedor,q.unit_cost Custo,q.lead_days Prazo from quotes q join products p on p.id=q.product_id join suppliers s on s.id=q.supplier_id order by p.name,q.unit_cost',c)
        if 'categoria' in x or 'representatividade' in x:
            d=pd.read_sql_query("select p.category Categoria,sum(ii.xml_total) Valor from invoice_items ii join invoices i on i.id=ii.invoice_id join products p on p.id=ii.product_id where i.status='ENTRADA' group by p.category order by Valor desc",c); d['%']=d.Valor/d.Valor.sum()*100 if not d.empty else 0;return 'Representatividade por categoria',d
        if 'custo' in x or 'caro' in x or 'ranking' in x:return 'Ranking de custos',pd.read_sql_query("select p.code Código,p.name Produto,p.category Categoria,avg(m.unit_cost) 'Custo Médio',max(m.unit_cost) 'Maior Custo',min(m.unit_cost) 'Menor Custo' from movements m join products p on p.id=m.product_id where m.type='ENTRY' and m.unit_cost>0 group by p.id order by 'Custo Médio' desc limit 50",c)
        return 'Exemplos de consultas',pd.DataFrame({'Perguntas':['produtos de maior consumo','ranking de custos','perdas por causa','fornecedores mais em conta','representatividade por categoria']})
    finally:c.close()


def item_timeline(pid):
    c=db()
    mov=pd.read_sql_query("""select m.id 'Movimento ID',m.movement_date Data,m.type Tipo,m.qty Quantidade,m.unit_cost Custo,
                         coalesce(m.reference,'') Referência,coalesce(m.notes,'') Observações,
                         i.id 'Nota ID',i.number NF,i.issue_date 'Data NF',i.status 'Status NF',
                         s.legal_name Fornecedor
                         from movements m
                         left join invoices i on i.id=m.invoice_id
                         left join suppliers s on s.id=i.supplier_id
                         where m.product_id=? order by m.movement_date,m.id""",c,params=[pid])
    inv=pd.read_sql_query("""select inventory_date Data,counted_qty Contagem,avg_cost_3m Custo,
                         total_value Valor,coalesce(notes,'') Observações,session_id
                         from inventory where product_id=? order by inventory_date,id""",c,params=[pid])
    pending_nf=pd.read_sql_query("""select i.id 'Nota ID',i.number NF,i.issue_date 'Data NF',
                         i.entry_date Data,i.status 'Status NF',s.legal_name Fornecedor,
                         ii.description 'Item NF',ii.converted_qty Quantidade,
                         ii.converted_unit_cost Custo,ii.xml_total Valor
                         from invoice_items ii join invoices i on i.id=ii.invoice_id
                         left join suppliers s on s.id=i.supplier_id
                         where ii.product_id=? and upper(coalesce(i.status,'PENDENTE'))<>'ENTRADA'
                         order by i.issue_date,i.id,ii.id""",c,params=[pid])
    c.close()
    events=[];saldo=0.0
    for _,r in mov.iterrows():
        q=float(r['Quantidade'] or 0);saldo+=q
        ref=r['Referência'] or ''
        events.append({
            'Data_dt':pd.to_datetime(r['Data'],errors='coerce'),
            'Tipo':r['Tipo'],'Quantidade':q,'Custo':float(r['Custo'] or 0),
            'Valor':abs(q)*float(r['Custo'] or 0),'Saldo Acumulado':saldo,
            'Nota ID':int(r['Nota ID']) if pd.notna(r['Nota ID']) else None,
            'NF':str(r['NF'] or '') if pd.notna(r['NF']) else '',
            'Data NF':str(r['Data NF'] or '') if pd.notna(r['Data NF']) else '',
            'Status NF':str(r['Status NF'] or '') if pd.notna(r['Status NF']) else '',
            'Fornecedor':str(r['Fornecedor'] or '') if pd.notna(r['Fornecedor']) else '',
            'Referência':ref,'Observações':r['Observações'] or ''
        })
    for _,r in pending_nf.iterrows():
        events.append({
            'Data_dt':pd.to_datetime(r['Data NF'] or r['Data'],errors='coerce'),
            'Tipo':'NF PENDENTE / ITEM FISCAL',
            'Quantidade':float(r['Quantidade'] or 0),'Custo':float(r['Custo'] or 0),
            'Valor':float(r['Valor'] or 0),'Saldo Acumulado':None,
            'Nota ID':int(r['Nota ID']) if pd.notna(r['Nota ID']) else None,
            'NF':str(r['NF'] or ''),'Data NF':str(r['Data NF'] or ''),
            'Status NF':str(r['Status NF'] or ''),'Fornecedor':str(r['Fornecedor'] or ''),
            'Referência':f"NF {r['NF']} — item pendente",
            'Observações':str(r['Item NF'] or '')
        })
    for _,r in inv.iterrows():
        events.append({
            'Data_dt':pd.to_datetime(r['Data'],errors='coerce'),'Tipo':'INVENTÁRIO (CONTAGEM)',
            'Quantidade':float(r['Contagem'] or 0),'Custo':float(r['Custo'] or 0),
            'Valor':float(r['Valor'] or 0),'Saldo Acumulado':None,
            'Nota ID':None,'NF':'','Data NF':'','Status NF':'','Fornecedor':'',
            'Referência':f"Inventário #{r['session_id'] or ''}",
            'Observações':r['Observações'] or ''
        })
    if not events:
        return pd.DataFrame(columns=[
            'Data','Tipo','Quantidade','Custo','Valor','Saldo Acumulado','Nota ID','NF',
            'Data NF','Status NF','Fornecedor','Referência','Observações'
        ])
    df=pd.DataFrame(events).sort_values('Data_dt').reset_index(drop=True)
    df['Data']=df['Data_dt'].dt.strftime('%d/%m/%Y %H:%M').fillna('')
    return df[['Data','Tipo','Quantidade','Custo','Valor','Saldo Acumulado','Nota ID','NF',
               'Data NF','Status NF','Fornecedor','Referência','Observações']]

def installed_printers():
    try:
        cp=subprocess.run(['powershell','-NoProfile','-Command','Get-Printer | Select-Object -ExpandProperty Name'],
                          capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=15)
        return [x.strip() for x in cp.stdout.splitlines() if x.strip()]
    except Exception:
        return []

def direct_print_pdf(pdf_bytes,printer_name=None):
    export_dir=ROOT/'exports'; export_dir.mkdir(exist_ok=True)
    path=export_dir/'ETIQUETAS_ULTIMA_IMPRESSAO.pdf'; path.write_bytes(pdf_bytes)
    if os.name!='nt':
        raise RuntimeError('Impressão direta está disponível no Windows. Use o PDF em outros sistemas.')
    if printer_name and printer_name!='Impressora padrão do Windows':
        safe=str(printer_name).replace("'","''")
        cmd=f"Start-Process -FilePath '{str(path)}' -Verb PrintTo -ArgumentList '\"{safe}\"'"
        subprocess.Popen(['powershell','-NoProfile','-Command',cmd])
    else:
        os.startfile(str(path),'print')
    return path


def set_flash(message,kind='success'):
    st.session_state['_hnt_flash']={'message':str(message),'kind':str(kind)}

def confirm_success(message):
    set_flash(message,'success')
    st.success('✅ '+str(message))

def render_flash():
    item=st.session_state.pop('_hnt_flash',None)
    if not item:return
    msg=item.get('message','')
    kind=item.get('kind','success')
    if kind=='error':st.error('❌ '+msg)
    elif kind=='warning':st.warning('⚠️ '+msg)
    else:confirm_success('✅ '+msg)


ALL_MODULES=[
    'Dashboard','Vendas','Notas / XML','Compras Avulsas','DF-e SEFAZ','Produtos','Fornecedores',
    'Associações & Conversões','Estoque Inicial','Estoque','Extrato de Itens','Extrato de Custos',
    'Custos Médios','Inventário','Contagem & Compras','Retiradas','Perdas','Cotações','CMV & BI',
    'Controle Produção Proteínas','Relatórios','Central de Correções','Config. Operacional',
    'Assistente IA','Etiquetas','Logs','Configurações','Usuários & Acessos'
]

ROLE_DEFAULT_MODULES={
    'ADMIN':ALL_MODULES,
    'GERENTE':[m for m in ALL_MODULES if m!='Usuários & Acessos'],
    'ESTOQUE':['Dashboard','Notas / XML','Compras Avulsas','DF-e SEFAZ','Produtos','Fornecedores',
               'Associações & Conversões','Estoque Inicial','Estoque','Extrato de Itens','Extrato de Custos',
               'Custos Médios','Inventário','Contagem & Compras','Retiradas','Perdas','Cotações',
               'Controle Produção Proteínas','Relatórios','Etiquetas'],
    'OPERADOR':['Dashboard','Notas / XML','Estoque','Extrato de Itens','Inventário','Contagem & Compras',
                'Retiradas','Perdas','Controle Produção Proteínas','Etiquetas'],
    'VISUALIZAÇÃO':['Dashboard','CMV & BI','Relatórios']
}

def _password_hash(password,salt_hex=None):
    if not isinstance(password,str) or len(password)<8:
        raise ValueError('A senha deve ter pelo menos 8 caracteres.')
    salt=bytes.fromhex(salt_hex) if salt_hex else secrets.token_bytes(16)
    digest=hashlib.scrypt(password.encode('utf-8'),salt=salt,n=2**14,r=8,p=1,dklen=32)
    return digest.hex(),salt.hex()

def _normalize_username(username):
    u=str(username or '').strip().lower()
    if not re.fullmatch(r'[a-z0-9._-]{3,50}',u):
        raise ValueError('Usuário deve ter 3 a 50 caracteres: letras minúsculas, números, ponto, hífen ou _.')
    return u

def user_count():
    c=db();n=int(c.execute("select count(*) n from app_users").fetchone()['n'] or 0);c.close();return n

def create_user(username,full_name,password,role='OPERADOR',email='',modules=None,must_change=False):
    username=_normalize_username(username)
    full_name=str(full_name or '').strip()
    if not full_name:raise ValueError('Informe o nome completo.')
    role=str(role or 'OPERADOR').upper()
    if role not in ROLE_DEFAULT_MODULES:raise ValueError('Perfil inválido.')
    ph,salt=_password_hash(password)
    chosen=list(modules) if modules is not None else list(ROLE_DEFAULT_MODULES[role])
    if role=='ADMIN':chosen=list(ALL_MODULES)
    now=datetime.now().isoformat(timespec='seconds')
    c=db()
    try:
        c.execute('BEGIN IMMEDIATE')
        c.execute("""insert into app_users(username,full_name,email,role,password_hash,password_salt,
                     active,allowed_modules,must_change_password,created_at,updated_at)
                     values(?,?,?,?,?,?,1,?,?,?,?)""",
                  (username,full_name,str(email or '').strip(),role,ph,salt,
                   json.dumps(chosen,ensure_ascii=False),1 if must_change else 0,now,now))
        c.commit()
    except sqlite3.IntegrityError:
        c.rollback();raise ValueError('Já existe um usuário com esse login.')
    finally:c.close()
    return True

def _user_row(username):
    c=db();r=c.execute("select * from app_users where username=?",(_normalize_username(username),)).fetchone();c.close()
    return r

def authenticate_user(username,password):
    try:u=_normalize_username(username)
    except Exception:return None,'Usuário ou senha inválidos.'
    c=db();r=c.execute("select * from app_users where username=?",(u,)).fetchone()
    if not r:
        c.close();return None,'Usuário ou senha inválidos.'
    if not int(r['active'] or 0):
        c.close();return None,'Usuário desativado.'
    locked=str(r['locked_until'] or '')
    if locked:
        try:
            until=datetime.fromisoformat(locked)
            if until>datetime.now():
                c.close();return None,f'Usuário temporariamente bloqueado até {until.strftime("%d/%m/%Y %H:%M")}.'
        except Exception:pass
    try:
        ph,_salt=_password_hash(str(password or ''),str(r['password_salt']))
    except Exception:
        ph=''
    if not hmac.compare_digest(ph,str(r['password_hash'] or '')):
        fails=int(r['failed_attempts'] or 0)+1
        lock_until=''
        if fails>=5:
            lock_until=(datetime.now()+timedelta(minutes=10)).isoformat(timespec='seconds')
            fails=0
        c.execute("update app_users set failed_attempts=?,locked_until=?,updated_at=? where id=?",
                  (fails,lock_until,datetime.now().isoformat(timespec='seconds'),int(r['id'])))
        c.commit();c.close()
        return None,'Usuário ou senha inválidos.'
    c.execute("""update app_users set failed_attempts=0,locked_until='',last_login=?,updated_at=?
                 where id=?""",(datetime.now().isoformat(timespec='seconds'),
                                datetime.now().isoformat(timespec='seconds'),int(r['id'])))
    c.commit()
    modules=[]
    try:modules=json.loads(r['allowed_modules'] or '[]')
    except Exception:modules=[]
    if not modules:modules=list(ROLE_DEFAULT_MODULES.get(str(r['role']).upper(),[]))
    user={'id':int(r['id']),'username':r['username'],'full_name':r['full_name'],'email':r['email'],
          'role':str(r['role']).upper(),'modules':modules,
          'must_change_password':bool(int(r['must_change_password'] or 0))}
    c.close()
    return user,''

def current_user():
    return st.session_state.get('_auth_user')

def user_allowed_modules(user=None):
    user=user or current_user() or {}
    if str(user.get('role','')).upper()=='ADMIN':return list(ALL_MODULES)
    mods=user.get('modules') or ROLE_DEFAULT_MODULES.get(str(user.get('role','')).upper(),[])
    return [m for m in ALL_MODULES if m in mods and m!='Usuários & Acessos']

def update_user_record(user_id,full_name,email,role,active,modules):
    role=str(role or 'OPERADOR').upper()
    if role not in ROLE_DEFAULT_MODULES:raise ValueError('Perfil inválido.')
    chosen=list(ALL_MODULES) if role=='ADMIN' else [m for m in modules if m in ALL_MODULES and m!='Usuários & Acessos']
    c=db()
    current=c.execute("select role,active from app_users where id=?",(int(user_id),)).fetchone()
    if not current:
        c.close();raise ValueError('Usuário não encontrado.')
    if str(current['role']).upper()=='ADMIN' and int(current['active'] or 0)==1 and (role!='ADMIN' or not bool(active)):
        admins=int(c.execute("select count(*) n from app_users where upper(role)='ADMIN' and active=1").fetchone()['n'] or 0)
        if admins<=1:
            c.close();raise ValueError('Não é possível remover/desativar o último administrador ativo.')
    c.execute("""update app_users set full_name=?,email=?,role=?,active=?,allowed_modules=?,updated_at=?
                 where id=?""",(str(full_name or '').strip(),str(email or '').strip(),role,int(bool(active)),
                               json.dumps(chosen,ensure_ascii=False),datetime.now().isoformat(timespec='seconds'),int(user_id)))
    c.commit();c.close()

def reset_user_password(user_id,new_password,must_change=True):
    ph,salt=_password_hash(new_password)
    c=db();c.execute("""update app_users set password_hash=?,password_salt=?,must_change_password=?,
                        failed_attempts=0,locked_until='',updated_at=? where id=?""",
                     (ph,salt,1 if must_change else 0,datetime.now().isoformat(timespec='seconds'),int(user_id)))
    c.commit();c.close()

def change_own_password(user_id,current_password,new_password):
    c=db();r=c.execute("select username from app_users where id=?",(int(user_id),)).fetchone();c.close()
    if not r:raise ValueError('Usuário não encontrado.')
    user,msg=authenticate_user(r['username'],current_password)
    if not user:raise ValueError(msg or 'Senha atual inválida.')
    ph,salt=_password_hash(new_password)
    c=db();c.execute("""update app_users set password_hash=?,password_salt=?,must_change_password=0,
                        updated_at=? where id=?""",
                     (ph,salt,datetime.now().isoformat(timespec='seconds'),int(user_id)))
    c.commit();c.close()


# V11.5.2 — banco real carregado no projeto para inicialização no Streamlit Cloud.
# Atenção: o filesystem do Community Cloud não deve ser tratado como banco persistente definitivo.
st.set_page_config(page_title='HNT FoodService BI V11.5.2 — SEFAZ FIX + Banco Real',layout='wide')

st.markdown("""
<style>
[data-testid="stStatusWidget"],
[data-testid="stAppRunningMan"],
[data-testid="stAppRunningManContainer"],
[data-testid="stSpinner"] {
    display: none !important;
    visibility: hidden !important;
}
</style>
""", unsafe_allow_html=True)
st.markdown('''
<style>
:root { --hnt:#1f2937; --accent:#84a51d; --soft:#f6f8fb; }
.block-container{padding-top:1.2rem;padding-bottom:3rem;max-width:1550px}
[data-testid="stSidebar"]{background:#111827}
[data-testid="stSidebar"] *{color:#f9fafb}
h1,h2,h3{letter-spacing:-0.02em}
div[data-testid="stMetric"]{background:white;border:1px solid #e5e7eb;border-radius:14px;padding:12px 14px;box-shadow:0 2px 8px rgba(0,0,0,.04)}
.stButton>button{border-radius:9px;font-weight:600}
.stDownloadButton>button{border-radius:9px;font-weight:600}
div[data-testid="stExpander"]{border-radius:12px;border-color:#e5e7eb}
[data-testid="stDataFrame"]{border-radius:12px;overflow:hidden;border:1px solid #e5e7eb}
[data-testid="stStatusWidget"]{display:none!important}
[data-testid="stToolbar"]{opacity:.18}
[data-testid="stDecoration"]{display:none!important}

</style>
''',unsafe_allow_html=True)

# ==============================================================
# V11.5 - LOGIN INTERNO / USUÁRIOS / PERMISSÕES
# ==============================================================
if user_count()==0:
    st.title('Primeiro acesso — criar Administrador')
    st.info('Nenhum usuário existe ainda. Crie o administrador inicial. A senha é armazenada somente como hash criptográfico.')
    with st.form('first_admin_form'):
        a1,a2=st.columns(2)
        username=a1.text_input('Login do administrador',value='admin')
        full_name=a2.text_input('Nome completo')
        email=st.text_input('E-mail (opcional)')
        p1=st.text_input('Senha',type='password')
        p2=st.text_input('Confirmar senha',type='password')
        submitted=st.form_submit_button('CRIAR ADMINISTRADOR',type='primary')
    if submitted:
        try:
            if p1!=p2:raise ValueError('As senhas não conferem.')
            create_user(username,full_name,p1,'ADMIN',email,ALL_MODULES,False)
            set_flash('Administrador criado. Faça login.','success')
            st.rerun()
        except Exception as ex:st.error(str(ex))
    st.stop()

auth=current_user()
if not auth:
    st.title('HNT FoodService BI — Acesso')
    with st.form('login_form'):
        lu=st.text_input('Usuário')
        lp=st.text_input('Senha',type='password')
        login_btn=st.form_submit_button('ENTRAR',type='primary')
    if login_btn:
        user,msg=authenticate_user(lu,lp)
        if user:
            st.session_state['_auth_user']=user
            st.session_state['_auth_at']=datetime.now().isoformat(timespec='seconds')
            app_log('Segurança','Login',user['username'])
            st.rerun()
        else:
            st.error(msg or 'Usuário ou senha inválidos.')
    st.stop()

# expiração simples da sessão após 12 horas
try:
    auth_at=datetime.fromisoformat(st.session_state.get('_auth_at',''))
    if datetime.now()-auth_at>timedelta(hours=12):
        st.session_state.pop('_auth_user',None);st.session_state.pop('_auth_at',None)
        st.warning('Sessão expirada. Entre novamente.')
        st.rerun()
except Exception:pass

auth=current_user()
if auth and auth.get('must_change_password'):
    st.title('Alteração obrigatória de senha')
    with st.form('must_change_password_form'):
        oldp=st.text_input('Senha atual',type='password')
        newp=st.text_input('Nova senha',type='password')
        newp2=st.text_input('Confirmar nova senha',type='password')
        ch=st.form_submit_button('ALTERAR SENHA',type='primary')
    if ch:
        try:
            if newp!=newp2:raise ValueError('As novas senhas não conferem.')
            change_own_password(auth['id'],oldp,newp)
            user,_=authenticate_user(auth['username'],newp)
            st.session_state['_auth_user']=user
            set_flash('Senha alterada.','success');st.rerun()
        except Exception as ex:st.error(str(ex))
    st.stop()

st.sidebar.title('HNT FoodService BI V11.5')
st.sidebar.caption('Rápido • Usuários • Entrada fiscal • Estoque • CMV • SEFAZ')
st.sidebar.markdown(f"**{auth.get('full_name')}**  \\n{auth.get('role')}")
if st.sidebar.button('SAIR',key='logout_v115'):
    app_log('Segurança','Logout',auth.get('username',''))
    st.session_state.clear()
    st.rerun()

if st.session_state.get('_goto_page'):
    target=st.session_state.pop('_goto_page')
    if target in user_allowed_modules(auth):
        st.session_state['main_page']=target

allowed_pages=user_allowed_modules(auth)
if not allowed_pages:
    st.error('Este usuário não possui módulos liberados. Procure o administrador.')
    st.stop()
if st.session_state.get('main_page') not in allowed_pages:
    st.session_state['main_page']=allowed_pages[0]
page=st.sidebar.radio('Módulo',allowed_pages,key='main_page')
render_flash()

if page=='Dashboard':
    st.title('Dashboard Executivo');c=db();counts=[c.execute('select count(*) n from products where active=1').fetchone()['n'],c.execute('select count(*) n from suppliers where active=1').fetchone()['n'],c.execute('select count(*) n from invoices').fetchone()['n'],c.execute("select count(*) n from invoices where status='PENDENTE'").fetchone()['n']];c.close();cols=st.columns(4)

    st.caption(f'Banco em uso: {DB}')
    if Path(DB).name=='hnt_foodservice_v3.db' and Path(DB).exists():
        st.caption('Base: Banco real inicial V11.5.2 carregado no ambiente atual.')
    if V1151_BACKUP_WARNING:st.warning(f'Falha ao criar backup V11.5.1: {V1151_BACKUP_WARNING}')
    if V115_BACKUP_WARNING:st.warning(f'Falha ao criar backup V11.5: {V115_BACKUP_WARNING}')
    if V114_BACKUP_WARNING:st.warning(f'Falha ao criar backup V11.4: {V114_BACKUP_WARNING}')
    if V113_BACKUP_WARNING:st.warning(f'Falha ao criar backup V11.3: {V113_BACKUP_WARNING}')
    if V112_BACKUP_WARNING:st.warning(f'Falha ao criar backup V11.2: {V112_BACKUP_WARNING}')
    with st.expander('🔎 Diagnóstico de Compras',expanded=False):
        _c=db()
        _d=pd.read_sql_query("""select i.id ID,i.number NF,i.issue_date Emissão,s.legal_name Fornecedor,
            i.total 'Total NF',i.status Status,
            coalesce((select sum(ii.xml_total) from invoice_items ii where ii.invoice_id=i.id),0) 'Itens Compra'
            from invoices i left join suppliers s on s.id=i.supplier_id
            order by i.id desc limit 30""",_c)
        _c.close()
        st.caption('Somente notas com Status = ENTRADA entram no valor de Compras do Dashboard.')
        st.dataframe(_d,use_container_width=True,height=280,hide_index=True)

    for col,l,v in zip(cols,['Produtos','Fornecedores','Notas','Pendentes'],counts):col.metric(l,v)
    a=date.today().replace(day=1);s,p,l=period_stats(a,date.today());x=st.columns(4);x[0].metric('Venda mês',f'R$ {s:,.2f}');x[1].metric('Compras mês',f'R$ {p:,.2f}');x[2].metric('CMV Compras',f'{p/s*100:.2f}%' if s else '-');x[3].metric('Perdas',f'{l/s*100:.2f}%' if s else '-')

elif page=='Relatórios':
    st.title('Relatórios Gerenciais')
    tabs=st.tabs(['Grande consumo','Grande valor agregado','Fornecedores mais em conta','Variação de custos','Ranking por categoria','Ranking de compras','Pareto','Perdas por causa'])
    c=db()
    with tabs[0]:
        d=pd.read_sql_query("select p.code Código,p.name Produto,p.category Categoria,sum(-m.qty) Consumo,sum((-m.qty)*m.unit_cost) Valor from movements m join products p on p.id=m.product_id where m.type in ('WITHDRAWAL','LOSS') group by p.id order by Consumo desc",c);st.dataframe(d,use_container_width=True);export_buttons(d,'RELATORIO_GRANDE_CONSUMO','r1')
    with tabs[1]:
        d=pd.read_sql_query("select p.code Código,p.name Produto,p.category Categoria,max(m.unit_cost) 'Maior Custo',avg(m.unit_cost) 'Custo Médio' from movements m join products p on p.id=m.product_id where m.type='ENTRY' and m.unit_cost>0 group by p.id order by 'Maior Custo' desc",c);st.dataframe(d,use_container_width=True);export_buttons(d,'RELATORIO_GRANDE_VALOR','r2')
    with tabs[2]:
        d=pd.read_sql_query("select p.name Produto,s.legal_name Fornecedor,sum(ii.xml_total)/nullif(sum(ii.converted_qty),0) 'Custo Médio Convertido',sum(ii.xml_total) 'Valor Comprado',count(distinct i.id) Compras from invoice_items ii join invoices i on i.id=ii.invoice_id join products p on p.id=ii.product_id join suppliers s on s.id=i.supplier_id where i.status='ENTRADA' and ii.converted_qty>0 group by p.id,s.id order by p.name,'Custo Médio Convertido'",c);st.dataframe(d,use_container_width=True);export_buttons(d,'FORNECEDORES_MAIS_EM_CONTA','r3')
    with tabs[3]:
        d=pd.read_sql_query("select p.code Código,p.name Produto,min(m.unit_cost) 'Menor Custo',max(m.unit_cost) 'Maior Custo',case when min(m.unit_cost)>0 then (max(m.unit_cost)-min(m.unit_cost))*100.0/min(m.unit_cost) else 0 end 'Variação %' from movements m join products p on p.id=m.product_id where m.type='ENTRY' and m.unit_cost>0 group by p.id order by 'Variação %' desc",c);st.dataframe(d,use_container_width=True);export_buttons(d,'VARIACAO_CUSTOS','r4')
    with tabs[4]:
        d=pd.read_sql_query("select p.category Categoria,p.name Produto,sum(ii.xml_total) Compras from invoice_items ii join invoices i on i.id=ii.invoice_id join products p on p.id=ii.product_id where i.status='ENTRADA' group by p.id order by p.category,Compras desc",c);st.dataframe(d,use_container_width=True);export_buttons(d,'RANKING_CATEGORIA','r5')
    with tabs[5]:
        d=pd.read_sql_query("select p.code Código,p.name Produto,p.category Categoria,sum(ii.xml_total) Compras from invoice_items ii join invoices i on i.id=ii.invoice_id join products p on p.id=ii.product_id where i.status='ENTRADA' group by p.id order by Compras desc",c);st.dataframe(d,use_container_width=True);export_buttons(d,'RANKING_COMPRAS','r6')
    with tabs[6]:
        d=pd.read_sql_query("select p.code Código,p.name Produto,p.category Categoria,sum(ii.xml_total) Compras from invoice_items ii join invoices i on i.id=ii.invoice_id join products p on p.id=ii.product_id where i.status='ENTRADA' group by p.id order by Compras desc",c)
        if not d.empty:
            d['Representatividade %']=d.Compras/d.Compras.sum()*100;d['Pareto %']=d['Representatividade %'].cumsum()
        st.dataframe(d,use_container_width=True);export_buttons(d,'PARETO_COMPRAS','r7')
    with tabs[7]:
        d=pd.read_sql_query("select l.cause Causa,p.category Categoria,sum(l.qty) Quantidade,sum(l.qty*l.unit_cost) Valor from losses l join products p on p.id=l.product_id group by l.cause,p.category order by Valor desc",c);st.dataframe(d,use_container_width=True);export_buttons(d,'PERDAS_POR_CAUSA','r8')
    c.close()

elif page=='Produtos':
    st.title('Cadastro Mestre de Produtos')
    standard_template_button('Produtos','prod_tpl');st.info(f'{len(CATALOG)} itens pré-cadastrados e cadastro ilimitado.');q=st.text_input('🔎 Busca instantânea');d=products(q);st.dataframe(d.drop(columns=['id']),use_container_width=True,height=380);export_buttons(d.drop(columns=['id']),'PRODUTOS','prod_export');t1,t2,t3=st.tabs(['Cadastrar / editar','Importar Excel','Barcodes'])
    with t1:
        pid=pick_product('editprod','Editar produto existente')
        if pid:
            c=db();r=c.execute('select * from products where id=?',(pid,)).fetchone();c.close();name=st.text_input('Nome',r['name']);brand=st.text_input('Marca',r['brand'] or '');cat=st.text_input('Categoria',r['category']);sub=st.text_input('Subcategoria',r['subcategory']);unit=st.text_input('Unidade',r['unit']);obs=st.text_area('Observações',r['notes'] or '')
            if st.button('Salvar edição'):c=db();c.execute('update products set name=?,brand=?,category=?,subcategory=?,unit=?,notes=? where id=?',(name,brand,cat,sub,unit,obs,pid));c.commit();c.close();st.rerun()
        st.divider();name=st.text_input('Novo produto');brand_new=st.text_input('Marca do novo produto');cat=st.text_input('Nova categoria');sub=st.text_input('Nova subcategoria');unit=st.selectbox('Unidade estoque',['UN','KG','G','L','ML','CX','PCT']);bc=st.text_input('Barcode adicional')
        if st.button('Criar produto') and name:
            c=db();code=c.execute('select coalesce(max(code),100000)+1 x from products').fetchone()['x'];ib=ean13(code);pid=c.execute('insert into products(code,internal_barcode,name,brand,category,subcategory,unit) values(?,?,?,?,?,?,?)',(code,ib,name,brand_new,cat,sub,unit)).lastrowid;c.execute('insert into product_barcodes(product_id,barcode,description) values(?,?,?)',(pid,ib,'Interno'));
            if bc:c.execute('insert or ignore into product_barcodes(product_id,barcode,description) values(?,?,?)',(pid,bc,'Fornecedor'))
            c.commit();c.close();st.rerun()
    with t2:
        template('MODELO_CADASTRO_PRODUTOS.xlsx');up=st.file_uploader('Importar XLS/XLSX',type=['xls','xlsx'])
        if up and st.button('Processar cadastro'):
            z=pd.read_excel(up);c=db();n=0
            for _,r in z.iterrows():
                name=str(r.get('Nome','')).strip();
                if not name or name=='nan':continue
                code=None if pd.isna(r.get('Código')) else int(r.get('Código'));pr=c.execute('select id from products where code=?',(code,)).fetchone() if code else None
                if pr:pid=pr['id']
                else:
                    if not code:code=c.execute('select coalesce(max(code),100000)+1 x from products').fetchone()['x']
                    ib=ean13(code);pid=c.execute('insert into products(code,internal_barcode,name,brand,category,subcategory,unit,notes) values(?,?,?,?,?,?,?,?)',(code,ib,name,str(r.get('Marca','') if not pd.isna(r.get('Marca')) else ''),str(r.get('Categoria','')),str(r.get('Subcategoria','')),str(r.get('Unidade Estoque','UN')),str(r.get('Observações','')))).lastrowid;c.execute('insert or ignore into product_barcodes(product_id,barcode,description) values(?,?,?)',(pid,ib,'Interno'))
                b=r.get('Código Barras');
                if not pd.isna(b) and str(b).strip():c.execute('insert or ignore into product_barcodes(product_id,barcode,description) values(?,?,?)',(pid,str(b).strip(),str(r.get('Descrição Barcode',''))));n+=1
            c.commit();c.close();confirm_success(f'{n} linhas processadas.');st.rerun()
        buf=io.BytesIO();products('').drop(columns=['id']).to_excel(buf,index=False);st.download_button('Exportar cadastro',buf.getvalue(),'CADASTRO_PRODUTOS.xlsx');export_buttons(products('').drop(columns=['id']),'CADASTRO_PRODUTOS','prodexp')
    with t3:
        pid=pick_product('bar');
        if pid:
            c=db();bars=pd.read_sql_query('select id,barcode,description from product_barcodes where product_id=?',c,params=[pid]);c.close();st.dataframe(bars,use_container_width=True);b=st.text_input('Novo barcode');desc=st.text_input('Descrição do barcode','Fornecedor / embalagem')
            if st.button('Adicionar barcode') and b:c=db();c.execute('insert or ignore into product_barcodes(product_id,barcode,description) values(?,?,?)',(pid,b,desc));c.commit();c.close();st.rerun()

elif page=='Fornecedores':
    st.title('Fornecedores e Associações de Tabelas')
    standard_template_button('Fornecedores','sup_tpl')
    tabs=st.tabs(['Cadastro de Fornecedores','Tabela do Fornecedor','Associações'])

    with tabs[0]:
        with st.expander('Cadastrar novo fornecedor',expanded=True):
            nc=st.text_input('CNPJ novo',key='new_cnpj');nn=st.text_input('Razão social nova',key='new_sup_name')
            nf=st.text_input('Fantasia nova',key='new_sup_trade');nie=st.text_input('IE nova',key='new_sup_ie')
            if st.button('Cadastrar fornecedor',key='new_sup_btn') and nc and nn:
                c=db();c.execute('insert or ignore into suppliers(cnpj,legal_name,trade_name,ie,address) values(?,?,?,?,?)',(nc,nn,nf,nie,''));c.commit();c.close();app_log('Fornecedores','Cadastro',nn);st.rerun()
        q=st.text_input('🔎 CNPJ, razão social ou fantasia',key='sup_search');c=db();sql='select * from suppliers where active=1';args=[]
        if q:sql+=' and (cnpj like ? or legal_name like ? or trade_name like ?)';args=['%'+q+'%']*3
        d=pd.read_sql_query(sql+' order by legal_name',c,params=args);c.close()
        st.dataframe(d,use_container_width=True,height=320);export_buttons(d,'CADASTRO_FORNECEDORES','supexp')
        if not d.empty:
            sid=st.selectbox('Editar fornecedor',d.id.tolist(),key='sup_edit',
                format_func=lambda x:d.loc[d.id==x,'legal_name'].iloc[0])
            r=d[d.id==sid].iloc[0]
            name=st.text_input('Razão social',r.legal_name,key='sup_name_edit');trade=st.text_input('Fantasia',r.trade_name or '',key='sup_trade_edit')
            ie=st.text_input('IE',r.ie or '',key='sup_ie_edit');addr=st.text_input('Endereço',r.address or '',key='sup_addr_edit')
            phone=st.text_input('Telefone',r.phone or '',key='sup_phone_edit');email=st.text_input('E-mail',r.email or '',key='sup_email_edit')
            c1,c2=st.columns(2)
            if c1.button('SALVAR FORNECEDOR'):
                c=db();c.execute('update suppliers set legal_name=?,trade_name=?,ie=?,address=?,phone=?,email=? where id=?',(name,trade,ie,addr,phone,email,sid));c.commit();c.close();st.rerun()
            if c2.button('DESATIVAR FORNECEDOR'):
                c=db();c.execute('update suppliers set active=0 where id=?',(sid,));c.commit();c.close();st.rerun()

    with tabs[1]:
        c=db();sups=pd.read_sql_query("select id,cnpj,legal_name from suppliers where active=1 order by legal_name",c);c.close()
        if sups.empty:
            st.warning('Cadastre um fornecedor primeiro.')
        else:
            sid=st.selectbox('Fornecedor da tabela',sups.id.tolist(),key='supplier_table_sid',
                format_func=lambda x:f"{sups.loc[sups.id==x,'legal_name'].iloc[0]} | {sups.loc[sups.id==x,'cnpj'].iloc[0]}")
            st.info('Envie a tabela do fornecedor. O sistema guarda Código/SKU, descrição, GTIN/barcode, unidade e preço, e permite associar ao seu cadastro mestre.')
            up=st.file_uploader('Tabela XLS/XLSX do fornecedor',type=['xls','xlsx'],key='supplier_table_upload')
            if up and st.button('IMPORTAR TABELA DO FORNECEDOR'):
                try:
                    n,errs=import_supplier_table(up,sid);confirm_success(f'{n} itens importados/atualizados.')
                    if errs:st.warning('\n'.join(errs[:30]))
                    st.rerun()
                except Exception as ex:st.error(str(ex))

            with st.expander('➕ Cadastrar item do fornecedor manualmente'):
                a,b=st.columns(2);scode=a.text_input('Código/SKU fornecedor',key='fsi_code');sdesc=b.text_input('Descrição',key='fsi_desc')
                a,b,c1=st.columns(3);sbar=a.text_input('GTIN/Barcode fornecedor',key='fsi_bar');sunit=b.text_input('Unidade',key='fsi_unit');sprice=c1.number_input('Preço do fornecedor',min_value=0.0,format=num_format(),key='fsi_price')
                pid=pick_product('fsi_product','Associar agora a produto existente (opcional)')
                if st.button('CADASTRAR ITEM DO FORNECEDOR'):
                    if not sdesc:st.error('Informe a descrição.')
                    else:
                        upsert_supplier_item(sid,scode,sdesc,sbar,sunit,1,sprice,pid)
                        confirm_success('Item cadastrado e associação salva.' if pid else 'Item cadastrado para associação posterior.');st.rerun()

            c=db()
            it=pd.read_sql_query("""select sci.id,sci.supplier_code Código,sci.description Descrição,sci.barcode Barcode,sci.unit Unidade,
                sci.supplier_price Preço,p.code 'Código Produto',p.name 'Produto Associado'
                from supplier_catalog_items sci left join products p on p.id=sci.product_id
                where sci.supplier_id=? and sci.active=1 order by sci.description""",c,params=[sid])
            c.close()
            st.dataframe(it,use_container_width=True,height=380)
            export_buttons(it,'TABELA_FORNECEDOR','sup_table_exp')

    with tabs[2]:
        c=db();sups=pd.read_sql_query("select id,cnpj,legal_name from suppliers where active=1 order by legal_name",c);c.close()
        if not sups.empty:
            sid=st.selectbox('Fornecedor',sups.id.tolist(),key='assoc_sid',
                format_func=lambda x:sups.loc[sups.id==x,'legal_name'].iloc[0])
            c=db()
            pend=pd.read_sql_query("""select id,supplier_code Código,description Descrição,barcode Barcode,unit Unidade,
                supplier_price Preço,product_id from supplier_catalog_items
                where supplier_id=? and active=1 order by (product_id is not null),description""",c,params=[sid])
            c.close()
            if pend.empty:st.info('Nenhum item cadastrado para este fornecedor.')
            else:
                iid=st.selectbox('Item da tabela',pend.id.tolist(),key='assoc_item_id',
                    format_func=lambda x:f"{pend.loc[pend.id==x,'Código'].iloc[0]} | {pend.loc[pend.id==x,'Descrição'].iloc[0]}")
                row=pend[pend.id==iid].iloc[0]
                st.write(f"**Fornecedor:** {row['Descrição']}  |  **Barcode:** {row['Barcode'] or '-'}  |  **Preço:** {brl(row['Preço'])}")
                pid=pick_product('assoc_existing','Associar a produto cadastrado')
                mult=st.number_input('Fator de multiplicação',min_value=0.000001,value=1.0,key='assoc_mult')
                conv=st.number_input('Fator de conversão',min_value=0.000001,value=1.0,key='assoc_conv')
                c1,c2=st.columns(2)
                if c1.button('SALVAR ASSOCIAÇÃO') and pid:
                    upsert_supplier_item(sid,row['Código'],row['Descrição'],row['Barcode'],row['Unidade'],1,row['Preço'],pid,mult,conv)
                    confirm_success('Associação gravada e reutilizável nas próximas NF-e/tabelas.');st.rerun()

                with st.expander('Produto não existe? CADASTRAR E ASSOCIAR AGORA'):
                    np=st.text_input('Nome do produto',value=str(row['Descrição']),key='assoc_np_name')
                    nb=st.text_input('Marca',key='assoc_np_brand')
                    nc=st.text_input('Categoria',key='assoc_np_cat')
                    ns=st.text_input('Subcategoria',key='assoc_np_sub')
                    nu=st.selectbox('Unidade estoque',['UN','KG','G','L','ML','CX','PCT'],key='assoc_np_unit')
                    if st.button('CRIAR PRODUTO + ASSOCIAR') and np and nc:
                        c=db();code=c.execute('select coalesce(max(code),100000)+1 x from products').fetchone()['x'];ib=ean13(code)
                        newpid=c.execute('insert into products(code,internal_barcode,name,brand,category,subcategory,unit) values(?,?,?,?,?,?,?)',(code,ib,np,nb,nc,ns,nu)).lastrowid
                        c.execute('insert or ignore into product_barcodes(product_id,barcode,description) values(?,?,?)',(newpid,ib,'Código interno'))
                        if row['Barcode']:c.execute('insert or ignore into product_barcodes(product_id,barcode,description) values(?,?,?)',(newpid,str(row['Barcode']),'Fornecedor'))
                        c.commit();c.close()
                        upsert_supplier_item(sid,row['Código'],row['Descrição'],row['Barcode'],row['Unidade'],1,row['Preço'],newpid,mult,conv)
                        confirm_success(f'Produto {code} criado e associado.');st.rerun()

elif page=='Notas / XML':
    st.title('Entrada de Notas Fiscais – XML NF-e')
    _focus_nf=st.session_state.get('_focus_invoice_editor')
    if _focus_nf:
        _fc=db();_fr=_fc.execute("""select i.number,s.legal_name from invoices i
            left join suppliers s on s.id=i.supplier_id where i.id=?""",(int(_focus_nf),)).fetchone();_fc.close()
        if _fr:
            st.success(f'🎯 Edição direta: NF {_fr["number"]} | {_fr["legal_name"] or ""} já está selecionada abaixo para alteração.')
        st.session_state.pop('_focus_invoice_editor',None)
    st.caption('Fluxo simples: importe o XML, associe os produtos na própria tabela e clique GRAVAR E DAR ENTRADA.')
    st.info('Regra: notas e itens podem ser corrigidos ou excluídos a qualquer momento. Se a NF já entrou no estoque, reabra a nota para que o sistema estorne a entrada antes da edição.')
    tab_xml,tab_manual=st.tabs(['Importar XML NF-e','Criar Nota Manual'])

    with tab_xml:
        st.subheader('Importar XML da NF-e')
        st.info('A entrada fiscal é feita pelo XML da NF-e. Não existe planilha XLSX padrão para importar nota fiscal.')
        uploads=st.file_uploader(
            'Selecione um ou vários arquivos XML de NF-e',
            type=['xml'],
            accept_multiple_files=True,
            key='xml_nf_multi'
        )

        if uploads:
            previews=[]
            valid_files=[]
            for up in uploads:
                try:
                    raw=up.getvalue()
                    sup,inv,items=parse_nfe(raw)
                    previews.append({
                        'Arquivo':up.name,
                        'NF':inv['number'],
                        'Série':inv['series'],
                        'Emissão':inv['issue_date'],
                        'Fornecedor':sup['name'],
                        'CNPJ':sup['cnpj'],
                        'Itens':len(items),
                        'Valor':inv['total'],
                        'Situação':'OK'
                    })
                    valid_files.append((up.name,raw))
                except Exception as ex:
                    previews.append({
                        'Arquivo':up.name,'NF':'','Série':'','Emissão':'',
                        'Fornecedor':'','CNPJ':'','Itens':0,'Valor':0,
                        'Situação':f'ERRO: {ex}'
                    })

            pv=pd.DataFrame(previews)
            st.dataframe(
                pv,
                use_container_width=True,
                hide_index=True,
                column_config={
                    'Valor':st.column_config.NumberColumn('Valor NF',format='R$ %.2f'),
                    'Itens':st.column_config.NumberColumn('Itens',format='%d')
                }
            )

            if st.button('IMPORTAR XML(S) PARA O SISTEMA',type='primary',key='btn_xml_nf_multi'):
                imported=0
                existing=0
                errors=[]
                last_id=None
                for filename,raw in valid_files:
                    try:
                        iid,created,msg=import_nfe(raw,'XML')
                        last_id=iid
                        if created:
                            imported+=1
                        else:
                            existing+=1
                    except Exception as ex:
                        errors.append(f'{filename}: {ex}')
                if last_id:
                    st.session_state['open_invoice_id']=last_id
                if imported:
                    confirm_success(f'{imported} NF-e(s) importada(s) com sucesso.')
                if existing:
                    st.info(f'{existing} NF-e(s) já existiam e foram mantidas sem duplicação.')
                if errors:
                    st.error('\n'.join(errors))
                if imported or existing:
                    st.rerun()

        sample=ROOT/'XML_NFE_EXEMPLO_SEM_VALIDADE_FISCAL.xml'
        if sample.exists():
            st.download_button(
                'Baixar XML de teste',
                sample.read_bytes(),
                sample.name,
                mime='application/xml',
                key='xml_test'
            )

    with tab_manual:
        c=db();supdf=pd.read_sql_query("select id,cnpj,legal_name from suppliers where active=1 order by legal_name",c);c.close()
        mode=st.radio('Fornecedor',['Selecionar cadastrado','Cadastrar no ato'],horizontal=True,key='mn_mode')
        sid=None
        if mode=='Selecionar cadastrado':
            if not supdf.empty:
                sid=st.selectbox('Fornecedor',supdf.id.tolist(),key='mn_sid',
                    format_func=lambda x:f"{supdf.loc[supdf.id==x,'legal_name'].iloc[0]} | {supdf.loc[supdf.id==x,'cnpj'].iloc[0]}")
            else: st.info('Cadastre o fornecedor no ato.')
        else:
            mc=st.text_input('CNPJ/CPF',key='mn_cnpj');mn=st.text_input('Razão social / Nome',key='mn_name')
            mf=st.text_input('Fantasia',key='mn_trade');mie=st.text_input('IE',key='mn_ie')
        c1,c2,c3=st.columns(3)
        num=c1.text_input('Número da nota/documento',key='mn_num')
        ser=c2.text_input('Série',value='1',key='mn_ser')
        dt=c3.date_input('Data de emissão',date.today(),key='mn_date')
        obs=st.text_area('Observações',key='mn_obs')
        if st.button('CRIAR NOTA MANUAL',type='primary',key='mn_create'):
            try:
                c=db()
                if mode=='Cadastrar no ato':
                    if not mn: raise ValueError('Informe o fornecedor.')
                    sid=supplier(mc,mn,mf,mie,'',connection=c)
                if not sid: raise ValueError('Selecione/cadastre fornecedor.')
                if not num: raise ValueError('Informe o número.')
                iid=c.execute('''insert into invoices(access_key,number,series,issue_date,entry_date,supplier_id,total,status,notes,source)
                                 values(NULL,?,?,?,?,?,?,?,?,'MANUAL')''',
                              (num,ser,str(dt),datetime.now().isoformat(),sid,0,'PENDENTE',obs)).lastrowid
                c.commit();c.close()
                st.session_state['open_invoice_id']=iid
                app_log('Notas / XML','Nota manual criada',f'NF {num}')
                confirm_success('Nota manual criada. Adicione os itens abaixo.');st.rerun()
            except Exception as e:
                try:c.close()
                except Exception:pass
                st.error(str(e))

    st.divider()
    st.subheader('Notas cadastradas')
    c=db()
    manage=pd.read_sql_query("""select i.id,i.number NF,i.issue_date Emissão,s.legal_name Fornecedor,
        i.total Valor,i.status Status,coalesce(i.edit_status,'FECHADA') Edição,i.source Origem
        from invoices i join suppliers s on s.id=i.supplier_id order by i.id desc""",c)
    c.close()
    if not manage.empty:
        st.dataframe(manage,use_container_width=True,height=270)
        export_buttons(manage,'NOTAS_CADASTRADAS','notes_list_exp')
        action_ids=st.multiselect('Selecionar nota(s) para ação',manage.id.tolist(),
            format_func=lambda x:f"NF {manage.loc[manage.id==x,'NF'].iloc[0]} | {manage.loc[manage.id==x,'Fornecedor'].iloc[0]} | {manage.loc[manage.id==x,'Status'].iloc[0]}")
        ac1,ac2,ac3=st.columns(3)
        if ac1.button('COLOCAR EM ABERTO',disabled=not action_ids):
            for _id in action_ids: reopen_invoice(int(_id))
            confirm_success('Nota(s) aberta(s). Se já estavam lançadas, a entrada de estoque foi desfeita.');st.rerun()
        if ac2.button('FECHAR ALTERAÇÃO',disabled=not action_ids):
            for _id in action_ids: close_invoice_edit(int(_id))
            confirm_success('Nota(s) fechada(s) para edição.');st.rerun()
        confirm_del=st.checkbox('Confirmo a exclusão das notas selecionadas',key='confirm_delete_invoice')
        if ac3.button('EXCLUIR / LIBERAR REIMPORTAÇÃO',type='primary',disabled=(not action_ids or not confirm_del)):
            n=0
            for _id in action_ids:
                if delete_invoice_safe(int(_id)):n+=1
            confirm_success(f'{n} nota(s) excluída(s). Podem ser importadas novamente pelo XML/DF-e.');st.rerun()
    notes=manage.copy()
    if not notes.empty:
        default_iid=st.session_state.pop('open_invoice_id',None); options=notes.id.tolist(); default_index=options.index(default_iid) if default_iid in options else 0
        iid=st.selectbox('Abrir / editar',options,index=default_index,format_func=lambda x:f"NF {notes.loc[notes.id==x,'NF'].iloc[0]} | {notes.loc[notes.id==x,'Fornecedor'].iloc[0]}");c=db();inv=c.execute('select * from invoices where id=?',(iid,)).fetchone();c.close();can_edit=(str(inv['edit_status'] or 'FECHADA').upper()=='ABERTA' or str(inv['status']).upper()=='PENDENTE')

        c=db();_inv_ctrl=c.execute("select status,edit_status,number from invoices where id=?",(iid,)).fetchone();c.close()
        if _inv_ctrl:
            ec1,ec2,ec3=st.columns(3)
            if str(_inv_ctrl['status']).upper()=='ENTRADA':
                if ec1.button('🔓 REABRIR NOTA PARA EDITAR',key=f'reopen_nf_any_{iid}'):
                    reopen_invoice(iid);confirm_success('Entrada estornada. A nota está aberta para edição.');st.rerun()
            else:
                ec1.success('Nota aberta para edição')
            if ec2.button('🗑️ EXCLUIR NOTA COMPLETA',key=f'del_nf_any_{iid}'):
                st.session_state[f'confirm_del_nf_{iid}']=True
            if st.session_state.get(f'confirm_del_nf_{iid}',False):
                st.warning('A exclusão remove a nota e libera o mesmo XML para importação novamente.')
                if ec3.button('CONFIRMAR EXCLUSÃO DA NOTA',key=f'confirm_del_nf_btn_{iid}'):
                    delete_invoice_safe(iid);st.session_state.pop(f'confirm_del_nf_{iid}',None);confirm_success('Nota excluída.');st.rerun()
        if not can_edit: st.info('Nota fechada para edição. Use COLOCAR EM ABERTO acima para alterar.')
        num=st.text_input('Número',inv['number']);ser=st.text_input('Série',inv['series'] or '');emi=st.text_input('Emissão',inv['issue_date'] or '');vt=st.number_input('Valor total NF',value=float(inv['total'] or 0));obs=st.text_area('Observações NF',inv['notes'] or '')
        if st.button('Salvar cabeçalho',disabled=not can_edit):c=db();c.execute('update invoices set number=?,series=?,issue_date=?,total=?,notes=? where id=?',(num,ser,emi,vt,obs,iid));c.commit();c.close();st.rerun()
        if str(inv['source']).upper()=='MANUAL':
            with st.expander('➕ Adicionar item manual',expanded=True):
                a1,a2=st.columns([2,1]);mi_desc=a1.text_input('Descrição do item',key=f'midesc{iid}');mi_code=a2.text_input('Código fornecedor',key=f'micode{iid}')
                b1,b2,b3=st.columns(3);mi_unit=b1.selectbox('Unidade',['UN','KG','G','L','ML','CX','PCT','FD'],key=f'miunit{iid}');mi_qty=b2.number_input('Quantidade',min_value=0.000001,value=1.0,key=f'miqty{iid}');mi_uv=b3.number_input('Valor unitário',min_value=0.0,value=0.0,format=num_format(),key=f'miuv{iid}')
                c1,c2,c3=st.columns(3);mi_bar=c1.text_input('Barcode/GTIN',key=f'mibar{iid}');mi_ncm=c2.text_input('NCM',key=f'mincm{iid}');mi_cfop=c3.text_input('CFOP',key=f'micfop{iid}')
                mi_total=mi_qty*mi_uv;st.info(f'Valor total do item: {brl(mi_total)}')
                if st.button('ADICIONAR ITEM',key=f'miadd{iid}',disabled=not can_edit):
                    if not mi_desc: st.error('Informe a descrição.')
                    else:
                        c=db();c.execute('''insert into invoice_items(invoice_id,supplier_code,barcode,description,ncm,cfop,xml_unit,xml_qty,xml_unit_value,xml_total,product_id,multiplier,conversion,converted_qty,converted_unit_cost)
                                           values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                                         (iid,mi_code,mi_bar,mi_desc,mi_ncm,mi_cfop,mi_unit,mi_qty,mi_uv,mi_total,None,1,1,mi_qty,mi_uv))
                        newtotal=c.execute('select coalesce(sum(xml_total),0) v from invoice_items where invoice_id=?',(iid,)).fetchone()['v']
                        c.execute('update invoices set total=? where id=?',(newtotal,iid));c.commit();c.close()
                        app_log('Notas / XML','Item manual adicionado',mi_desc);st.rerun()
        # ======================================================
        # V10.5 - ENTRADA DE NF EM GRADE ÚNICA
        # ======================================================
        st.divider()
        st.subheader('Entrada da Nota — associação, quantidade e custo')

        c=db()
        raw_items=pd.read_sql_query("""select ii.id,
            ii.supplier_code 'Cód. Fornecedor',
            ii.description 'Item NF',
            ii.barcode Barcode,
            coalesce(nullif(ii.commercial_unit,''),ii.xml_unit,'') 'Un. Comercial',
            coalesce(nullif(ii.stock_unit,''),p.unit,'') 'Un. Estoque',
            ii.xml_qty 'Qtd Fiscal',
            ii.xml_total 'Valor Item',
            coalesce(ii.multiplier,1) 'Fator Mult.',
            coalesce(ii.conversion,1) 'Fator Conv.',
            ii.product_id
            from invoice_items ii
            left join products p on p.id=ii.product_id
            where ii.invoice_id=?
            order by ii.id""",c,params=[iid])
        product_count=c.execute("select count(*) n from products").fetchone()['n']
        c.close()

        if raw_items.empty:
            st.warning('Esta nota não possui itens. Reimporte o XML ou adicione os itens manualmente.')
        else:
            labels,label_to_id,id_to_label=invoice_product_options()

            raw_items['Produto Associado']=raw_items['product_id'].apply(
                lambda x:id_to_label.get(int(x),'— NÃO ASSOCIADO —') if pd.notna(x) else '— NÃO ASSOCIADO —'
            )

            st.caption(
                f'{len(raw_items)} item(ns) na NF | {product_count} produtos disponíveis para associação. '
                'Na coluna Produto Associado, clique na célula e digite para localizar o produto.'
            )

            grid_cols=[
                'id','Cód. Fornecedor','Item NF','Barcode',
                'Un. Comercial','Un. Estoque',
                'Qtd Fiscal','Valor Item','Fator Mult.','Fator Conv.',
                'Produto Associado'
            ]

            editor=st.data_editor(
                raw_items[grid_cols],
                use_container_width=True,
                hide_index=True,
                height=min(650,110+38*len(raw_items)),
                key=f'nf_grid_v104_{iid}',
                disabled=['id','Cód. Fornecedor'],
                column_config={
                    'Produto Associado':st.column_config.SelectboxColumn(
                        'Produto Associado',
                        options=labels,
                        required=False,
                        help='Clique e digite parte do código ou nome. A lista contém todo o cadastro.'
                    ),
                    'Un. Estoque':st.column_config.SelectboxColumn(
                        'Un. Estoque',
                        options=['UN','KG','G','L','ML','CX','PCT','FD','SC','BD','LT'],
                        required=False
                    ),
                    'Qtd Fiscal':st.column_config.NumberColumn(min_value=0.000001,step=0.001,format=num_format()),
                    'Valor Item':st.column_config.NumberColumn(min_value=0.0,step=0.01,format='R$ %.2f'),
                    'Fator Mult.':st.column_config.NumberColumn(min_value=0.000001,step=0.1,format=num_format()),
                    'Fator Conv.':st.column_config.NumberColumn(min_value=0.000001,step=0.1,format=num_format())
                }
            )

            # Prévia simples e visível
            preview=editor.copy()
            preview['Qtd Estoque']=preview.apply(
                lambda r:float(r['Qtd Fiscal'] or 0)*float(r['Fator Mult.'] or 1)*float(r['Fator Conv.'] or 1),
                axis=1
            )
            preview['Custo Unitário']=preview.apply(
                lambda r:float(r['Valor Item'] or 0)/float(r['Qtd Estoque'])
                if float(r['Qtd Estoque'] or 0)>0 else 0,
                axis=1
            )
            preview['Status']=preview['Produto Associado'].apply(
                lambda x:'PENDENTE' if x=='— NÃO ASSOCIADO —' else 'OK'
            )

            st.subheader('Conferência')
            st.dataframe(
                preview[['Item NF','Produto Associado','Un. Estoque','Qtd Estoque','Custo Unitário','Status']],
                use_container_width=True,
                hide_index=True,
                height=min(450,100+36*len(preview)),
                column_config={
                    'Qtd Estoque':st.column_config.NumberColumn(format=num_format()),
                    'Custo Unitário':st.column_config.NumberColumn(format='R$ '+num_format())
                }
            )

            pending_rows=preview[preview['Produto Associado']=='— NÃO ASSOCIADO —']
            bad_rows=preview[
                (pd.to_numeric(preview['Qtd Estoque'],errors='coerce').fillna(0)<=0) |
                (pd.to_numeric(preview['Custo Unitário'],errors='coerce').fillna(0)<=0)
            ]

            c1,c2=st.columns(2)

            if c1.button('💾 GRAVAR NOTA',type='secondary',disabled=not can_edit,key=f'save_nf_v104_{iid}'):
                try:
                    res=save_invoice_grid(int(iid),editor,label_to_id,True)
                    if res['pending']:
                        set_flash(
                            f"Nota gravada. Ainda faltam {len(res['pending'])} associação(ões).",
                            'warning'
                        )
                    else:
                        set_flash('Nota gravada. Todos os itens estão associados.','success')
                    st.rerun()
                except Exception as ex:
                    st.error(f'Não foi possível gravar a nota: {ex}')

            # Botão nunca fica "misteriosamente" bloqueado.
            # Ao clicar, salva a grade atual e mostra exatamente o que falta.
            if c2.button('✅ GRAVAR E DAR ENTRADA',type='primary',disabled=not can_edit,key=f'enter_nf_v104_{iid}'):
                try:
                    save_res=save_invoice_grid(int(iid),editor,label_to_id,True)

                    if save_res['pending']:
                        st.error(
                            'Não é possível dar entrada ainda. Associe estes itens: '
                            + ' | '.join(save_res['pending'][:12])
                        )
                    else:
                        # Recarrega após salvar para validar valores reais do banco.
                        check=invoice_items_view(int(iid))
                        invalid=check[
                            (pd.to_numeric(check['Qtd Estoque'],errors='coerce').fillna(0)<=0) |
                            (pd.to_numeric(check['Custo Unitário'],errors='coerce').fillna(0)<=0)
                        ]
                        if not invalid.empty:
                            st.error(
                                'Corrija quantidade/custo destes itens: '
                                + ' | '.join(invalid['Item NF'].astype(str).tolist()[:12])
                            )
                        else:
                            result=confirm_invoice_entry(int(iid))
                            if result.get('already'):
                                st.warning(result['message'])
                            else:
                                set_flash(result['message'],'success')
                                st.rerun()
                except Exception as ex:
                    st.error(f'Entrada NÃO realizada: {ex}')

            with st.expander('➕ Produto não existe? Cadastrar e usar nesta nota'):
                new_name=st.text_input('Nome do novo produto',key=f'v104_new_name_{iid}')
                n1,n2,n3=st.columns(3)
                new_brand=n1.text_input('Marca',key=f'v104_new_brand_{iid}')
                new_cat=n2.text_input('Categoria',key=f'v104_new_cat_{iid}')
                new_unit=n3.selectbox('Unidade',['UN','KG','G','L','ML','CX','PCT','FD','SC'],key=f'v104_new_unit_{iid}')
                new_sub=st.text_input('Subcategoria',key=f'v104_new_sub_{iid}')
                if st.button('CADASTRAR PRODUTO',key=f'v104_create_product_{iid}'):
                    if not new_name.strip() or not new_cat.strip():
                        st.error('Informe nome e categoria.')
                    else:
                        c=db()
                        try:
                            c.execute('BEGIN IMMEDIATE')
                            code=c.execute('select coalesce(max(code),100000)+1 x from products').fetchone()['x']
                            ib=ean13(code)
                            c.execute("""insert into products(
                                code,internal_barcode,name,brand,category,subcategory,unit,active)
                                values(?,?,?,?,?,?,?,1)""",
                                (code,ib,new_name.strip(),new_brand.strip(),new_cat.strip(),new_sub.strip(),new_unit))
                            pid=c.execute('select last_insert_rowid() id').fetchone()['id']
                            c.execute("""insert or ignore into product_barcodes(product_id,barcode,description)
                                         values(?,?,?)""",(pid,ib,'Código interno'))
                            c.commit()
                            clear_data_cache()
                            set_flash(f'Produto {code} cadastrado. Ele já aparecerá na lista de associação.','success')
                            st.rerun()
                        except Exception as ex:
                            c.rollback()
                            st.error(f'Erro ao cadastrar produto: {ex}')
                        finally:
                            c.close()

            with st.expander('🗑️ Excluir um item da nota'):
                item_del=st.selectbox(
                    'Item',
                    raw_items.id.tolist(),
                    key=f'v104_del_item_{iid}',
                    format_func=lambda x:
                        f"{raw_items.loc[raw_items.id==x,'Cód. Fornecedor'].iloc[0]} | "
                        f"{raw_items.loc[raw_items.id==x,'Item NF'].iloc[0]}"
                )
                confirm_delete=st.checkbox('Confirmo a exclusão deste item',key=f'v104_confirm_del_{iid}_{item_del}')
                if st.button('EXCLUIR ITEM',disabled=not confirm_delete,key=f'v104_delete_{iid}_{item_del}'):
                    try:
                        res=delete_invoice_item_safe(int(iid),int(item_del))
                        set_flash(res['message'],'success')
                        st.rerun()
                    except Exception as ex:
                        st.error(f'Erro ao excluir item: {ex}')

            export_buttons(
                preview.drop(columns=['id'],errors='ignore'),
                f'ENTRADA_NF_{iid}',
                f'v104_export_{iid}'
            )



elif page=='Compras Avulsas':
    st.title('Compras Avulsas')
    st.caption('Use quando você conhece o valor final da compra, mas não possui XML/itens/quantidades. Entra em Compras e CMV, mas não movimenta quantidade de estoque.')
    t1,t2=st.tabs(['Lançar / Editar','Relatório'])

    with t1:
        a,b,cx=st.columns(3)
        pdte=a.date_input('Data da compra',date.today(),key='lp_date')
        supplier_name=b.text_input('Fornecedor',key='lp_supplier')
        doc_ref=cx.text_input('Documento / referência',key='lp_ref')
        cats=sorted(products('').Categoria.dropna().astype(str).unique().tolist())
        d,e=st.columns(2)
        cat=d.selectbox('Categoria (opcional)',['']+cats,key='lp_cat')
        total=e.number_input('Valor final da compra',min_value=0.0,step=0.001,format=num_format(),key='lp_total')
        desc=st.text_input('Descrição',key='lp_desc')
        notes=st.text_area('Observações',key='lp_notes')
        if st.button('✅ GRAVAR COMPRA AVULSA',type='primary',key='lp_save'):
            if total<=0:
                st.error('Informe um valor maior que zero.')
            else:
                c=db()
                c.execute("""insert into loose_purchases(
                    purchase_date,supplier_name,document_ref,category,description,total,notes,active,created_at,updated_at)
                    values(?,?,?,?,?,?,?,1,?,?)""",
                    (str(pdte),supplier_name.strip(),doc_ref.strip(),cat,desc.strip(),
                     round_entry(total),notes.strip(),datetime.now().isoformat(timespec='seconds'),
                     datetime.now().isoformat(timespec='seconds')))
                c.commit();c.close()
                set_flash('Compra avulsa gravada e incluída no CMV de compras.','success');st.rerun()

        c=db()
        lp=pd.read_sql_query("""select id,purchase_date Data,supplier_name Fornecedor,
            document_ref Documento,category Categoria,description Descrição,total Valor,notes Observações
            from loose_purchases where active=1 order by purchase_date desc,id desc limit 300""",c)
        c.close()
        if not lp.empty:
            st.dataframe(lp,use_container_width=True,height=330,hide_index=True,
                column_config={'Valor':st.column_config.NumberColumn(format='R$ '+num_format())})
            rid=st.selectbox('Alterar / excluir',lp.id.tolist(),key='lp_edit_id',
                format_func=lambda x:f"{lp.loc[lp.id==x,'Data'].iloc[0]} | {lp.loc[lp.id==x,'Fornecedor'].iloc[0]} | {brl(lp.loc[lp.id==x,'Valor'].iloc[0])}")
            rr=lp[lp.id==rid].iloc[0]
            ee1,ee2=st.columns(2)
            new_total=ee1.number_input('Novo valor',min_value=0.0,value=float(rr['Valor'] or 0),step=0.001,format=num_format(),key='lp_edit_total')
            new_desc=ee2.text_input('Nova descrição',value=str(rr['Descrição'] or ''),key='lp_edit_desc')
            b1,b2=st.columns(2)
            if b1.button('SALVAR ALTERAÇÃO',key='lp_update'):
                c=db();c.execute("""update loose_purchases set total=?,description=?,updated_at=? where id=?""",
                    (round_entry(new_total),new_desc,datetime.now().isoformat(timespec='seconds'),int(rid)))
                c.commit();c.close();set_flash('Compra avulsa alterada.','success');st.rerun()
            if b2.button('EXCLUIR COMPRA',key='lp_delete'):
                c=db();c.execute("update loose_purchases set active=0,updated_at=? where id=?",
                    (datetime.now().isoformat(timespec='seconds'),int(rid)));c.commit();c.close()
                set_flash('Compra avulsa excluída do cálculo de compras/CMV.','success');st.rerun()

    with t2:
        r1,r2=st.columns(2)
        ra=r1.date_input('De',date.today().replace(day=1),key='lp_ra')
        rb=r2.date_input('Até',date.today(),key='lp_rb')
        c=db()
        rep=pd.read_sql_query("""select purchase_date Data,supplier_name Fornecedor,document_ref Documento,
             category Categoria,description Descrição,total Valor,notes Observações
             from loose_purchases where active=1 and purchase_date between ? and ?
             order by purchase_date,id""",c,params=[str(ra),str(rb)])
        c.close()
        st.metric('Total Compras Avulsas',brl(float(rep.Valor.sum()) if not rep.empty else 0))
        st.dataframe(rep,use_container_width=True,hide_index=True)
        if not rep.empty:export_buttons(rep,'COMPRAS_AVULSAS','lp_report')

elif page=='DF-e SEFAZ':
    st.title('DF-e / SEFAZ — Caixa de Entrada NF-e')
    st.caption('Objetivo: receber automaticamente os DF-e destinados ao CNPJ, guardar o XML, importar a NF-e completa sem digitação e permitir abrir/dar entrada pelo próprio painel.')

    cfg=settings_dict()
    cnpj=cfg.get('cnpj','')
    uf=cfg.get('uf','33')
    ult=cfg.get('ult_nsu','000000000000000')
    hom=cfg.get('ambiente','Produção')=='Homologação'
    pfx=resolve_sefaz_pfx()

    s1,s2,s3,s4=st.columns(4)
    s1.metric('CNPJ',cnpj or 'Não configurado')
    s2.metric('Ambiente','Homologação' if hom else 'Produção')
    s3.metric('ultNSU',ult or '-')
    s4.metric('Certificado','OK' if pfx else 'Não configurado')

    st.info('O XML completo recebido é importado automaticamente como NF PENDENTE. O estoque só é movimentado quando a nota estiver totalmente associada e você confirmar a entrada.')

    with st.expander('⚙️ Sincronização SEFAZ / NSU',expanded=True):
        auto_on=st.checkbox(
            'Sincronizar automaticamente ao abrir o sistema, respeitando intervalo mínimo de 1 hora',
            value=cfg.get('sefaz_auto_sync','1')=='1',
            key='sefaz_auto_sync_v113'
        )
        if str(int(auto_on))!=cfg.get('sefaz_auto_sync','1'):
            c=db()
            c.execute("""insert into settings(key,value) values('sefaz_auto_sync',?)
                         on conflict(key) do update set value=excluded.value""",(str(int(auto_on)),))
            c.commit();c.close()

        auto_result=None
        if auto_on:
            auto_result=auto_sync_sefaz_if_due(False)
            if auto_result and not auto_result.get('ok'):
                st.warning('Auto-sync: '+auto_result.get('message',''))
            elif auto_result and not auto_result.get('skipped') and auto_result.get('count',0)>0:
                confirm_success(f"Auto-sync: {auto_result.get('count')} documento(s) recebido(s).")

        cfg=settings_dict()
        d1,d2,d3,d4=st.columns(4)
        d1.metric('Última sincronização',cfg.get('sefaz_last_sync','Nunca'))
        d2.metric('cStat',cfg.get('sefaz_last_cstat','-'))
        d3.metric('ultNSU',cfg.get('ult_nsu','-'))
        d4.metric('maxNSU',cfg.get('sefaz_last_maxnsu','-'))
        lastmsg=cfg.get('sefaz_last_message','') or cfg.get('sefaz_last_error','')
        if lastmsg:
            if str(cfg.get('sefaz_last_cstat','')) not in ('137','138'):
                st.error(f"xMotivo / retorno SEFAZ: {lastmsg}")
            else:
                st.caption('xMotivo: '+str(lastmsg))

        with st.expander('🩺 Diagnóstico SEFAZ — conexão, schema e consulta por chave',expanded=False):
            tpamb='2' if hom else '1'
            endpoint=SEFAZ_HOM if hom else SEFAZ_PROD
            g1,g2,g3,g4=st.columns(4)
            g1.metric('tpAmb',tpamb)
            g2.metric('cUFAutor',str(uf).zfill(2))
            g3.metric('cStat',cfg.get('sefaz_last_cstat','-'))
            g4.metric('maxNSU',cfg.get('sefaz_last_maxnsu','-'))
            st.caption('Endpoint: '+endpoint)
            st.caption('A consulta usa distDFeInt v1.01 com tpAmb + cUFAutor + CNPJ + distNSU/consChNFe. Esta correção foi aplicada para compatibilidade com o pacote oficial Distribuição de DF-e v1.04 publicado em 03/07/2026.')
            st.code(_dfe_request_preview(cnpj,uf,ult,hom),language='xml')
            st.info('cStat 137 significa nenhum documento localizado; 138 significa documento(s) localizado(s). Outros códigos são exibidos junto do xMotivo e não são tratados como sincronização válida.')

            diag_key=st.text_input('Chave NF-e para teste (44 dígitos) — não altera o ultNSU',key='sefaz_diag_key_v1152fix')
            diag_pwd=st.text_input('Senha PFX somente para o teste desta sessão',type='password',key='sefaz_diag_pwd_v1152fix')
            x1,x2=st.columns(2)
            if x1.button('🔐 VALIDAR CERTIFICADO',key='sefaz_diag_cert_v1152fix'):
                try:
                    dpwd=diag_pwd or resolve_sefaz_password()
                    dpfx=resolve_sefaz_pfx()
                    if not dpfx or not dpwd:raise ValueError('Configure o PFX/P12 e informe a senha do certificado.')
                    info=pfx_certificate_info(dpfx,dpwd)
                    st.success(f"Certificado OK | expira em {info.get('expires','-')} | dias restantes: {info.get('days','-')}")
                    st.caption('Subject: '+str(info.get('subject','')))
                except Exception as ex:st.error(str(ex))
            if x2.button('🔎 TESTAR CONSULTA POR CHAVE',key='sefaz_diag_key_btn_v1152fix'):
                try:
                    dpwd=diag_pwd or resolve_sefaz_password()
                    dpfx=resolve_sefaz_pfx()
                    key=re.sub(r'\D','',diag_key or '')
                    if not dpfx or not dpwd:raise ValueError('Configure o PFX/P12 e informe a senha do certificado.')
                    if len(key)!=44:raise ValueError('Informe uma chave NF-e com 44 dígitos.')
                    docs_test,cs_test,msg_test=dfe_query_key(cnpj,uf,dpfx,dpwd,key,hom)
                    dfe_log_sync('DIAGNOSTICO_CHAVE',access_key=key,cstat=cs_test,message=msg_test,
                                 docs_received=len(docs_test),success=_dfe_status_ok(cs_test))
                    if _dfe_status_ok(cs_test):
                        st.success(f"cStat {cs_test} | {msg_test} | {len(docs_test)} documento(s) retornado(s).")
                    else:
                        st.error(f"cStat {cs_test} | {msg_test}")
                except Exception as ex:st.error(str(ex))

        pw=st.text_input(
            'Senha PFX para esta sessão (deixe vazio se estiver em SEFAZ_PFX_PASSWORD)',
            type='password',
            key='sefaz_pw_v113'
        )

        if st.button('🔄 SINCRONIZAR NOVOS DF-e AGORA',type='primary',key='sefaz_sync_now_v113'):
            try:
                cfg=settings_dict()
                pwd=pw or resolve_sefaz_password()
                pfx=resolve_sefaz_pfx()
                cnpj=cfg.get('cnpj','');uf=cfg.get('uf','33')
                ult_before=cfg.get('ult_nsu','000000000000000')
                hom=cfg.get('ambiente','Produção')=='Homologação'
                if not cnpj or not pfx or not pwd:
                    raise ValueError('Configure CNPJ, certificado PFX/P12 e senha do certificado.')
                newult,maxn,docs,cstat,xmotivo=dfe_sync(cnpj,uf,pfx,pwd,ult_before,hom)
                saved=save_dfe(docs,cnpj)
                ok_status=_dfe_status_ok(cstat)
                dfe_log_sync('DIST_NSU',ult_before=ult_before,ult_after=newult,max_nsu=maxn or '',
                             cstat=cstat,message=xmotivo,docs_received=len(docs),success=ok_status)
                c=db();now=datetime.now().isoformat(timespec='seconds')
                for k,v in [
                    ('ult_nsu',newult),('sefaz_last_sync',now),('sefaz_last_cstat',cstat),
                    ('sefaz_last_message',xmotivo),('sefaz_last_maxnsu',maxn or '')
                ]:
                    c.execute("""insert into settings(key,value) values(?,?)
                                 on conflict(key) do update set value=excluded.value""",(k,str(v)))
                c.commit();c.close()
                msg=(f"{len(docs)} DF-e recebido(s) | {saved.get('full_xml',0)} XML completo(s) | "
                     f"{saved.get('imported',0)} NF(s) importada(s) automaticamente | cStat {cstat} | {xmotivo}")
                if not ok_status:
                    st.error(msg)
                    st.info('O ultNSU só deve avançar com retorno válido da SEFAZ. Verifique o Diagnóstico SEFAZ abaixo.')
                elif saved.get('errors'):
                    st.warning(msg+' | Erros: '+'; '.join(saved['errors'][:5]))
                else:
                    set_flash(msg,'success');st.rerun()
            except Exception as ex:
                dfe_log_sync('DIST_NSU',ult_before=ult,cstat='',message=str(ex),docs_received=0,success=False)
                st.error(str(ex))

    cfg=settings_dict()
    cnpj=cfg.get('cnpj','')
    pending=dfe_pending_df(cnpj)

    st.subheader('📥 NF-e / XML pendentes')
    if pending.empty:
        st.success('Nenhuma NF-e pendente encontrada para este CNPJ.')
    else:
        f1,f2,f3=st.columns([2,2,1])
        search=f1.text_input('🔎 Buscar emitente, CNPJ, NF ou chave',key='dfe_search_v113')
        status_options=['Todos','Somente XML completo','Somente resumo / aguardando XML']
        sf=f2.selectbox('Situação XML',status_options,key='dfe_status_filter_v113')
        limit=f3.selectbox('Mostrar',[25,50,100,250],index=1,key='dfe_limit_v113')

        work=pending.copy()
        if search.strip():
            q=search.strip().lower()
            mask=None
            for col in ['Emitente','CNPJ','NF','Chave']:
                if col in work.columns:
                    m=work[col].fillna('').astype(str).str.lower().str.contains(q,regex=False)
                    mask=m if mask is None else (mask|m)
            if mask is not None:work=work[mask]
        if sf=='Somente XML completo':
            work=work[pd.to_numeric(work['XML Completo'],errors='coerce').fillna(0)>0]
        elif sf=='Somente resumo / aguardando XML':
            work=work[pd.to_numeric(work['XML Completo'],errors='coerce').fillna(0)<=0]
        work=work.head(int(limit))

        full_count=int((pd.to_numeric(pending['XML Completo'],errors='coerce').fillna(0)>0).sum())
        summary_count=len(pending)-full_count
        ready_count=0
        for _,r in pending.iterrows():
            iid=r.get('Nota ID')
            if pd.notna(iid):
                try:
                    if dfe_entry_readiness(int(iid)).get('ready'):ready_count+=1
                except Exception:pass

        k1,k2,k3,k4=st.columns(4)
        k1.metric('Pendentes',len(pending))
        k2.metric('XML completo',full_count)
        k3.metric('Só resumo',summary_count)
        k4.metric('Prontas para entrada',ready_count)

        show=work[['NSU','NF','Emissão','Emitente','CNPJ','Valor','Status DF-e','Status Nota','Chave']].copy()
        if 'Valor' in show.columns:
            show['Valor']=pd.to_numeric(show['Valor'],errors='coerce').fillna(0).apply(brl)
        st.dataframe(show,use_container_width=True,height=380,hide_index=True)

        summaries=work[pd.to_numeric(work['XML Completo'],errors='coerce').fillna(0)<=0]
        if not summaries.empty:
            with st.expander('Buscar XML completo das notas que ainda estão só como resumo'):
                st.warning('A consulta em lote é limitada a 5 chaves por execução para evitar excesso de chamadas ao serviço fiscal.')
                confirm_bulk=st.checkbox('Confirmo consultar até 5 chaves agora',key='dfe_bulk_confirm_v113')
                if st.button('BUSCAR XML COMPLETO — ATÉ 5 CHAVES',
                             disabled=not confirm_bulk,key='dfe_bulk_key_v113'):
                    pwd=pw or resolve_sefaz_password()
                    if not pwd:
                        st.error('Informe a senha do PFX nesta tela ou configure SEFAZ_PFX_PASSWORD.')
                    else:
                        msgs=[]
                        for _,rr in summaries.head(5).iterrows():
                            key=str(rr['Chave'] or '')
                            if len(re.sub(r'\D','',key))!=44:
                                msgs.append(f'Chave inválida/ausente: {key}')
                                continue
                            try:
                                res,cs,msg=dfe_requery_key(key,pwd)
                                msgs.append(f"{key[-8:]}: {res.get('full_xml',0)} XML completo | cStat {cs} {msg}")
                            except Exception as ex:
                                dfe_log_sync('CONSULTA_CHAVE',access_key=key,message=str(ex),success=False)
                                msgs.append(f"{key[-8:]}: ERRO {ex}")
                        set_flash(' | '.join(msgs),'success');st.rerun()

        st.divider()
        st.subheader('Documento selecionado')
        if work.empty:
            st.info('Nenhum documento com os filtros atuais.')
        else:
            options=work.id.tolist()
            did=st.selectbox(
                'NF-e / DF-e',
                options,
                key='dfe_selected_id_v113',
                format_func=lambda x:(
                    f"NF {work.loc[work.id==x,'NF'].iloc[0] or '—'} | "
                    f"{work.loc[work.id==x,'Emitente'].iloc[0] or 'Emitente não informado'} | "
                    f"{work.loc[work.id==x,'Status DF-e'].iloc[0]}"
                )
            )
            row=work[work.id==did].iloc[0]
            access=str(row['Chave'] or '')
            invoice_id=int(row['Nota ID']) if pd.notna(row['Nota ID']) else None
            is_full=bool(float(pd.to_numeric(pd.Series([row['XML Completo']]),errors='coerce').fillna(0).iloc[0])>0)

            a1,a2,a3,a4=st.columns(4)
            a1.metric('NF',str(row['NF'] or '—'))
            a2.metric('Valor',brl(row['Valor']))
            a3.metric('XML','COMPLETO' if is_full else 'RESUMO')
            a4.metric('Nota no sistema',f'ID {invoice_id}' if invoice_id else 'Ainda não importada')
            st.caption(f"Chave: {access or 'não disponível'}")
            if row.get('Erro Importação'):
                st.error('Erro ao importar XML: '+str(row['Erro Importação']))

            xml_bytes,xml_name=dfe_doc_bytes(int(did))
            c1,c2,c3=st.columns(3)
            if xml_bytes:
                label='⬇️ BAIXAR XML NF-e' if is_full else '⬇️ BAIXAR RESUMO XML'
                c1.download_button(label,xml_bytes,xml_name or 'documento.xml','application/xml',
                                   key=f'dfe_download_{did}')
            else:
                c1.warning('Arquivo XML não localizado no disco.')

            if not is_full and len(re.sub(r'\D','',access))==44:
                if c2.button('🔎 RECONSULTAR CHAVE / BUSCAR XML COMPLETO',key=f'dfe_requery_{did}'):
                    try:
                        pwd=pw or resolve_sefaz_password()
                        if not pwd:raise ValueError('Informe a senha PFX ou configure SEFAZ_PFX_PASSWORD.')
                        res,cs,msg=dfe_requery_key(access,pwd)
                        if res.get('full_xml',0)>0:
                            set_flash(f'XML completo recebido e NF importada automaticamente. cStat {cs} | {msg}','success')
                        else:
                            set_flash(f'O SEFAZ ainda não devolveu XML completo para esta chave. cStat {cs} | {msg}','warning')
                        st.rerun()
                    except Exception as ex:
                        dfe_log_sync('CONSULTA_CHAVE',access_key=access,message=str(ex),success=False)
                        st.error(str(ex))
            else:
                c2.success('XML completo já armazenado.')

            if invoice_id:
                if c3.button('📄 ABRIR NOTA PREENCHIDA — SEM DIGITAÇÃO',key=f'dfe_open_nf_{did}'):
                    st.session_state['open_invoice_id']=int(invoice_id)
                    st.session_state['_goto_page']='Notas / XML'
                    st.rerun()

                readiness=dfe_entry_readiness(invoice_id)
                st.markdown('#### Situação para entrada de estoque')
                r1,r2,r3,r4=st.columns(4)
                r1.metric('Itens XML',readiness['items'])
                r2.metric('Sem associação',readiness['pending'])
                r3.metric('Qtd/Custo inválido',readiness['invalid'])
                r4.metric('Pronta','SIM' if readiness['ready'] else 'NÃO')

                if readiness['ready']:
                    st.success('Todos os itens já estão associados e com quantidade/custo válidos.')
                    enter_confirm=st.checkbox(
                        'Confirmo dar entrada desta NF no estoque e atualizar custos',
                        key=f'dfe_enter_confirm_{invoice_id}'
                    )
                    if st.button('✅ DAR ENTRADA AUTOMATICAMENTE',
                                 type='primary',disabled=not enter_confirm,
                                 key=f'dfe_enter_now_{invoice_id}'):
                        try:
                            result=confirm_invoice_entry(int(invoice_id))
                            if result.get('already'):
                                st.warning(result['message'])
                            else:
                                set_flash(result['message'],'success');st.rerun()
                        except Exception as ex:
                            st.error('Entrada NÃO realizada: '+str(ex))
                else:
                    st.warning(
                        f"A NF já foi preenchida pelo XML, mas ainda existem {readiness['pending']} item(ns) sem associação "
                        f"e {readiness['invalid']} item(ns) com quantidade/custo inválido. "
                        "Abra a nota para alinhar uma vez; os mapeamentos fornecedor+SKU ficam gravados para as próximas notas."
                    )
            else:
                if is_full:
                    st.warning('Há XML completo, mas ele ainda não está vinculado a uma NF do sistema. Use REPROCESSAR XML abaixo.')
                    if st.button('REPROCESSAR XML E CRIAR NF PENDENTE',key=f'dfe_reprocess_{did}'):
                        try:
                            if not xml_bytes:raise ValueError('Arquivo XML não localizado.')
                            iid=import_nfe_id(xml_bytes,'SEFAZ')
                            c=db();c.execute("update dfe_docs set invoice_id=?,import_error='' where id=?",(int(iid),int(did)));c.commit();c.close()
                            set_flash(f'NF criada/vinculada com ID {iid}.','success');st.rerun()
                        except Exception as ex:st.error(str(ex))
                else:
                    st.info('Este documento é somente um resumo. Reconsulte a chave para tentar obter o XML completo.')

    with st.expander('🧾 Histórico técnico de consultas SEFAZ'):
        c=db()
        hist=pd.read_sql_query("""select event_date Data,mode Modo,access_key Chave,
            ult_nsu_before 'ultNSU antes',ult_nsu_after 'ultNSU depois',max_nsu maxNSU,
            cstat cStat,message Mensagem,docs_received Documentos,
            case success when 1 then 'OK' else 'ERRO' end Situação
            from dfe_sync_log order by id desc limit 200""",c)
        c.close()
        st.dataframe(hist,use_container_width=True,height=300,hide_index=True)


elif page=='Vendas':
    st.title('Vendas - Balcão + Delivery')
    standard_template_button('Vendas','sales_tpl')
    confirm_success('REGRA DO CONSOLIDADO: 3S = Total Bruto - Gorjeta. Delivery (99 + iFood) = quanto efetivamente fica para a loja.')
    st.caption('Tudo que não é 3S Checkout é tratado como DELIVERY. O sistema também mantém a venda bruta dos deliveries para análise, mas ela NÃO é somada ao consolidado operacional.')

    tab1,tab2,tab3,tab4=st.tabs(['Importar Planilhas','Digitação Manual','Apuração Diária','Dashboards / Skill'])

    with tab1:
        st.subheader('Importar Excel')
        st.info("""Interpretação automática:
• Venda_3s: BALCÃO = Total Bruto − Total Gorjeta.
• Geral_99: DELIVERY 99 = Receita total (líquido que fica para a loja). Receita total de vendas fica disponível como bruto 99.
• Bowls, Frango Frito, Mex, Poke e ZChicken: DELIVERY iFood.
  - Venda Bruta = valor_cesta_final, uma única vez por pedido.
  - Líquido Loja = soma da coluna valor SOMENTE quando impacto_no_repasse = SIM.
  - Linhas com impacto_no_repasse = NÃO não são descontadas novamente do repasse.""")
        ups=st.file_uploader('Selecione uma ou várias planilhas XLS/XLSX',type=['xls','xlsx'],accept_multiple_files=True,key='sales_correct_import')
        if ups and st.button('PROCESSAR / REPROCESSAR PLANILHAS',type='primary'):
            msgs=[];errs=[];total=0
            for up in ups:
                try:
                    up.seek(0);rows,kind=detect_and_parse_sales(up);n=_upsert_sales_daily(rows,up.name);total+=n
                    msgs.append(f"{up.name}: {n} novo(s) registro(s) incluído(s); {st.session_state.get('_sales_import_skipped',0)} já existente(s) mantido(s) ({kind})")
                except Exception as ex:errs.append(f'{up.name}: {ex}')
            if msgs:confirm_success('\n'.join(msgs))
            if errs:st.error('\n'.join(errs))
            if total:st.rerun()

    with tab2:
        st.subheader('Digitação direta')
        a,b,cx=st.columns(3)
        md=a.date_input('Data',date.today(),key='sales_manual_date7')
        src=b.selectbox('Origem',['3S','99','IFOOD','OUTRO DELIVERY'],key='sales_manual_source7')
        brand=cx.text_input('Marca / estabelecimento',key='sales_manual_brand7')
        d1,d2,d3,d4=st.columns(4)
        gross=d1.number_input('Venda Bruta / Base',min_value=0.0,format='%.2f',key='sales_manual_gross7')
        tips=d2.number_input('Gorjeta (3S)',min_value=0.0,format='%.2f',key='sales_manual_tip7')
        net=d3.number_input('Líquido que fica na loja (Delivery)',min_value=0.0,format='%.2f',key='sales_manual_net7')
        clients=d4.number_input('Clientes / Tickets',min_value=0,step=1,key='sales_manual_clients7')
        considered=(gross-tips) if src=='3S' else net
        st.metric('Venda considerada no consolidado',brl(considered))
        st.caption('No 3S o sistema usa Bruto − Gorjeta. Nos demais, usa o Líquido Loja.')
        notes=st.text_input('Observações',key='sales_manual_notes7')
        if st.button('SALVAR VENDA',type='primary'):
            if not brand.strip():st.error('Informe a marca/estabelecimento.')
            else:
                gross_save=(gross-tips) if src=='3S' else gross
                _upsert_sales_daily([{'sale_date':md,'source':src,'brand':brand.strip(),'store':brand.strip(),
                    'gross_sales':gross_save,'net_store':gross_save if src=='3S' else net,'tips':tips,
                    'tickets':clients,'avg_ticket':(considered/clients if clients else 0),
                    'credits_inflows':considered,'notes':notes}],'DIGITAÇÃO MANUAL')
                confirm_success('Venda gravada.');st.rerun()

        c=db();man=pd.read_sql_query("""select id,sale_date Data,source Origem,brand Marca,
            gross_sales 'Venda Bruta / Base',net_store 'Líquido Loja',tips Gorjeta,tickets Clientes
            from sales_daily order by sale_date desc,id desc limit 150""",c);c.close()
        st.dataframe(man,use_container_width=True,height=330)
        if not man.empty:
            rid=st.selectbox('Alterar / excluir lançamento',man.id.tolist(),key='sales_edit_id7',
                format_func=lambda x:f"{man.loc[man.id==x,'Data'].iloc[0]} | {man.loc[man.id==x,'Origem'].iloc[0]} | {man.loc[man.id==x,'Marca'].iloc[0]}")
            r=man[man.id==rid].iloc[0]
            e1,e2,e3,e4=st.columns(4)
            eg=e1.number_input('Venda Bruta/Base',min_value=0.0,value=float(r['Venda Bruta / Base'] or 0),key='sales_eg7')
            en=e2.number_input('Líquido Loja',value=float(r['Líquido Loja'] or 0),key='sales_en7')
            et=e3.number_input('Gorjeta',min_value=0.0,value=float(r['Gorjeta'] or 0),key='sales_et7')
            ec=e4.number_input('Clientes',min_value=0,value=int(r['Clientes'] or 0),key='sales_ec7')
            considered_edit=eg if str(r['Origem']).upper()=='3S' else en
            b1,b2=st.columns(2)
            if b1.button('SALVAR ALTERAÇÃO'):
                c=db();c.execute("update sales_daily set gross_sales=?,net_store=?,tips=?,tickets=?,avg_ticket=? where id=?",
                    (eg,en,et,ec,(considered_edit/ec if ec else 0),rid));c.commit();c.close();st.rerun()
            if b2.button('EXCLUIR LANÇAMENTO'):
                c=db();c.execute("delete from sales_daily where id=?",(rid,));c.commit();c.close();st.rerun()

    with tab3:
        st.subheader('Apuração Diária Consolidada')
        f1,f2=st.columns(2)
        a=f1.date_input('De',date.today().replace(day=1),key='sales_daily_a7')
        b=f2.date_input('Até',date.today(),key='sales_daily_b7')
        df=sales_period_df(a,b)
        if df.empty:
            st.info('Sem vendas no período.')
        else:
            sm=sales_channel_summary(a,b)
            balc=sm['balcao_sales'];delivery=sm['delivery_sales'];total=sm['total_sales'];clients=sm['total_clients']
            k1,k2,k3=st.columns(3)
            k1.metric('Balcão 3S sem gorjeta',brl(balc))
            k2.metric('Clientes Balcão',f"{sm['balcao_clients']:,}".replace(',','.'))
            k3.metric('Ticket Médio Balcão',brl(sm['balcao_ticket']))
            k4,k5,k6=st.columns(3)
            k4.metric('Delivery Líquido',brl(delivery))
            k5.metric('Clientes Delivery',f"{sm['delivery_clients']:,}".replace(',','.'))
            k6.metric('Ticket Médio Delivery',brl(sm['delivery_ticket']))
            k7,k8,k9=st.columns(3)
            k7.metric('TOTAL ACUMULADO',brl(total))
            k8.metric('Clientes Acumulados',f"{sm['total_clients']:,}".replace(',','.'))
            k9.metric('Ticket Médio Acumulado',brl(sm['total_ticket']))

            work=df.copy()
            work['Balcão 3S']=work.apply(lambda r:r['Venda Considerada'] if str(r['Origem']).upper()=='3S' else 0,axis=1)
            work['Delivery Líquido']=work.apply(lambda r:r['Venda Considerada'] if str(r['Origem']).upper()!='3S' else 0,axis=1)
            daily=work.groupby('Data',as_index=False).agg({
                'Balcão 3S':'sum','Delivery Líquido':'sum','Clientes':'sum'})
            daily['Total Consolidado']=daily['Balcão 3S']+daily['Delivery Líquido']
            daily['Ticket Médio']=daily.apply(lambda r:r['Total Consolidado']/r['Clientes'] if r['Clientes'] else 0,axis=1)
            daily['Participação %']=daily['Total Consolidado']/daily['Total Consolidado'].sum()*100 if daily['Total Consolidado'].sum() else 0
            daily['Data']=pd.to_datetime(daily['Data']).dt.strftime('%d/%m/%Y')
            show=daily.copy()
            for col in ['Balcão 3S','Delivery Líquido','Total Consolidado','Ticket Médio']:show[col]=show[col].apply(brl)
            show['Participação %']=show['Participação %'].map(lambda x:f'{x:.2f}%')
            st.dataframe(show,use_container_width=True,height=440)
            export_buttons(show,'VENDA_CORRETA_DIARIA','sales_correct_daily')

            st.subheader('Vendas e Compras — Semanas Fixas do Mês')
            st.caption('Regra operacional: 1–7 = 1ª semana; 8–14 = 2ª; 15–21 = 3ª; 22 até o último dia do mês = 4ª semana.')
            fixed_rows=[]
            for wk in fixed_month_week_ranges(a,b):
                ws=consolidated_sales_value(wk['Início'],wk['Fim'])
                wp=purchases_value(wk['Início'],wk['Fim'],None)
                fixed_rows.append({
                    'Mês':wk['Mês'],'Semana':wk['Semana'],
                    'Início':wk['Início'],'Fim':wk['Fim'],
                    'Vendas':ws,'Compras':wp,
                    'Compras/Vendas %':wp/ws*100 if ws else 0
                })
            fixed_weekly=pd.DataFrame(fixed_rows)
            if not fixed_weekly.empty:
                fwshow=fixed_weekly.copy()
                fwshow['Início']=pd.to_datetime(fwshow['Início']).dt.strftime('%d/%m/%Y')
                fwshow['Fim']=pd.to_datetime(fwshow['Fim']).dt.strftime('%d/%m/%Y')
                fwshow['Vendas']=fwshow['Vendas'].map(brl)
                fwshow['Compras']=fwshow['Compras'].map(brl)
                fwshow['Compras/Vendas %']=fwshow['Compras/Vendas %'].map(lambda x:f'{x:.2f}%')
                st.dataframe(fwshow,use_container_width=True,hide_index=True,height=300)
                export_buttons(fixed_weekly,'VENDAS_COMPRAS_SEMANAS_FIXAS','sales_purchases_fixed_weeks')
                chart=fixed_weekly.copy()
                chart['Período']=chart['Mês']+' • '+chart['Semana']
                st.plotly_chart(px.bar(chart,x='Período',y=['Vendas','Compras'],barmode='group'),
                                use_container_width=True)

            st.subheader('Delivery por Marca - Líquido Loja')
            dd=df[df['Origem'].str.upper()!='3S'].groupby(['Origem','Marca'],as_index=False).agg({
                'Venda Bruta / Base':'sum','Líquido Loja':'sum','Clientes':'sum'})
            dd['Diferença / Custos']=dd['Líquido Loja']-dd['Venda Bruta / Base']
            dd['Ticket Médio Líquido']=dd.apply(lambda r:r['Líquido Loja']/r['Clientes'] if r['Clientes'] else 0,axis=1)
            dshow=dd.copy()
            for col in ['Venda Bruta / Base','Líquido Loja','Diferença / Custos','Ticket Médio Líquido']:dshow[col]=dshow[col].apply(brl)
            st.dataframe(dshow,use_container_width=True,height=350)

    with tab4:
        st.subheader('Dashboard Comparativo / Análise por Skill')
        q1,q2=st.columns(2)
        a=q1.date_input('Período inicial',date.today().replace(day=1),key='sales_dash_a7')
        b=q2.date_input('Período final',date.today(),key='sales_dash_b7')
        df=sales_period_df(a,b)
        if df.empty:
            st.info('Sem vendas no período.')
        else:
            nd=(b-a).days+1;pa=a-timedelta(days=nd);pb=a-timedelta(days=1);prev=sales_period_df(pa,pb)
            cur=float(df['Venda Considerada'].sum())
            old=float(prev['Venda Considerada'].sum()) if not prev.empty else 0
            cli=int(df['Clientes'].sum());pcli=int(prev['Clientes'].sum()) if not prev.empty else 0
            def delta(x,y):return None if not y else f'{(x/y-1)*100:+.1f}%'
            balc=float(df.loc[df['Origem'].str.upper()=='3S','Venda Considerada'].sum())
            deli=float(df.loc[df['Origem'].str.upper()!='3S','Venda Considerada'].sum())
            z1,z2,z3,z4=st.columns(4)
            z1.metric('Total Consolidado',brl(cur),delta(cur,old))
            z2.metric('Balcão 3S',brl(balc))
            z3.metric('Delivery Líquido',brl(deli))
            z4.metric('Ticket Médio',brl(cur/cli if cli else 0),delta(cur/cli if cli else 0,old/pcli if pcli else 0))
            _sm=sales_channel_summary(a,b)
            cc1,cc2,cc3=st.columns(3)
            cc1.metric('Clientes Balcão',_sm['balcao_clients'])
            cc2.metric('Clientes Delivery',_sm['delivery_clients'])
            cc3.metric('Clientes Total',_sm['total_clients'])

            # Evolução diária
            temp=df.copy()
            temp['Balcão 3S']=temp.apply(lambda r:r['Venda Considerada'] if str(r['Origem']).upper()=='3S' else 0,axis=1)
            temp['Delivery Líquido']=temp.apply(lambda r:r['Venda Considerada'] if str(r['Origem']).upper()!='3S' else 0,axis=1)
            daily=temp.groupby('Data_dt',as_index=False).agg({'Balcão 3S':'sum','Delivery Líquido':'sum','Clientes':'sum'})
            daily['Total']=daily['Balcão 3S']+daily['Delivery Líquido']
            st.markdown('#### Balcão x Delivery x Total')
            st.line_chart(daily.set_index('Data_dt')[['Balcão 3S','Delivery Líquido','Total']])

            # Dia da semana
            dow=df.groupby('Dia da Semana',as_index=False).agg({'Venda Considerada':'sum','Clientes':'sum'})
            order=['Segunda','Terça','Quarta','Quinta','Sexta','Sábado','Domingo']
            dow['ord']=dow['Dia da Semana'].map({v:i for i,v in enumerate(order)});dow=dow.sort_values('ord')
            dow['Participação %']=dow['Venda Considerada']/dow['Venda Considerada'].sum()*100 if dow['Venda Considerada'].sum() else 0
            dow['Ticket Médio']=dow.apply(lambda r:r['Venda Considerada']/r['Clientes'] if r['Clientes'] else 0,axis=1)
            st.markdown('#### Venda considerada por dia da semana')
            st.bar_chart(dow.set_index('Dia da Semana')['Venda Considerada'])
            ds=dow.drop(columns=['ord']).copy()
            ds['Venda Considerada']=ds['Venda Considerada'].apply(brl);ds['Ticket Médio']=ds['Ticket Médio'].apply(brl);ds['Participação %']=ds['Participação %'].map(lambda x:f'{x:.2f}%')
            st.dataframe(ds,use_container_width=True)

            # Skill do iFood
            ifood=df[df['Origem'].str.upper()=='IFOOD'].copy()
            if not ifood.empty:
                st.markdown('#### iFood — Análise de Repasse')
                igross=float(ifood['Venda Bruta / Base'].sum())
                icred=float(ifood['Entradas/Créditos'].sum())
                ifees=float(ifood['Taxas/Comissões'].sum())
                isvc=float(ifood['Serviços/Promoções/Ajustes'].sum())
                inet=float(ifood['Líquido Loja'].sum())
                a1,a2,a3,a4,a5=st.columns(5)
                a1.metric('Venda Bruta Delivery',brl(igross))
                a2.metric('Entradas/Créditos',brl(icred))
                a3.metric('Taxas/Comissões',brl(ifees))
                a4.metric('Serviços/Ajustes',brl(isvc))
                a5.metric('Líquido Loja',brl(inet))
                st.caption('Líquido Loja = soma real das linhas com impacto_no_repasse = SIM. A venda bruta é mostrada apenas para análise e não é somada ao balcão.')

                bm=ifood.groupby('Marca',as_index=False).agg({
                    'Venda Bruta / Base':'sum','Entradas/Créditos':'sum',
                    'Taxas/Comissões':'sum','Serviços/Promoções/Ajustes':'sum',
                    'Líquido Loja':'sum','Clientes':'sum'})
                bm['Conversão Bruto→Líquido %']=bm.apply(lambda r:r['Líquido Loja']/r['Venda Bruta / Base']*100 if r['Venda Bruta / Base'] else 0,axis=1)
                bm=bm.sort_values('Líquido Loja',ascending=False)
                bms=bm.copy()
                for col in ['Venda Bruta / Base','Entradas/Créditos','Taxas/Comissões','Serviços/Promoções/Ajustes','Líquido Loja']:bms[col]=bms[col].apply(brl)
                bms['Conversão Bruto→Líquido %']=bms['Conversão Bruto→Líquido %'].map(lambda x:f'{x:.1f}%')
                st.dataframe(bms,use_container_width=True,height=360)

            # 99
            n99=df[df['Origem'].str.upper()=='99'].copy()
            if not n99.empty:
                st.markdown('#### 99 — Particularidade')
                n1,n2,n3=st.columns(3)
                n1.metric('Venda Bruta 99',brl(n99['Venda Bruta / Base'].sum()))
                n2.metric('Líquido Loja 99',brl(n99['Líquido Loja'].sum()))
                n3.metric('Ajuste Bruto→Líquido',brl(n99['Líquido Loja'].sum()-n99['Venda Bruta / Base'].sum()))
                st.caption('No consolidado entra somente a coluna Receita total do relatório 99, pois ela já representa o resultado líquido calculado pela plataforma.')


elif page=='Associações & Conversões':
    st.title('Associações & Conversões')
    st.caption('Configuração independente da NF. O que for salvo aqui vira padrão para as próximas entradas do mesmo Fornecedor + SKU.')

    tabm,tabn=st.tabs(['Pesquisar / Alterar Defaults','Criar Associação'])

    with tabm:
        q=st.text_input('🔎 Pesquisar por fornecedor, SKU, descrição ou produto',key='map_search')
        c=db()
        like='%'+q.strip()+'%'
        mappings=pd.read_sql_query("""select m.id,m.supplier_id,s.legal_name Fornecedor,
            m.supplier_code SKU,m.supplier_barcode Barcode,m.supplier_description Descrição,
            m.product_id,p.code 'Código Produto',p.name 'Produto Associado',
            m.multiplier 'Fator Multiplicação',m.conversion 'Fator Conversão',
            m.commercial_unit 'Unidade Comercial',m.stock_unit 'Unidade Estoque'
            from mappings m join suppliers s on s.id=m.supplier_id
            left join products p on p.id=m.product_id
            where (?='' or s.legal_name like ? or m.supplier_code like ?
                   or m.supplier_description like ? or p.name like ? or cast(p.code as text) like ?)
            order by s.legal_name,m.supplier_description""",c,
            params=[q.strip(),like,like,like,like,like])
        c.close()
        if mappings.empty:
            st.info('Nenhuma associação encontrada.')
        else:
            st.dataframe(mappings.drop(columns=['supplier_id','product_id']),use_container_width=True,
                         hide_index=True,height=360)
            mid=st.selectbox('Associação para editar',mappings.id.tolist(),key='map_edit_id',
                format_func=lambda x:f"{mappings.loc[mappings.id==x,'Fornecedor'].iloc[0]} | "
                                     f"{mappings.loc[mappings.id==x,'SKU'].iloc[0]} | "
                                     f"{mappings.loc[mappings.id==x,'Descrição'].iloc[0]} → "
                                     f"{mappings.loc[mappings.id==x,'Produto Associado'].iloc[0]}")
            mr=mappings[mappings.id==mid].iloc[0]
            c=db();sup=pd.read_sql_query("select id,legal_name from suppliers where active=1 order by legal_name",c);c.close()
            labels,label_to_id,id_to_label=invoice_product_options()
            current_label=id_to_label.get(int(mr['product_id']),'— NÃO ASSOCIADO —') if pd.notna(mr['product_id']) else '— NÃO ASSOCIADO —'
            m1,m2=st.columns(2)
            sid=m1.selectbox('Fornecedor',sup.id.tolist(),index=sup.id.tolist().index(int(mr['supplier_id'])) if int(mr['supplier_id']) in sup.id.tolist() else 0,
                key='map_edit_supplier',format_func=lambda x:sup.loc[sup.id==x,'legal_name'].iloc[0])
            sku=m2.text_input('SKU / Código do fornecedor',value=str(mr['SKU'] or ''),key='map_edit_sku')
            desc=st.text_input('Descrição do fornecedor',value=str(mr['Descrição'] or ''),key='map_edit_desc')
            barcode=st.text_input('Barcode fornecedor',value=str(mr['Barcode'] or ''),key='map_edit_bar')
            pidx=labels.index(current_label) if current_label in labels else 0
            plabel=st.selectbox('Produto associado',labels,index=pidx,key='map_edit_product')
            a,b,cx,d=st.columns(4)
            mult=a.number_input('Fator multiplicação',min_value=0.001,value=float(mr['Fator Multiplicação'] or 1),step=0.001,format=num_format(),key='map_edit_mult')
            conv=b.number_input('Fator conversão / gramatura',min_value=0.001,value=float(mr['Fator Conversão'] or 1),step=0.001,format=num_format(),key='map_edit_conv')
            comm=cx.text_input('Unidade comercial',value=str(mr['Unidade Comercial'] or ''),key='map_edit_comm')
            stock=d.text_input('Unidade estoque',value=str(mr['Unidade Estoque'] or ''),key='map_edit_stock')
            apply_pending=st.checkbox('Aplicar também às NFs pendentes deste Fornecedor + SKU',value=True,key='map_edit_pending')
            b1,b2=st.columns(2)
            if b1.button('✅ SALVAR DEFAULT',type='primary',key='map_edit_save'):
                pid=label_to_id.get(plabel)
                if not pid:st.error('Selecione um produto.')
                else:
                    try:
                        n=save_mapping_default(int(mid),int(sid),sku,barcode,desc,int(pid),
                                               mult,conv,comm,stock,apply_pending)
                        set_flash(f'Default salvo. {n} item(ns) pendente(s) atualizado(s).','success');st.rerun()
                    except Exception as ex:st.error(str(ex))
            confirm=st.checkbox('Confirmo que quero excluir esta associação/default',key='map_del_confirm')
            if b2.button('EXCLUIR DEFAULT',disabled=not confirm,key='map_delete'):
                c=db()
                try:
                    c.execute('BEGIN IMMEDIATE')
                    before=c.execute("select * from mappings where id=?",(int(mid),)).fetchone()
                    c.execute("delete from mappings where id=?",(int(mid),))
                    c.execute("""insert into correction_audit(event_date,module,record_id,action,before_json,after_json)
                                 values(?,?,?,?,?,?)""",
                              (datetime.now().isoformat(timespec='seconds'),'ASSOCIAÇÃO/CONVERSÃO',
                               str(mid),'EXCLUIR',json.dumps(dict(before),ensure_ascii=False) if before else '{}','{}'))
                    c.commit();set_flash('Associação/default excluído. Notas históricas não foram alteradas.','success');st.rerun()
                except Exception as ex:c.rollback();st.error(str(ex))
                finally:c.close()

    with tabn:
        c=db()
        sup=pd.read_sql_query("select id,legal_name from suppliers where active=1 order by legal_name",c);c.close()
        if sup.empty:
            st.info('Cadastre um fornecedor primeiro.')
        else:
            nsid=st.selectbox('Fornecedor',sup.id.tolist(),key='map_new_supplier',
                format_func=lambda x:sup.loc[sup.id==x,'legal_name'].iloc[0])
            nsku=st.text_input('SKU / Código fornecedor',key='map_new_sku')
            ndesc=st.text_input('Descrição fornecedor',key='map_new_desc')
            nbar=st.text_input('Barcode fornecedor',key='map_new_bar')
            labels,label_to_id,id_to_label=invoice_product_options()
            nlabel=st.selectbox('Produto associado',labels,key='map_new_product')
            n1,n2,n3,n4=st.columns(4)
            nmult=n1.number_input('Multiplicação',min_value=0.001,value=1.0,step=0.001,format=num_format(),key='map_new_mult')
            nconv=n2.number_input('Conversão / gramatura',min_value=0.001,value=1.0,step=0.001,format=num_format(),key='map_new_conv')
            ncomm=n3.text_input('Unidade comercial',key='map_new_comm')
            nstock=n4.text_input('Unidade estoque',key='map_new_stock')
            if st.button('CRIAR E SALVAR DEFAULT',type='primary',key='map_new_save'):
                npid=label_to_id.get(nlabel)
                if not nsku.strip():st.error('Informe o SKU do fornecedor.')
                elif not npid:st.error('Selecione o produto.')
                else:
                    try:
                        n=save_mapping_default(None,int(nsid),nsku,nbar,ndesc,int(npid),
                                               nmult,nconv,ncomm,nstock,True)
                        set_flash(f'Associação criada. {n} item(ns) de NFs pendentes atualizado(s).','success');st.rerun()
                    except Exception as ex:st.error(str(ex))

elif page=='Estoque Inicial':
    st.title('Contagem Inicial de Estoque')
    st.info('Regra: a contagem inicial pode ser reaberta, alterada e ter itens excluídos. Ao reabrir, os movimentos iniciais são desfeitos antes da correção.')
    st.caption('Use este módulo para implantar o saldo inicial. Você pode cadastrar produtos e custos durante a própria contagem.')
    standard_template_button('Estoque Inicial','opening_tpl')

    c=db();batches=pd.read_sql_query("select id ID,batch_date Data,name Nome,status Status,notes Observações from opening_stock_batches order by id desc",c);c.close()
    t0,t1,t2=st.tabs(['Gerenciar','Contar / Alterar','Importar XLSX'])

    with t0:
        if not batches.empty:
            st.dataframe(batches,use_container_width=True,height=260)
            bid=st.selectbox('Contagem inicial',batches.ID.tolist(),key='opening_manage',
                format_func=lambda x:f"#{x} | {batches.loc[batches.ID==x,'Data'].iloc[0]} | {batches.loc[batches.ID==x,'Nome'].iloc[0]} | {batches.loc[batches.ID==x,'Status'].iloc[0]}")
            row=batches[batches.ID==bid].iloc[0]
            a,b,cx=st.columns(3)
            if str(row.Status).upper()=='ABERTO':
                if a.button('FECHAR E LANÇAR ESTOQUE',type='primary'):
                    close_opening_batch(int(bid));clear_data_cache();confirm_success('Estoque inicial lançado.');st.rerun()
            else:
                if a.button('REABRIR'):
                    reopen_opening_batch(int(bid));confirm_success('Contagem reaberta e movimentos iniciais retirados.');st.rerun()
            if b.button('ABRIR PARA CONTAR'):
                st.session_state['opening_batch_id']=int(bid);confirm_success('Contagem selecionada.')
            conf=st.checkbox('Confirmo exclusão desta contagem inicial',key='opening_del_conf')
            if cx.button('EXCLUIR',disabled=not conf):
                delete_opening_batch(int(bid));st.session_state.pop('opening_batch_id',None);st.rerun()

        st.divider()
        d=st.date_input('Data base',date.today(),key='opening_new_date')
        n=st.text_input('Nome',value=f'Estoque Inicial {date.today().strftime("%d/%m/%Y")}',key='opening_new_name')
        obs=st.text_input('Observações',key='opening_new_obs')
        if st.button('CRIAR CONTAGEM INICIAL ABERTA'):
            bid=create_opening_batch(d,n,obs);st.session_state['opening_batch_id']=bid;confirm_success(f'Contagem #{bid} criada.');st.rerun()

    active_id=st.session_state.get('opening_batch_id')
    active=get_opening_batch(active_id) if active_id else None

    with t1:
        if not active or str(active['status']).upper()!='ABERTO':
            st.warning('Crie ou selecione uma contagem inicial ABERTA.')
        else:
            confirm_success(f"Editando #{active_id} — {active['name']}")
            st.caption('Edite quantidades e custos diretamente na tabela. Somente linhas com quantidade maior que zero serão gravadas.')

            with st.expander('➕ CADASTRAR PRODUTO NO ATO',expanded=False):
                np=st.text_input('Nome do produto',key='opening_np');nb=st.text_input('Marca',key='opening_nb')
                x1,x2,x3=st.columns(3)
                nc=x1.text_input('Categoria',key='opening_nc')
                ns=x2.text_input('Subcategoria',key='opening_ns')
                nu=x3.selectbox('Unidade',['UN','KG','G','L','ML','CX','PCT'],key='opening_nu')
                bc=st.text_input('Barcode fornecedor',key='opening_bc')
                ic=st.number_input('Custo inicial',min_value=0.0,format=num_format(),key='opening_ic')
                iq=st.number_input('Quantidade inicial',min_value=0.0,format=num_format(),key='opening_iq')
                if st.button('CADASTRAR + INCLUIR NA CONTAGEM') and np and nc and ic>0:
                    c=db();code=c.execute('select coalesce(max(code),100000)+1 x from products').fetchone()['x'];ib=ean13(code)
                    pid=c.execute('insert into products(code,internal_barcode,name,brand,category,subcategory,unit) values(?,?,?,?,?,?,?)',(code,ib,np,nb,nc,ns,nu)).lastrowid
                    c.execute('insert or ignore into product_barcodes(product_id,barcode,description) values(?,?,?)',(pid,ib,'Código interno'))
                    if bc:c.execute('insert or ignore into product_barcodes(product_id,barcode,description) values(?,?,?)',(pid,bc,'Fornecedor'))
                    c.commit();c.close();clear_data_cache()
                    save_opening_item(int(active_id),pid,iq,ic,'Cadastrado na contagem inicial')
                    confirm_success(f'Produto {code} cadastrado e incluído.');st.rerun()

            c=db()
            existing=pd.read_sql_query("""select product_id,qty,unit_cost,notes
                from opening_stock_items where batch_id=?""",c,params=[active_id])
            c.close()

            base=product_grid_base()
            cats=sorted(base['Categoria'].dropna().unique().tolist()) if not base.empty else []
            sc=st.multiselect('Filtrar categoria(s)',cats,key='opening_grid_cats')
            search=st.text_input('🔎 Buscar produto por código/nome/categoria',key='opening_grid_search')
            if sc:
                base=base[base['Categoria'].isin(sc)]
            if search:
                ss=search.lower()
                base=base[base.apply(lambda r:ss in (str(r['Código'])+' '+str(r['Produto'])+' '+str(r['Categoria'])).lower(),axis=1)]

            edited=editable_count_grid(base,existing,'Quantidade Inicial','Custo Unitário',key=f'opening_grid_{active_id}')

            b1,b2=st.columns(2)
            if b1.button('SALVAR TODA A TABELA',type='primary'):
                n=0;errs=[]
                for _,r in edited.iterrows():
                    try:
                        qty=float(r['Quantidade Inicial'] or 0)
                        cost=float(r['Custo Unitário'] or 0)
                        pid=int(r['id'])
                        if qty<=0:
                            continue
                        if cost<=0:
                            raise ValueError(f"Custo inválido para {r['Produto']}")
                        save_opening_item(int(active_id),pid,qty,cost,str(r.get('Observações','')))
                        n+=1
                    except Exception as ex:
                        errs.append(str(ex))
                confirm_success(f'{n} itens gravados/atualizados.')
                if errs:st.warning('\n'.join(errs[:20]))
                st.rerun()

            if b2.button('ZERAR FILTRO / RECARREGAR'):
                st.rerun()

            c=db()
            cur=pd.read_sql_query("""select osi.id,p.code Código,p.name Produto,p.category Categoria,p.unit Unidade,
                osi.qty Quantidade,osi.unit_cost 'Custo Unitário',(osi.qty*osi.unit_cost) Valor,osi.notes Observações
                from opening_stock_items osi join products p on p.id=osi.product_id
                where osi.batch_id=? order by p.category,p.name""",c,params=[active_id])
            c.close()
            if not cur.empty:
                st.subheader('Itens já gravados')
                st.dataframe(cur,use_container_width=True,height=300)
                export_buttons(cur,f'ESTOQUE_INICIAL_{active_id}','opening_exp')
                _oid=st.selectbox('Excluir item da contagem inicial',cur.id.tolist(),key=f'opening_del_item_{active_id}',
                    format_func=lambda x:f"{int(cur.loc[cur.id==x,'Código'].iloc[0])} | {cur.loc[cur.id==x,'Produto'].iloc[0]}")
                if st.button('🗑️ EXCLUIR ITEM DA CONTAGEM INICIAL',key=f'opening_del_item_btn_{active_id}'):
                    c=db();c.execute("delete from opening_stock_items where id=? and batch_id=?",(_oid,active_id));c.commit();c.close()
                    confirm_success('Item excluído.');st.rerun()

    with t2:
        if not active or str(active['status']).upper()!='ABERTO':
            st.warning('Selecione uma contagem inicial ABERTA.')
        else:
            up=st.file_uploader('Planilha padrão preenchida',type=['xlsx'],key='opening_import')
            if up and st.button('IMPORTAR SOMENTE ITENS NOVOS / ATUALIZAR CONTAGEM'):
                x=pd.read_excel(up);n=0;errs=[]
                for ix,r in x.iterrows():
                    try:
                        code=r.get('Código Produto')
                        pid=None
                        if not pd.isna(code):
                            c=db();pr=c.execute("select id from products where code=?",(int(code),)).fetchone();c.close();pid=pr['id'] if pr else None
                        if not pid:
                            name=str(r.get('Nome Produto','')).strip()
                            if not name or name.lower()=='nan':raise ValueError('produto não localizado e sem nome')
                            cat=str(r.get('Categoria','')).strip();unit=str(r.get('Unidade','UN')).strip()
                            c=db();newcode=c.execute('select coalesce(max(code),100000)+1 x from products').fetchone()['x'];ib=ean13(newcode)
                            pid=c.execute('insert into products(code,internal_barcode,name,category,subcategory,unit) values(?,?,?,?,?,?)',(newcode,ib,name,cat,'',unit)).lastrowid
                            c.execute('insert or ignore into product_barcodes(product_id,barcode,description) values(?,?,?)',(pid,ib,'Código interno'));c.commit();c.close();clear_data_cache()
                        qty=_money(r.get('Quantidade Inicial'));cost=_money(r.get('Custo Unitário'))
                        save_opening_item(int(active_id),pid,qty,cost,str(r.get('Observações','')))
                        n+=1
                    except Exception as ex:errs.append(f'Linha {ix+2}: {ex}')
                confirm_success(f'{n} itens processados.')
                if errs:st.warning('\\n'.join(errs[:30]))
                st.rerun()

elif page=='Estoque':
    st.title('Gestão de Estoque')
    t1,t2=st.tabs(['Saldo e custos','Dias / Mínimo / Máximo / Segurança'])
    with t1:
        q=st.text_input('🔎 Pesquisar estoque por código, produto, marca ou categoria',key='stock_fast_search')
        dfstock=stock_snapshot_df(q)
        if dfstock.empty:
            st.info('Nenhum item encontrado.')
        else:
            total_qty=float(dfstock['Saldo'].sum())
            total_value=float(dfstock['Valor'].sum())
            a,b,cx=st.columns(3)
            a.metric('Itens encontrados',len(dfstock))
            b.metric('Saldo total (unidades equivalentes)',f'{total_qty:,.3f}')
            cx.metric('Valor do estoque',brl(total_value))
            st.dataframe(dfstock,use_container_width=True,height=600,hide_index=True,
                column_config={
                    'Saldo':st.column_config.NumberColumn(format=num_format()),
                    'Custo Médio Vigente':st.column_config.NumberColumn(format='R$ '+num_format()),
                    'Valor':st.column_config.NumberColumn(format='R$ %.2f')
                })
            export_buttons(dfstock,'POSICAO_ESTOQUE','stock_fast_export')
    with t2:
        st.caption('Parâmetros recomendados calculados pelas retiradas e perdas. Estoque de segurança usa variabilidade diária e nível de serviço aproximado de 95%.')
        horizon=st.slider('Janela de consumo (dias)',30,180,90,step=15);lead=st.number_input('Lead time padrão (dias)',min_value=1.0,value=7.0);review=st.number_input('Ciclo de revisão/pedido (dias)',min_value=1.0,value=7.0)
        allp=products('');cats=sorted(allp.Categoria.unique().tolist());sc=st.multiselect('Categorias (vazio = todas)',cats)
        if sc:allp=allp[allp.Categoria.isin(sc)]
        rows=[]
        for _,r in allp.iterrows():
            m=stock_metrics(int(r.id),horizon,lead,review,1.65);bal=balance(int(r.id));rows.append([r.Código,r.Produto,r.Categoria,bal,m['avg_daily'],m['days_stock'],m['safety'],m['minimum'],m['standard'],m['maximum']])
        dfm=pd.DataFrame(rows,columns=['Código','Produto','Categoria','Saldo','Consumo Médio/Dia','Dias de Estoque','Estoque Segurança','Estoque Mínimo','Estoque Padrão','Estoque Máximo'])
        st.dataframe(dfm,use_container_width=True,height=560)
        buf=io.BytesIO();dfm.to_excel(buf,index=False);st.download_button('Exportar política de estoque',buf.getvalue(),'POLITICA_ESTOQUE.xlsx')

elif page=='Extrato de Itens':
    st.title('Extrato de Itens — Todos os Produtos')
    st.caption('Todos os produtos e todas as categorias, inclusive inativos. O extrato mostra NF, data da NF, fornecedor e permite abrir/reabrir a própria nota para correção.')

    q=st.text_input('🔎 Pesquisar por código, produto, marca, categoria, subcategoria ou barcode',key='timeline_all_search_v114')
    allp=all_products_df(q,10000)
    cats=sorted(allp['Categoria'].fillna('').astype(str).unique().tolist()) if not allp.empty else []
    selected_cats=st.multiselect('Filtrar categorias (vazio = TODAS)',cats,key='timeline_all_cats_v114')
    if selected_cats and not allp.empty:
        allp=allp[allp['Categoria'].astype(str).isin(selected_cats)]
    st.caption(f'{len(allp)} produto(s) disponível(is) no filtro atual.')
    if allp.empty:
        st.warning('Nenhum produto encontrado.')
    else:
        st.dataframe(allp[['Código','Produto','Marca','Categoria','Subcategoria','Unidade','Saldo','Custo','Ativo']],
                     use_container_width=True,height=260,hide_index=True)
        pid=st.selectbox('Produto para extrato',allp.id.tolist(),key='timeline_all_pid_v114',
            format_func=lambda x:f"{allp.loc[allp.id==x,'Código'].iloc[0]} | "
                                 f"{allp.loc[allp.id==x,'Produto'].iloc[0]} | "
                                 f"{allp.loc[allp.id==x,'Categoria'].iloc[0]} | "
                                 f"{'ATIVO' if int(allp.loc[allp.id==x,'Ativo'].iloc[0] or 0)==1 else 'INATIVO'}")
        p=product_entity_summary(int(pid))
        k=st.columns(5)
        k[0].metric('Código',p['code'])
        k[1].metric('Produto',p['name'])
        k[2].metric('Categoria',p['category'])
        k[3].metric('Saldo atual',f"{balance(pid):,.3f} {p['unit']}")
        k[4].metric('Custo vigente',brl6(current_cost(pid)))

        with st.expander('✏️ Corrigir cadastro do produto / proteína',expanded=False):
            c=db();pr=c.execute("select * from products where id=?",(int(pid),)).fetchone();c.close()
            cp=controlled_protein_info(int(pid))
            e1,e2,e3=st.columns(3)
            ename=e1.text_input('Nome do produto',value=str(pr['name'] or ''),key=f'ext_item_name_{pid}')
            ecat=e2.text_input('Categoria',value=str(pr['category'] or ''),key=f'ext_item_cat_{pid}')
            eunit=e3.text_input('Unidade estoque',value=str(pr['unit'] or ''),key=f'ext_item_unit_{pid}')
            e4,e5=st.columns(2)
            ebrand=e4.text_input('Marca',value=str(pr['brand'] or ''),key=f'ext_item_brand_{pid}')
            esub=e5.text_input('Subcategoria',value=str(pr['subcategory'] or ''),key=f'ext_item_sub_{pid}')
            active=st.checkbox('Produto ativo',value=bool(int(pr['active'] if pr['active'] is not None else 1)),key=f'ext_item_active_{pid}')

            is_protein=st.checkbox('É uma proteína controlada',value=cp is not None,key=f'ext_item_isprotein_{pid}')
            protein_options=['Salmão','Lombo Atum','Atum','Camarão','Peixe Branco / Ceviche','Tilápia',
                             'Polvo','Lula','Haddock','Kani','Frango','Pork','Carne / Filé Mignon','Outra']
            if is_protein:
                oldfam=(cp or {}).get('protein_family','')
                idx=protein_options.index(oldfam) if oldfam in protein_options else len(protein_options)-1
                pfam=st.selectbox('Família da proteína',protein_options,index=idx,key=f'ext_item_pfam_{pid}')
            else:
                pfam=''
            confirm_prod=st.checkbox('Confirmo salvar a correção deste produto',key=f'ext_item_confirm_prod_{pid}')
            if st.button('SALVAR CORREÇÃO DO PRODUTO',type='primary',
                         disabled=not confirm_prod,key=f'ext_item_save_prod_{pid}'):
                c=db()
                try:
                    c.execute('BEGIN IMMEDIATE')
                    before=dict(pr)
                    c.execute("""update products set name=?,brand=?,category=?,subcategory=?,unit=?,active=? where id=?""",
                              (ename.strip(),ebrand.strip(),ecat.strip(),esub.strip(),eunit.strip(),int(active),int(pid)))
                    if is_protein:
                        c.execute("""insert into controlled_products(product_id,active,protein_family,updated_at)
                                     values(?,1,?,?)
                                     on conflict(product_id) do update set active=1,
                                     protein_family=excluded.protein_family,updated_at=excluded.updated_at""",
                                  (int(pid),pfam,datetime.now().isoformat(timespec='seconds')))
                    elif cp:
                        c.execute("update controlled_products set active=0,updated_at=? where product_id=?",
                                  (datetime.now().isoformat(timespec='seconds'),int(pid)))
                    after=dict(c.execute("select * from products where id=?",(int(pid),)).fetchone())
                    c.execute("""insert into correction_audit(event_date,module,record_id,action,before_json,after_json)
                                 values(?,?,?,?,?,?)""",
                              (datetime.now().isoformat(timespec='seconds'),'EXTRATO ITEM',str(pid),
                               'CORRIGIR PRODUTO/PROTEÍNA',json.dumps(before,ensure_ascii=False),
                               json.dumps({'product':after,'protein_family':pfam if is_protein else None},ensure_ascii=False)))
                    c.commit();clear_data_cache()
                    set_flash('Produto/proteína corrigido no extrato.','success');st.rerun()
                except Exception as ex:
                    c.rollback();st.error(str(ex))
                finally:c.close()

        df=item_timeline(int(pid))
        if df.empty:
            st.info('Ainda não há movimentações para este produto.')
        else:
            f1,f2,f3=st.columns([2,2,1])
            types=f1.multiselect('Filtrar eventos',sorted(df.Tipo.dropna().unique().tolist()),key=f'timeline_types_{pid}')
            search=f2.text_input('Pesquisar NF / fornecedor / referência / observação',key=f'timeline_ref_search_{pid}')
            only_nf=f3.checkbox('Só eventos com NF',value=False,key=f'timeline_only_nf_{pid}')
            view=df.copy()
            if types:view=view[view.Tipo.isin(types)]
            if only_nf:view=view[view['Nota ID'].notna()]
            if search:
                qq=search.lower()
                view=view[view.apply(lambda r:qq in (
                    str(r['NF'])+' '+str(r['Fornecedor'])+' '+str(r['Referência'])+' '+str(r['Observações'])
                ).lower(),axis=1)]
            show=view.copy()
            show['Custo']=show.Custo.map(brl6);show['Valor']=show.Valor.map(brl)
            st.dataframe(show,use_container_width=True,height=520,hide_index=True)

            movchart=view[view['Saldo Acumulado'].notna()].copy()
            if not movchart.empty:
                st.subheader('Evolução do saldo')
                movchart['Evento']=range(1,len(movchart)+1)
                st.line_chart(movchart.set_index('Evento')['Saldo Acumulado'])
            export_buttons(show,f"EXTRATO_ITEM_{p['code']}",'timelineexp_v114')

            nfrows=view[view['Nota ID'].notna()].copy()
            if not nfrows.empty:
                st.divider()
                st.subheader('🧾 Corrigir Nota Fiscal diretamente deste extrato')
                nfopts=sorted(set(int(x) for x in nfrows['Nota ID'].dropna().tolist()))
                c=db()
                nfmeta=pd.read_sql_query("""select i.id,i.number NF,i.issue_date 'Data NF',i.status Status,
                    s.legal_name Fornecedor from invoices i left join suppliers s on s.id=i.supplier_id
                    where i.id in ("""+','.join('?' for _ in nfopts)+") order by i.issue_date desc,i.id desc",
                    c,params=nfopts)
                c.close()
                nfid=st.selectbox('NF para corrigir',nfopts,key=f'ext_item_nf_correct_{pid}',
                    format_func=lambda x:f"NF {nfmeta.loc[nfmeta.id==x,'NF'].iloc[0]} | "
                                         f"{nfmeta.loc[nfmeta.id==x,'Data NF'].iloc[0]} | "
                                         f"{nfmeta.loc[nfmeta.id==x,'Fornecedor'].iloc[0]} | "
                                         f"{nfmeta.loc[nfmeta.id==x,'Status'].iloc[0]}")
                nfstatus=str(nfmeta.loc[nfmeta.id==nfid,'Status'].iloc[0]).upper()
                if nfstatus=='ENTRADA':
                    st.warning('Esta NF já movimentou estoque. Para editar com segurança, o sistema precisa reabri-la e estornar esta entrada antes da correção.')
                    confirm_nf=st.checkbox('Confirmo reabrir/estornar esta NF para corrigir',key=f'ext_item_nf_confirm_{pid}_{nfid}')
                    if st.button('REABRIR NF E IR PARA CORREÇÃO',type='primary',
                                 disabled=not confirm_nf,key=f'ext_item_nf_reopen_{pid}_{nfid}'):
                        try:
                            reopen_invoice(int(nfid))
                            st.session_state['open_invoice_id']=int(nfid)
                            st.session_state['_goto_page']='Notas / XML'
                            set_flash('NF reaberta com estorno da entrada. Corrija os itens e confirme a entrada novamente.','success')
                            st.rerun()
                        except Exception as ex:st.error(str(ex))
                else:
                    if st.button('ABRIR NF PARA CORREÇÃO',type='primary',key=f'ext_item_nf_open_{pid}_{nfid}'):
                        st.session_state['open_invoice_id']=int(nfid)
                        st.session_state['_focus_invoice_editor']=int(nfid)
                        st.session_state['_goto_page']='Notas / XML'
                        st.rerun()

elif page=='Extrato de Custos':
    st.title('Extrato de Custos — Crítico por NF')
    st.caption('Todos os produtos de todas as categorias, inclusive inativos. O sistema compara cada custo fiscal com o custo anterior e com a mediana das 5 entradas anteriores para sinalizar possíveis erros de NF.')

    q=st.text_input('🔎 Pesquisar produto / categoria / barcode',key='cost_all_search_v114')
    allp=all_products_df(q,10000)
    cats=sorted(allp['Categoria'].fillna('').astype(str).unique().tolist()) if not allp.empty else []
    selected_cats=st.multiselect('Filtrar categorias (vazio = TODAS)',cats,key='cost_all_cats_v114')
    if selected_cats and not allp.empty:
        allp=allp[allp['Categoria'].astype(str).isin(selected_cats)]
    st.caption(f'{len(allp)} produto(s) disponível(is) no filtro atual.')

    if allp.empty:
        st.warning('Nenhum produto encontrado.')
    else:
        st.dataframe(allp[['Código','Produto','Marca','Categoria','Subcategoria','Unidade','Saldo','Custo','Ativo']],
                     use_container_width=True,height=250,hide_index=True)
        pid=st.selectbox('Produto para análise de custo',allp.id.tolist(),key='cost_all_pid_v114',
            format_func=lambda x:f"{allp.loc[allp.id==x,'Código'].iloc[0]} | "
                                 f"{allp.loc[allp.id==x,'Produto'].iloc[0]} | "
                                 f"{allp.loc[allp.id==x,'Categoria'].iloc[0]}")
        c=db();pr=c.execute("select code,name,category,unit from products where id=?",(int(pid),)).fetchone();c.close()
        c1,c2,c3,c4=st.columns(4)
        c1.metric('Código',pr['code']);c2.metric('Produto',pr['name'])
        c3.metric('Categoria',pr['category']);c4.metric('Custo vigente',brl6(current_cost(pid)))

        with st.expander('🧬 Corrigir classificação da proteína / categoria',expanded=False):
            cp=controlled_protein_info(int(pid))
            pc1,pc2=st.columns(2)
            pcat=pc1.text_input('Categoria do produto',value=str(pr['category'] or ''),key=f'cost_prod_cat_{pid}')
            isprotein=pc2.checkbox('É proteína controlada',value=cp is not None,key=f'cost_isprotein_{pid}')
            protein_options=['Salmão','Lombo Atum','Atum','Camarão','Peixe Branco / Ceviche','Tilápia',
                             'Polvo','Lula','Haddock','Kani','Frango','Pork','Carne / Filé Mignon','Outra']
            pfam=''
            if isprotein:
                oldfam=(cp or {}).get('protein_family','')
                pidx=protein_options.index(oldfam) if oldfam in protein_options else len(protein_options)-1
                pfam=st.selectbox('Família da proteína',protein_options,index=pidx,key=f'cost_pfam_{pid}')
            pcfm=st.checkbox('Confirmo a correção de classificação',key=f'cost_pclass_confirm_{pid}')
            if st.button('SALVAR CLASSIFICAÇÃO',disabled=not pcfm,key=f'cost_pclass_save_{pid}'):
                c=db()
                try:
                    c.execute('BEGIN IMMEDIATE')
                    before={'category':pr['category'],'controlled_protein':cp}
                    c.execute("update products set category=? where id=?",(pcat.strip(),int(pid)))
                    if isprotein:
                        c.execute("insert into controlled_products(product_id,active,protein_family,updated_at) "
                                  "values(?,1,?,?) "
                                  "on conflict(product_id) do update set active=1, "
                                  "protein_family=excluded.protein_family,updated_at=excluded.updated_at",
                                  (int(pid),pfam,datetime.now().isoformat(timespec='seconds')))
                    elif cp:
                        c.execute("update controlled_products set active=0,updated_at=? where product_id=?",
                                  (datetime.now().isoformat(timespec='seconds'),int(pid)))
                    c.execute("insert into correction_audit(event_date,module,record_id,action,before_json,after_json) "
                              "values(?,?,?,?,?,?)",
                              (datetime.now().isoformat(timespec='seconds'),'EXTRATO CUSTOS',str(pid),
                               'CORRIGIR CLASSIFICAÇÃO PROTEÍNA',
                               json.dumps(before,ensure_ascii=False),
                               json.dumps({'category':pcat.strip(),'protein_family':pfam if isprotein else None},ensure_ascii=False)))
                    c.commit();clear_data_cache()
                    set_flash('Classificação do produto/proteína corrigida.','success');st.rerun()
                except Exception as ex:
                    c.rollback();st.error(str(ex))
                finally:c.close()

        cfg=settings_dict()
        try:wdefault=float(cfg.get('cost_alert_warning_pct','25') or 25)
        except Exception:wdefault=25.0
        try:cdefault=float(cfg.get('cost_alert_critical_pct','50') or 50)
        except Exception:cdefault=50.0
        with st.expander('⚙️ Limites do alerta crítico de custos'):
            w1,w2=st.columns(2)
            warning_pct=w1.number_input('ATENÇÃO a partir de variação absoluta (%)',min_value=1.0,max_value=5000.0,
                                        value=float(wdefault),step=1.0,key='cost_warn_pct_v114')
            critical_pct=w2.number_input('CRÍTICO a partir de variação absoluta (%)',min_value=float(warning_pct),
                                          max_value=10000.0,value=max(float(cdefault),float(warning_pct)),
                                          step=1.0,key='cost_crit_pct_v114')
            if st.button('SALVAR LIMITES DE ALERTA',key='save_cost_alert_limits_v114'):
                c=db()
                for k,v in [('cost_alert_warning_pct',warning_pct),('cost_alert_critical_pct',critical_pct)]:
                    c.execute("""insert into settings(key,value) values(?,?)
                                 on conflict(key) do update set value=excluded.value""",(k,str(float(v))))
                c.commit();c.close();set_flash('Limites de alerta de custo salvos.','success');st.rerun()

        hist=product_invoice_cost_history(int(pid))
        if hist.empty:
            st.info('Este produto ainda não possui itens de nota fiscal associados.')
        else:
            critical_n=int((hist['Alerta de Custo']=='CRÍTICO').sum())
            warning_n=int((hist['Alerta de Custo']=='ATENÇÃO').sum())
            k1,k2,k3=st.columns(3)
            k1.metric('Entradas fiscais',len(hist))
            k2.metric('Alertas críticos',critical_n)
            k3.metric('Alertas atenção',warning_n)

            if critical_n:
                st.error(f'Foram encontradas {critical_n} entrada(s) com variação extrema de custo. Revise antes de confiar no CMV.')
            elif warning_n:
                st.warning(f'Foram encontradas {warning_n} entrada(s) com variação relevante de custo.')
            else:
                st.success('Nenhuma variação fiscal acima dos limites configurados.')

            view=hist.copy()
            only_alert=st.checkbox('Mostrar somente ATENÇÃO / CRÍTICO',value=False,key=f'cost_only_alert_{pid}')
            if only_alert:view=view[view['Alerta de Custo']!='OK']
            show=view.copy()
            for col in ['Custo Unitário','Custo Anterior','Mediana 5 Anteriores']:
                show[col]=show[col].apply(lambda x:'' if pd.isna(x) else brl6(x))
            show['Valor Item']=show['Valor Item'].map(brl)
            for col in ['Variação Anterior %','Variação Mediana %']:
                show[col]=show[col].apply(lambda x:'' if pd.isna(x) else f'{x:+.2f}%')
            st.dataframe(show,use_container_width=True,height=560,hide_index=True)
            export_buttons(show,f"EXTRATO_CUSTOS_FISCAIS_{pr['code']}",'cost_nf_exp_v114')

            chart=hist[['Data NF','Custo Unitário']].copy()
            chart['Data NF']=pd.to_datetime(chart['Data NF'],errors='coerce')
            chart=chart.dropna(subset=['Data NF']).sort_values('Data NF')
            if not chart.empty:
                st.subheader('Evolução do custo unitário fiscal')
                st.line_chart(chart.set_index('Data NF')['Custo Unitário'])

            st.divider()
            st.subheader('🧾 Corrigir Nota Fiscal diretamente deste extrato')
            nfopts=hist['Nota ID'].dropna().astype(int).unique().tolist()
            if nfopts:
                nfid=st.selectbox('NF para abrir/corrigir',nfopts,key=f'cost_nf_correct_{pid}',
                    format_func=lambda x:f"NF {hist.loc[hist['Nota ID']==x,'NF'].iloc[0]} | "
                                         f"{hist.loc[hist['Nota ID']==x,'Data NF'].iloc[0]} | "
                                         f"{hist.loc[hist['Nota ID']==x,'Fornecedor'].iloc[0]} | "
                                         f"{hist.loc[hist['Nota ID']==x,'Alerta de Custo'].iloc[0]}")
                nfstatus=str(hist.loc[hist['Nota ID']==nfid,'Status NF'].iloc[0]).upper()
                selected_alert=str(hist.loc[hist['Nota ID']==nfid,'Alerta de Custo'].iloc[0])
                if selected_alert in ('ATENÇÃO','CRÍTICO'):
                    st.warning(hist.loc[hist['Nota ID']==nfid,'Diagnóstico'].iloc[0])
                if nfstatus=='ENTRADA':
                    confirm_nf=st.checkbox('Confirmo reabrir esta NF e estornar a entrada para corrigir',
                                           key=f'cost_nf_confirm_{pid}_{nfid}')
                    if st.button('REABRIR NF E CORRIGIR',type='primary',
                                 disabled=not confirm_nf,key=f'cost_nf_reopen_{pid}_{nfid}'):
                        try:
                            reopen_invoice(int(nfid))
                            st.session_state['open_invoice_id']=int(nfid)
                            st.session_state['_focus_invoice_editor']=int(nfid)
                            st.session_state['_goto_page']='Notas / XML'
                            set_flash('NF reaberta e selecionada automaticamente na Entrada de Notas para edição.','success')
                            st.rerun()
                        except Exception as ex:st.error(str(ex))
                else:
                    if st.button('ABRIR NF PARA CORREÇÃO',type='primary',key=f'cost_nf_open_{pid}_{nfid}'):
                        st.session_state['open_invoice_id']=int(nfid)
                        st.session_state['_focus_invoice_editor']=int(nfid)
                        st.session_state['_goto_page']='Notas / XML'
                        st.rerun()

        manual=product_noninvoice_cost_history(int(pid))
        if not manual.empty:
            with st.expander('Outros ajustes de custo (inventário/manual/configuração)'):
                mshow=manual.copy()
                mshow['Custo']=pd.to_numeric(mshow['Custo'],errors='coerce').fillna(0).map(brl6)
                st.dataframe(mshow,use_container_width=True,hide_index=True)

        with st.expander('✏️ Corrigir custo mestre do produto',expanded=False):
            st.warning('Use esta opção somente para corrigir o custo vigente fora de uma NF. Se o erro veio de uma NF, corrija a própria nota acima.')
            new_cost=st.number_input('Novo custo mestre',min_value=0.000001,value=max(float(current_cost(pid)),0.000001),
                                     step=0.001,format=num_format(),key=f'cost_master_fix_{pid}')
            reason=st.text_input('Motivo obrigatório',key=f'cost_master_reason_{pid}')
            cfm=st.checkbox('Confirmo a correção manual do custo mestre',key=f'cost_master_confirm_{pid}')
            if st.button('CORRIGIR CUSTO MESTRE',disabled=(not cfm or not reason.strip()),
                         key=f'cost_master_save_{pid}'):
                try:
                    old=current_cost(pid)
                    set_master_cost(int(pid),round_entry(new_cost),reason.strip(),
                                    source='CORREÇÃO EXTRATO CUSTOS',reference=f'Produto {pr["code"]}')
                    c=db()
                    c.execute("""insert into correction_audit(event_date,module,record_id,action,before_json,after_json)
                                 values(?,?,?,?,?,?)""",
                              (datetime.now().isoformat(timespec='seconds'),'EXTRATO CUSTOS',str(pid),
                               'CORRIGIR CUSTO MESTRE',
                               json.dumps({'cost':old},ensure_ascii=False),
                               json.dumps({'cost':round_entry(new_cost),'reason':reason},ensure_ascii=False)))
                    c.commit();c.close()
                    set_flash('Custo mestre corrigido e registrado no histórico.','success');st.rerun()
                except Exception as ex:st.error(str(ex))


elif page=='Custos Médios':
    standard_template_button('Custos Médios','cost_tpl')
    with st.expander('IMPORTAR PLANILHA PADRÃO XLSX'):
        _up=st.file_uploader('Arquivo XLSX',type=['xlsx'],key='imp_cost_tpl')
        if _up and st.button('PROCESSAR IMPORTAÇÃO',key='btn_imp_cost_tpl'):
            _n,_e=import_standard_costs(_up);confirm_success(f'{_n} registros processados.')
            if _e:st.warning('\\n'.join(_e[:30]))
            st.rerun()
    st.title('Central de Custos Médios')
    st.info('Regra V11.5.1: o custo vigente é a média ponderada das ENTRADAS do trimestre civil mais recente com compras. O custo ajustado manualmente funciona apenas como fallback para produtos sem entrada válida.')
    allp=products('');cats=sorted(allp.Categoria.unique().tolist());sc=st.multiselect('Filtrar categoria(s)',cats,key='costcats')
    if sc:allp=allp[allp.Categoria.isin(sc)]
    q=st.text_input('🔎 Filtrar nome/código',key='costq')
    if q:allp=allp[allp.apply(lambda r:q.lower() in (str(r.Código)+' '+r.Produto+' '+r.Categoria).lower(),axis=1)]
    rows=[]
    qstart,qend=quarter_bounds(date.today())
    for _,r in allp.iterrows():
        pid=int(r.id)
        rows.append([pid,r.Código,r.Produto,r.Categoria,periodic_quarter_cost(pid,date.today()),
                     last_cost(pid),master_cost(pid),current_cost(pid),
                     f'{qstart.strftime("%d/%m/%Y")} a {qend.strftime("%d/%m/%Y")}'])
    ed=pd.DataFrame(rows,columns=['ID','Código','Produto','Categoria','Média Ponderada Trimestre',
                                  'Último Custo','Custo Manual/Fallback','Custo Vigente','Período'])
    edited=st.data_editor(
        ed,hide_index=True,use_container_width=True,height=520,
        disabled=['ID','Código','Produto','Categoria','Média Ponderada Trimestre','Último Custo','Custo Vigente','Período'],
        column_config={'Custo Manual/Fallback':st.column_config.NumberColumn(min_value=0.0,format='R$ '+num_format())}
    )
    if st.button('Salvar custos ajustados',type='primary'):
        n=0
        for _,r in edited.iterrows():
            val=float(r['Custo Manual/Fallback'] or 0)
            if val>0:set_master_cost(int(r.ID),val);n+=1
        app_log('Custos Médios','Ajuste manual',f'{n} produtos');confirm_success(f'{n} custos atualizados.');st.rerun()
    model=edited[['Código','Produto','Categoria','Custo Manual/Fallback']].copy();model=model.rename(columns={'Custo Manual/Fallback':'Custo Ajustado'});buf=io.BytesIO();model.to_excel(buf,index=False);st.download_button('Exportar planilha de ajuste de custos',buf.getvalue(),'AJUSTE_CUSTOS.xlsx')
    upc=st.file_uploader('Importar ajustes de custos XLS/XLSX',type=['xls','xlsx'],key='cost_import')
    if upc and st.button('Aplicar arquivo de custos'):
        x=pd.read_excel(upc);c=db();n=0;errs=[]
        for ix,r in x.iterrows():
            try:
                code=int(r['Código']);val=_money(r['Custo Ajustado']);pr=c.execute('select id from products where code=?',(code,)).fetchone()
                if not pr or val<=0:raise ValueError('Código inexistente ou custo zero')
                c.execute("insert into cost_master(product_id,current_cost,updated_at,notes) values(?,?,?,?) on conflict(product_id) do update set current_cost=excluded.current_cost,updated_at=excluded.updated_at,notes=excluded.notes",(pr['id'],val,datetime.now().isoformat(),'Importação Excel'));n+=1
            except Exception as e:errs.append(f'Linha {ix+2}: {e}')
        c.commit();c.close();app_log('Custos Médios','Importação Excel',f'{n} produtos');confirm_success(f'{n} custos aplicados.');
        if errs:st.warning('\n'.join(errs[:20]))

elif page=='Inventário':
    st.title('Inventário')
    st.info('Regra: inventários podem ser reabertos, alterados e ter itens excluídos. Ao reabrir, os ajustes do inventário são desfeitos antes da nova edição.')
    standard_template_button('Inventário','inv_tpl')
    st.caption('Inventários possuem ciclo ABERTO → FECHADO. Somente inventários FECHADOS entram no CMV e ajustam o estoque.')
    allp=products('');cats=sorted(allp.Categoria.dropna().unique().tolist())

    c=db()
    sessions=pd.read_sql_query("""select id ID,inventory_date Data,name Nome,status Status,
        created_at Criado,closed_at Fechado,notes Observações
        from inventory_sessions order by id desc""",c)
    c.close()

    t0,t1,t2,t3=st.tabs(['Gerenciar Inventários','Contagem manual','Planilha de contagem','Histórico'])

    with t0:
        st.subheader('Abrir / Fechar / Reabrir / Excluir')
        if not sessions.empty:
            st.dataframe(sessions,use_container_width=True,height=280)
            sid_manage=st.selectbox('Inventário',sessions.ID.tolist(),key='sid_manage',
                format_func=lambda x:f"#{x} | {sessions.loc[sessions.ID==x,'Data'].iloc[0]} | {sessions.loc[sessions.ID==x,'Nome'].iloc[0]} | {sessions.loc[sessions.ID==x,'Status'].iloc[0]}")
            srow=sessions[sessions.ID==sid_manage].iloc[0]
            g1,g2,g3=st.columns(3)
            if str(srow['Status']).upper()=='ABERTO':
                if g1.button('FECHAR INVENTÁRIO',type='primary'):
                    close_inventory_session(int(sid_manage));confirm_success('Inventário fechado. Estoque e CMV atualizados.');st.rerun()
            else:
                if g1.button('REABRIR INVENTÁRIO'):
                    reopen_inventory_session(int(sid_manage));confirm_success('Inventário reaberto. Ajuste anterior foi desfeito.');st.rerun()
            if g2.button('ABRIR PARA ALTERAR'):
                st.session_state['active_inventory_session']=int(sid_manage);confirm_success('Inventário selecionado para edição.')
            conf=st.checkbox('Confirmo exclusão deste inventário',key='inv_delete_confirm')
            if g3.button('EXCLUIR INVENTÁRIO',disabled=not conf):
                delete_inventory_session(int(sid_manage));st.session_state.pop('active_inventory_session',None);confirm_success('Inventário excluído e efeitos revertidos.');st.rerun()
        else:
            st.info('Nenhum inventário controlado criado ainda.')

        st.divider()
        st.subheader('Criar novo inventário')
        ni1,ni2=st.columns(2)
        nd=ni1.date_input('Data do inventário',date.today(),key='new_inv_date')
        nn=ni2.text_input('Nome',value=f"Inventário {date.today().strftime('%d/%m/%Y')}",key='new_inv_name')
        no=st.text_input('Observações',key='new_inv_notes')
        if st.button('CRIAR INVENTÁRIO ABERTO'):
            sid=create_inventory_session(nd,nn,no)
            st.session_state['active_inventory_session']=sid
            confirm_success(f'Inventário #{sid} criado e selecionado para edição.');st.rerun()

    active_sid=st.session_state.get('active_inventory_session')
    active=get_inventory_session(active_sid) if active_sid else None

    with t1:
        if not active or str(active['status']).upper()!='ABERTO':
            st.warning('Selecione ou crie um inventário ABERTO na aba Gerenciar Inventários.')
        else:
            confirm_success(f"Editando #{active_sid} | {active['name']} | Data {active['inventory_date']}")
            st.caption('Faça a contagem diretamente na tabela. A quantidade é editável; o custo do inventário é calculado automaticamente pela média ponderada das entradas do trimestre da data do inventário.')

            with st.expander('➕ Produto não existe? CADASTRAR NO ATO DO INVENTÁRIO'):
                np=st.text_input('Nome novo produto',key='inv_np_name');nb=st.text_input('Marca',key='inv_np_brand')
                a,b,cx=st.columns(3)
                nc=a.text_input('Categoria',key='inv_np_cat')
                ns=b.text_input('Subcategoria',key='inv_np_sub')
                nu=cx.selectbox('Unidade',['UN','KG','G','L','ML','CX','PCT'],key='inv_np_unit')
                extbc=st.text_input('Código de barras do fornecedor (quando houver)',key='inv_np_bar')
                initcost=st.number_input('Custo inicial / custo contado',min_value=0.0,format=num_format(),key='inv_np_cost')
                if st.button('CADASTRAR PRODUTO PARA ESTE INVENTÁRIO') and np and nc:
                    c=db();code=c.execute('select coalesce(max(code),100000)+1 x from products').fetchone()['x'];ib=ean13(code)
                    newpid=c.execute('insert into products(code,internal_barcode,name,brand,category,subcategory,unit) values(?,?,?,?,?,?,?)',(code,ib,np,nb,nc,ns,nu)).lastrowid
                    c.execute('insert or ignore into product_barcodes(product_id,barcode,description) values(?,?,?)',(newpid,ib,'Código interno'))
                    if extbc:c.execute('insert or ignore into product_barcodes(product_id,barcode,description) values(?,?,?)',(newpid,extbc,'Fornecedor'))
                    c.commit();c.close();clear_data_cache()
                    if initcost>0:set_master_cost(newpid,initcost,f'Custo criado no Inventário #{active_sid}','INVENTÁRIO',f'Inventário #{active_sid}')
                    confirm_success(f'Produto {code} cadastrado.');st.rerun()

            c=db()
            existing=pd.read_sql_query("""select product_id,counted_qty,avg_cost_3m,notes
                from inventory where session_id=?""",c,params=[active_sid])
            c.close()

            base=product_grid_base()
            cats=sorted(base['Categoria'].dropna().unique().tolist()) if not base.empty else []
            sc=st.multiselect('Filtrar categoria(s)',cats,key='inv_grid_cats')
            search=st.text_input('🔎 Buscar produto',key='inv_grid_search')
            if sc:
                base=base[base['Categoria'].isin(sc)]
            if search:
                ss=search.lower()
                base=base[base.apply(lambda r:ss in (str(r['Código'])+' '+str(r['Produto'])+' '+str(r['Categoria'])).lower(),axis=1)]

            edited=editable_count_grid(
                base,existing,'Quantidade Contada','Custo Unitário',
                key=f'inv_grid_{active_sid}',lock_cost=True,
                cost_ref=pd.to_datetime(active['inventory_date']).date()
            )

            if st.button('SALVAR TODA A CONTAGEM',type='primary'):
                n=0;errs=[]
                for _,r in edited.iterrows():
                    try:
                        qty=float(r['Quantidade Contada'] or 0)
                        pid=int(r['id'])
                        if qty<=0:
                            continue
                        cost=float(current_cost(pid,pd.to_datetime(active['inventory_date']).date()) or 0)
                        if cost<=0:
                            raise ValueError(f"Custo médio trimestral inválido para {r['Produto']}")
                        save_inventory_count(int(active_sid),pid,qty,cost,str(r.get('Observações','')))
                        n+=1
                    except Exception as ex:
                        errs.append(str(ex))
                confirm_success(f'{n} produtos gravados/atualizados.')
                if errs:st.warning('\n'.join(errs[:20]))
                st.rerun()

            c=db()
            current_rows=pd.read_sql_query("""select p.category Categoria,p.subcategory Subcategoria,p.code Código,p.name Produto,
                i.counted_qty Contagem,i.avg_cost_3m Custo,i.total_value Valor,i.notes Observações
                from inventory i join products p on p.id=i.product_id
                where i.session_id=? order by p.category,p.name""",c,params=[active_sid])
            c.close()
            if not current_rows.empty:
                st.subheader('Itens já contados')
                st.dataframe(current_rows,use_container_width=True,height=320)
                export_buttons(current_rows,f'INVENTARIO_{active_sid}_ABERTO','inv_open_export')
                c=db()
                _delinv=pd.read_sql_query("""select i.product_id,p.code Código,p.name Produto,i.counted_qty Quantidade,i.avg_cost_3m Custo
                    from inventory i join products p on p.id=i.product_id where i.session_id=? order by p.name""",c,params=[active_sid])
                c.close()
                if not _delinv.empty:
                    _pid_del=st.selectbox('Excluir item do inventário',_delinv.product_id.tolist(),key=f'inv_del_item_{active_sid}',
                        format_func=lambda x:f"{int(_delinv.loc[_delinv.product_id==x,'Código'].iloc[0])} | {_delinv.loc[_delinv.product_id==x,'Produto'].iloc[0]}")
                    if st.button('🗑️ EXCLUIR ITEM DO INVENTÁRIO',key=f'inv_del_btn_{active_sid}'):
                        delete_inventory_item_safe(int(active_sid),int(_pid_del));confirm_success('Item excluído.');st.rerun()

    with t2:
        st.subheader('Exportar planilha para contagem')
        if not active or str(active['status']).upper()!='ABERTO':
            st.warning('Selecione um inventário ABERTO para exportar/importar a planilha.')
        else:
            mode=st.radio('Conteúdo',['GERAL - todos os itens','POR CATEGORIA - uma ou mais'],horizontal=True,key='inv_sheet_mode')
            chosen=st.multiselect('Categorias',cats,key='inv_sheet_cats') if mode.startswith('POR') else []
            exp=allp.copy()
            if chosen:exp=exp[exp.Categoria.isin(chosen)]
            if mode.startswith('POR') and not chosen:exp=exp.iloc[0:0]
            if not exp.empty:
                # Preenche contagens já existentes
                c=db();existing=pd.read_sql_query("select product_id,counted_qty,notes from inventory where session_id=?",c,params=[active_sid]);c.close()
                emap={int(r.product_id):(r.counted_qty,r.notes) for _,r in existing.iterrows()}
                sheet=pd.DataFrame({
                    'Inventário ID':[active_sid]*len(exp),
                    'Data Inventário':[active['inventory_date']]*len(exp),
                    'Categoria':exp.Categoria,'Subcategoria':exp.Subcategoria,
                    'Código Produto':exp.Código.astype(int),'Nome Produto':exp.Produto,'Unidade':exp.Unidade,
                    'Quantidade Contada':[emap.get(int(pid),(None,''))[0] for pid in exp.id],
                    'Observações':[emap.get(int(pid),(None,''))[1] for pid in exp.id]
                })
                confirm_success(f'{len(sheet)} itens incluídos na planilha.')
                export_buttons(sheet,f'INVENTARIO_{active_sid}_CONTAGEM','inv_sheet_export')
                st.dataframe(sheet.head(100),use_container_width=True,height=300)

            st.divider()
            up=st.file_uploader('Importar planilha preenchida',type=['xls','xlsx'],key='inv_import_new')
            if up and st.button('IMPORTAR / ATUALIZAR CONTAGENS'):
                x=pd.read_excel(up);n=0;errs=[]
                for ix,r in x.iterrows():
                    try:
                        code=int(r['Código Produto'])
                        c=db();pr=c.execute('select id from products where code=?',(code,)).fetchone();c.close()
                        if not pr:raise ValueError('produto não encontrado')
                        qv=r.get('Quantidade Contada')
                        if pd.isna(qv) or str(qv).strip()=='':continue
                        qty=float(str(qv).replace(',','.'))
                        cost=current_cost(pr['id'],pd.to_datetime(active['inventory_date']).date())
                        if cost<=0:raise ValueError('custo zero')
                        save_inventory_count(int(active_sid),int(pr['id']),qty,cost,str(r.get('Observações','')))
                        n+=1
                    except Exception as ex:errs.append(f'Linha {ix+2}: {ex}')
                confirm_success(f'{n} contagens gravadas/atualizadas.')
                if errs:st.warning('\n'.join(errs[:30]))
                st.rerun()

    with t3:
        c=db()
        h=pd.read_sql_query("""select coalesce(s.id,0) 'Inventário ID',coalesce(s.name,'LEGADO') Inventário,
            coalesce(s.status,'FECHADO') Status,i.inventory_date Data,p.category Categoria,p.subcategory Subcategoria,
            p.code Código,p.name Produto,i.counted_qty Contagem,i.avg_cost_3m Custo,i.total_value Valor,i.notes Observações
            from inventory i
            left join inventory_sessions s on s.id=i.session_id
            join products p on p.id=i.product_id
            order by i.inventory_date desc,p.category,p.name""",c)
        c.close()
        st.dataframe(h,use_container_width=True,height=520)
        export_buttons(h,'HISTORICO_INVENTARIO','invhist')

elif page=='Contagem & Compras':
    standard_template_button('Contagem & Compras','count_tpl')

    with st.expander('📋 CONTAGEM RÁPIDA EM TABELA',expanded=True):
        base=product_grid_base()
        cats=sorted(base['Categoria'].dropna().unique().tolist()) if not base.empty else []
        sc=st.multiselect('Categoria(s)',cats,key='quick_count_cats')
        if sc:base=base[base['Categoria'].isin(sc)]
        qdate=st.date_input('Data da contagem',date.today(),key='quick_count_date')
        qdf=base.copy()
        qdf['Quantidade Contada']=0.0
        qdf['Estoque Alvo']=0.0
        qdf['Observações']=''
        edited=st.data_editor(qdf,use_container_width=True,hide_index=True,height=450,
            disabled=['id','Código','Produto','Categoria','Subcategoria','Unidade'],
            column_config={
                'Quantidade Contada':st.column_config.NumberColumn(min_value=0.0,step=0.001,format=num_format()),
                'Estoque Alvo':st.column_config.NumberColumn(min_value=0.0,step=0.001,format=num_format())
            },key='quick_count_grid')
        if st.button('SALVAR CONTAGEM DA TABELA',key='save_quick_count'):
            c=db();n=0
            for _,r in edited.iterrows():
                q=float(r['Quantidade Contada'] or 0);target=float(r['Estoque Alvo'] or 0)
                if q<=0 and target<=0:continue
                c.execute("""insert into counts(count_date,product_id,counted_qty,target_stock,suggested_qty,notes)
                    values(?,?,?,?,?,?)""",(str(qdate),int(r['id']),q,target,max(0,target-q),str(r.get('Observações',''))))
                n+=1
            c.commit();c.close()
            confirm_success(f'{n} linhas gravadas.');st.rerun()
    st.title('Contagem e Compras Programadas')
    allp=products('');cats=sorted(allp.Categoria.unique().tolist())
    t1,t2=st.tabs(['Programação e contagem','Planilha padrão importação/exportação'])
    with t1:
        sc=st.multiselect('Categoria(s) para localizar item',cats,key='pcats');pid=product_picker_by_categories('purchasecfg',sc);day=st.selectbox('Dia de pedido',DAYS);group=st.text_input('Grupo / fornecedor / rota','OPERADOR LOGÍSTICO HOMOLOGADO');target=st.number_input('Estoque alvo',min_value=0.0);minimum=st.number_input('Estoque mínimo',min_value=0.0)
        if pid and st.button('Salvar programação'):
            c=db();c.execute("""insert into purchase_schedule(product_id,order_day,supply_group,frequency,target_stock,min_stock,notes) values(?,?,?,?,?,?,?) on conflict(product_id,order_day,supply_group) do update set target_stock=excluded.target_stock,min_stock=excluded.min_stock""",(pid,day,group,'SEMANAL',target,minimum,''));c.commit();c.close();st.rerun()
        c=db();sched=pd.read_sql_query("""select ps.id,p.category Categoria,p.subcategory Subcategoria,p.code Código,p.name Produto,p.unit Unidade,ps.order_day 'Dia Pedido',ps.supply_group Grupo,ps.target_stock 'Estoque Alvo',ps.min_stock 'Estoque Mínimo' from purchase_schedule ps join products p on p.id=ps.product_id where ps.active=1 order by ps.order_day,ps.supply_group,p.category,p.name""",c);c.close();st.dataframe(sched,use_container_width=True,height=360)
    with t2:
        template('MODELO_CONTAGEM_COMPRA.xlsx')
        c=db();sched=pd.read_sql_query("""select p.category Categoria,p.subcategory Subcategoria,ps.order_day 'Dia Pedido',ps.supply_group 'Grupo Abastecimento',p.code 'Código Produto',p.name Produto,p.unit Unidade,ps.target_stock 'Estoque Alvo',ps.min_stock 'Estoque Mínimo' from purchase_schedule ps join products p on p.id=ps.product_id where ps.active=1 order by ps.order_day,ps.supply_group,p.category,p.name""",c);c.close()
        if not sched.empty:
            sched.insert(0,'Data',date.today());sched['Saldo Contado']='';sched['Sugestão Compra']='';sched['Observações']=''
            buf=io.BytesIO();sched.to_excel(buf,index=False);st.download_button('EXPORTAR PLANILHA PADRÃO DE CONTAGEM/COMPRA',buf.getvalue(),'CONTAGEM_COMPRAS_PADRAO.xlsx',type='primary');export_buttons(sched,'CONTAGEM_COMPRAS_PADRAO','countbuy')
        up=st.file_uploader('IMPORTAR PLANILHA DE CONTAGEM/COMPRA',type=['xls','xlsx'],key='purchase_count_import')
        if up and st.button('Processar planilha de contagem'):
            x=pd.read_excel(up);c=db();n=0;errs=[]
            for ix,r in x.iterrows():
                try:
                    code=int(r['Código Produto']);pr=c.execute('select id from products where code=?',(code,)).fetchone();
                    if not pr:raise ValueError('produto inexistente')
                    counted=float(str(r.get('Saldo Contado',0)).replace(',','.'));target=float(str(r.get('Estoque Alvo',0)).replace(',','.'));suggest=max(0,target-counted);dt=_date_br(r['Data'])
                    c.execute('insert into counts(count_date,product_id,order_day,supply_group,counted_qty,target_stock,suggested_qty,notes) values(?,?,?,?,?,?,?,?)',(str(dt),pr['id'],str(r.get('Dia Pedido','')),str(r.get('Grupo Abastecimento','')),counted,target,suggest,str(r.get('Observações',''))));n+=1
                except Exception as e:errs.append(f'Linha {ix+2}: {e}')
            c.commit();c.close();confirm_success(f'{n} linhas importadas.');
            if errs:st.warning('\n'.join(errs[:30]))

elif page=='Cotações':
    standard_template_button('Cotações','quote_tpl')
    st.title('Cotações e Fornecedores Mais em Conta')
    t1,t2,t3=st.tabs(['Cotações atuais','Melhor proposta','Histórico real de compras'])
    with t1:
        template('MODELO_COTACOES.xlsx');up=st.file_uploader('Importar cotações XLS/XLSX',type=['xls','xlsx'])
        if up and st.button('Importar cotações'):
            z=pd.read_excel(up);c=db();n=0;errs=[]
            try:
                c.execute('BEGIN IMMEDIATE')
                for ix,r in z.iterrows():
                    try:
                        code=int(r['Código Produto'])
                        p=c.execute('select id from products where code=?',(code,)).fetchone()
                        if not p: raise ValueError(f'Produto {code} não encontrado')
                        sid=supplier(str(r.get('Fornecedor CNPJ','')),str(r.get('Fornecedor','')),connection=c)
                        qty=_money(r.get('Quantidade',0));conv=_money(r.get('Fator Conversão',1)) or 1
                        price=_money(r.get('Preço Oferta',0));freight=_money(r.get('Frete',0));disc=_money(r.get('Desconto',0))
                        uc=(price+freight-disc)/(qty*conv) if qty*conv else 0
                        qdate=_date_br(r.get('Data'))
                        valid='' if pd.isna(r.get('Validade Oferta')) else str(_date_br(r.get('Validade Oferta')))
                        c.execute('''insert into quotes(quote_id,quote_date,product_id,supplier_id,qty,purchase_unit,conversion,offer_price,freight,discount,unit_cost,lead_days,valid_until,notes)
                                     values(?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                                  (str(r.get('ID Cotação','')),str(qdate),p['id'],sid,qty,str(r.get('Unidade Compra','')),conv,
                                   price,freight,disc,uc,int(_money(r.get('Prazo Dias',0))),valid,str(r.get('Observações',''))))
                        n+=1
                    except Exception as e:
                        errs.append(f'Linha {ix+2}: {e}')
                c.commit()
            except Exception:
                c.rollback()
                raise
            finally:
                c.close()
            app_log('Cotações','Importação',f'{n} propostas | {len(errs)} erros')
            if n: confirm_success(f'{n} propostas importadas.')
            if errs: st.warning('\n'.join(errs[:30]))
            if n: st.rerun()
        c=db();d=pd.read_sql_query("select q.quote_id Cotação,q.quote_date Data,p.category Categoria,p.name Produto,s.legal_name Fornecedor,q.qty Quantidade,q.purchase_unit 'UN Compra',q.conversion Conversão,q.offer_price Oferta,q.freight Frete,q.discount Desconto,q.unit_cost 'Custo Unitário',q.lead_days Prazo from quotes q join products p on p.id=q.product_id join suppliers s on s.id=q.supplier_id order by p.name,q.unit_cost",c);c.close();st.dataframe(d,use_container_width=True,height=420)
    with t2:
        c=db();d=pd.read_sql_query("select q.quote_date Data,p.category Categoria,p.name Produto,s.legal_name Fornecedor,q.unit_cost 'Custo Unitário',q.lead_days Prazo,q.valid_until Validade from quotes q join products p on p.id=q.product_id join suppliers s on s.id=q.supplier_id where q.unit_cost>0 order by p.name,q.unit_cost",c);c.close()
        if d.empty:st.info('Sem cotações registradas.')
        else:
            best=d.sort_values(['Produto','Custo Unitário']).groupby('Produto',as_index=False).first();st.subheader('Melhor proposta atual por produto');st.dataframe(best,use_container_width=True)
            sp=d.groupby('Produto')['Custo Unitário'].agg(['min','max']).reset_index();sp['Variação %']=(sp['max']-sp['min'])/sp['min'].replace(0,pd.NA)*100;st.subheader('Diferença entre fornecedor mais barato e mais caro');st.dataframe(sp,use_container_width=True)
    with t3:
        st.caption('Baseado nas NF-e efetivamente lançadas: custo médio ponderado convertido por produto e fornecedor.')
        c=db();hist=pd.read_sql_query("""select p.category Categoria,p.name Produto,s.legal_name Fornecedor,s.cnpj CNPJ,
        sum(ii.xml_total) 'Valor Comprado',sum(ii.converted_qty) 'Qtd Convertida',
        case when sum(ii.converted_qty)>0 then sum(ii.xml_total)/sum(ii.converted_qty) else 0 end 'Custo Médio Ponderado',
        min(ii.converted_unit_cost) 'Menor Custo',max(ii.converted_unit_cost) 'Maior Custo',count(distinct i.id) 'Nº Compras'
        from invoice_items ii join invoices i on i.id=ii.invoice_id join products p on p.id=ii.product_id join suppliers s on s.id=i.supplier_id
        where i.status='ENTRADA' and ii.converted_unit_cost>0 group by p.id,s.id order by p.name,'Custo Médio Ponderado'""",c);c.close()
        if hist.empty:st.info('Ainda não existem compras confirmadas suficientes para comparação.')
        else:
            st.dataframe(hist,use_container_width=True,height=380)
            besth=hist.sort_values(['Produto','Custo Médio Ponderado']).groupby('Produto',as_index=False).first()
            worst=hist.groupby('Produto')['Custo Médio Ponderado'].max().rename('Custo Mais Caro').reset_index();besth=besth.merge(worst,on='Produto',how='left');besth['Economia Potencial %']=(besth['Custo Mais Caro']-besth['Custo Médio Ponderado'])/besth['Custo Mais Caro'].replace(0,pd.NA)*100
            st.subheader('Fornecedor historicamente mais em conta por produto');st.dataframe(besth,use_container_width=True,height=420)
            buf=io.BytesIO();besth.to_excel(buf,index=False);st.download_button('Exportar relatório de fornecedores mais em conta',buf.getvalue(),'FORNECEDORES_MAIS_EM_CONTA.xlsx')

elif page=='Retiradas':
    standard_template_button('Retiradas','withdraw_tpl')
    with st.expander('IMPORTAR PLANILHA PADRÃO XLSX'):
        _up=st.file_uploader('Arquivo XLSX',type=['xlsx'],key='imp_withdraw_tpl')
        if _up and st.button('PROCESSAR IMPORTAÇÃO',key='btn_imp_withdraw_tpl'):
            _n,_e=import_standard_withdrawals(_up);confirm_success(f'{_n} registros processados.')
            if _e:st.warning('\\n'.join(_e[:30]))
            st.rerun()
    st.title('Retiradas por Categoria')
    allp=products('');cats=sorted(allp['Categoria'].dropna().unique().tolist());selcats=st.multiselect('Categoria(s) para retirada (vazio = todas)',cats,key='wd_cats')
    pid=product_picker_by_categories('wd',selcats);q=st.number_input('Quantidade',min_value=0.0001);obs=st.text_input('Motivo / setor')
    if pid and st.button('Registrar retirada'):
        cost=current_cost(pid);c=db();c.execute('insert into movements(product_id,movement_date,type,qty,unit_cost,notes) values(?,?,?,?,?,?)',(pid,datetime.now().isoformat(),'WITHDRAWAL',-abs(q),cost,obs));c.commit();c.close();app_log('Retiradas','Baixa',f'Produto {pid} | qtd {q}');confirm_success('Retirada registrada.');st.rerun()
    st.subheader('Histórico de retiradas')
    c=db();sql="select m.movement_date Data,p.category Categoria,p.subcategory Subcategoria,p.code Código,p.name Produto,-m.qty Quantidade,m.unit_cost Custo,(-m.qty*m.unit_cost) Valor,m.notes Observação from movements m join products p on p.id=m.product_id where m.type='WITHDRAWAL'";args=[]
    if selcats:
        sql+=' and p.category in ('+','.join(['?']*len(selcats))+')';args=selcats
    sql+=' order by m.movement_date desc';hist=pd.read_sql_query(sql,c,params=args);c.close();st.dataframe(hist,use_container_width=True,height=380)

elif page=='Perdas':
    standard_template_button('Perdas','loss_tpl')
    with st.expander('IMPORTAR PLANILHA PADRÃO XLSX'):
        _up=st.file_uploader('Arquivo XLSX',type=['xlsx'],key='imp_loss_tpl')
        if _up and st.button('PROCESSAR IMPORTAÇÃO',key='btn_imp_loss_tpl'):
            _n,_e=import_standard_losses(_up);confirm_success(f'{_n} registros processados.')
            if _e:st.warning('\\n'.join(_e[:30]))
            st.rerun()
    st.title('Perdas por Causa');pid=pick_product('loss');dt=st.date_input('Data perda',date.today());q=st.number_input('Quantidade perdida',min_value=0.0001);cause=st.selectbox('Causa',LOSS_CAUSES);obs=st.text_input('Observação')
    if pid:
        cost=current_cost(pid,dt);st.info(f'Custo {brl6(cost)} | Perda {brl(q*cost)}')
        if st.button('Registrar perda'):
            if cost<=0:st.error('Sem custo válido.')
            else:c=db();c.execute('insert into losses(product_id,loss_date,qty,unit_cost,cause,notes) values(?,?,?,?,?,?)',(pid,str(dt),q,cost,cause,obs));c.execute('insert into movements(product_id,movement_date,type,qty,unit_cost,reference,notes) values(?,?,?,?,?,?,?)',(pid,str(dt)+'T12:00:00','LOSS',-abs(q),cost,cause,obs));c.commit();c.close();app_log('Perdas','Registro',f'Produto {pid} | qtd {q} | causa {cause}');st.rerun()
    c=db();d=pd.read_sql_query("select l.loss_date Data,p.code Código,p.name Produto,p.category Categoria,l.qty Quantidade,l.unit_cost Custo,l.cause Causa,l.qty*l.unit_cost Valor from losses l join products p on p.id=l.product_id order by l.id desc",c);c.close();st.dataframe(d,use_container_width=True,height=350)

elif page=='CMV & BI':
    st.title('CMV Geral e Semanal')
    st.caption('Compras = NF confirmadas + Compras Avulsas. CMV Inventário = Estoque Inicial + Compras − Estoque Final.')

    today=date.today()
    c1,c2=st.columns(2)
    a=c1.date_input('Início do período',today.replace(day=1),key='cmv_v11_a')
    b=c2.date_input('Fim do período',today,key='cmv_v11_b')

    sales=consolidated_sales_value(a,b)
    nf_only=0.0
    c=db()
    r=c.execute("""select coalesce(sum(ii.xml_total),0) v from invoice_items ii
                   join invoices i on i.id=ii.invoice_id
                   where upper(i.status)='ENTRADA'
                   and date(substr(i.issue_date,1,10)) between date(?) and date(?)""",
                (str(a),str(b))).fetchone()
    nf_only=float(r['v'] or 0);c.close()
    loose=loose_purchases_value(a,b,None)
    purchases=nf_only+loose

    opening=inventory_value_at_category(a-timedelta(days=1),None)
    closing=inventory_value_at_category(b,None)
    cogs=opening+purchases-closing

    c=db()
    losses=float(c.execute("""select coalesce(sum(qty*unit_cost),0) v from losses
                             where loss_date between ? and ?""",(str(a),str(b))).fetchone()['v'] or 0)
    c.close()

    k=st.columns(6)
    k[0].metric('Venda Consolidada',brl(sales))
    k[1].metric('Compras NF',brl(nf_only))
    k[2].metric('Compras Avulsas',brl(loose))
    k[3].metric('Compras Totais',brl(purchases))
    k[4].metric('CMV Inventário',brl(cogs))
    k[5].metric('Perdas Registradas',brl(losses))

    k2=st.columns(4)
    k2[0].metric('Compras / Vendas',f'{purchases/sales*100:.2f}%' if sales else '-')
    k2[1].metric('CMV / Vendas',f'{cogs/sales*100:.2f}%' if sales else '-')
    k2[2].metric('Perdas / Vendas',f'{losses/sales*100:.2f}%' if sales else '-')
    k2[3].metric('CMV + Perdas / Vendas',f'{(cogs+losses)/sales*100:.2f}%' if sales else '-')

    st.info(f'Estoque inicial: {brl(opening)} | Estoque final: {brl(closing)} | CMV = {brl(opening)} + {brl(purchases)} − {brl(closing)} = {brl(cogs)}')

    # Semanas FIXAS do mês conforme regra operacional HNT:
    # 1-7 = 1ª | 8-14 = 2ª | 15-21 = 3ª | 22-fim = 4ª.
    rows=[]
    for wk in fixed_month_week_ranges(a,b):
        cursor=wk['Início'];week_end=wk['Fim']
        ws=consolidated_sales_value(cursor,week_end)
        wp=purchases_value(cursor,week_end,None)
        wo=inventory_value_at_category(cursor-timedelta(days=1),None)
        wc=inventory_value_at_category(week_end,None)
        wcogs=wo+wp-wc
        c=db()
        wl=float(c.execute("""select coalesce(sum(qty*unit_cost),0) v from losses
                              where loss_date between ? and ?""",(str(cursor),str(week_end))).fetchone()['v'] or 0)
        c.close()
        rows.append({
            'Mês':wk['Mês'],'Semana':wk['Semana'],
            'Início':cursor,'Fim':week_end,'Vendas':ws,'Compras':wp,
            'Compras/Vendas %':wp/ws*100 if ws else 0,
            'Estoque Inicial':wo,'Estoque Final':wc,'CMV':wcogs,
            'CMV/Vendas %':wcogs/ws*100 if ws else 0,
            'Perdas':wl,'CMV+Perdas/Vendas %':(wcogs+wl)/ws*100 if ws else 0
        })

    weekly=pd.DataFrame(rows)
    st.subheader('CMV sobre Vendas — Semanas Fixas do Mês')
    st.caption('Regra: dias 1–7 = 1ª semana; 8–14 = 2ª; 15–21 = 3ª; 22 até o último dia do mês = 4ª. Não há sobreposição de datas.')
    if not weekly.empty:
        show=weekly.copy()
        show['Início']=pd.to_datetime(show['Início']).dt.strftime('%d/%m/%Y')
        show['Fim']=pd.to_datetime(show['Fim']).dt.strftime('%d/%m/%Y')
        for col in ['Vendas','Compras','Estoque Inicial','Estoque Final','CMV','Perdas']:
            show[col]=show[col].map(brl)
        for col in ['Compras/Vendas %','CMV/Vendas %','CMV+Perdas/Vendas %']:
            show[col]=show[col].map(lambda x:f'{x:.2f}%')
        st.dataframe(show,use_container_width=True,hide_index=True,height=380)
        export_buttons(weekly,'CMV_SEMANAS_FIXAS','cmv_weekly_fixed_v1131')
        chart=weekly.copy()
        chart['Período']=chart['Mês']+' • '+chart['Semana']
        st.plotly_chart(px.line(chart,x='Período',y=['Compras/Vendas %','CMV/Vendas %','CMV+Perdas/Vendas %'],markers=True),
                        use_container_width=True)

    # Categorias configuradas para relatório de compras
    report_cats=allowed_categories('include_purchase_reports')
    c=db()
    args=[str(a),str(b)]
    q="""select p.category Categoria,sum(ii.xml_total) Compras
         from invoice_items ii join invoices i on i.id=ii.invoice_id
         join products p on p.id=ii.product_id
         where upper(i.status)='ENTRADA' and date(substr(i.issue_date,1,10)) between date(?) and date(?)"""
    if report_cats:
        q+=" and p.category in ("+','.join(['?']*len(report_cats))+")";args+=report_cats
    q+=" group by p.category order by Compras desc"
    cat=pd.read_sql_query(q,c,params=args);c.close()
    st.subheader('Compras por Categoria Configurada')
    if cat.empty:
        st.info('Sem compras de categorias configuradas neste período.')
    else:
        cat['% das Compras NF']=cat['Compras']/max(0.000001,float(cat['Compras'].sum()))*100
        cat['% sobre Vendas']=cat['Compras']/sales*100 if sales else 0
        st.dataframe(cat,use_container_width=True,hide_index=True,
            column_config={'Compras':st.column_config.NumberColumn(format='R$ %.2f')})
        export_buttons(cat,'COMPRAS_CATEGORIA','cmv_cat_v11')



elif page=='Controle Produção Proteínas':
    st.title('Controle de Produção — Proteínas')
    st.caption('Controle integrado de proteínas: Peixaria, Sushi/Japonês, Poke, Rodízio, fichas técnicas, CMV teórico, produção, rendimento, perdas e desvios. A aba de importação manual de Mix foi removida.')

    tcatalog,tgroups,tsheets,tsales,tc,tp,td,th,ta=st.tabs([
        'Itens / Filtros',
        'Combos / Grupos',
        'Fichas Técnicas',
        'Vendas & CMV Proteínas',
        'Proteínas Controladas',
        'Padrões de Corte / Produção',
        'Fechamento Diário',
        'Histórico / Editar / Excluir',
        'Análise Física'
    ])


    # A importação manual de Mix foi removida da interface nesta revisão.
    # Os dados já existentes, tabelas e funções históricas são preservados para auditoria e compatibilidade.
    if False:
        st.subheader('Importar Mix de Produtos por Canal')
        st.caption('Importa o relatório com PLU / PLU (Itens), detecta canais FL/FC/TS/TT, classifica Peixaria, Sushi/Japonês, Poke e Rodízio e sugere proteínas. Nenhuma sugestão de mercado vira ficha técnica sem validação.')

        i1,i2=st.columns(2)
        pstart=i1.date_input('Período inicial do relatório',date.today().replace(day=1),key='prot_mix_start')
        pend=i2.date_input('Período final do relatório',date.today(),key='prot_mix_end')
        up=st.file_uploader('Arquivo XLSX — Mix de Produtos por Canal',type=['xlsx'],key='prot_mix_upload')
        inotes=st.text_input('Observação da importação',key='prot_mix_notes')

        if up is not None:
            try:
                prev=parse_protein_sales_mix_xlsx(up)
                up.seek(0)
                if prev.empty:
                    st.warning('Nenhuma linha reconhecida.')
                else:
                    relevant=prev[(prev['family']!='Outros') | (prev['protein_suggestions']!='')]
                    c1,c2,c3,c4=st.columns(4)
                    c1.metric('Linhas',len(prev))
                    c2.metric('Linhas relevantes',len(relevant))
                    c3.metric('Valor linhas',brl(float(prev['total_sold'].sum())))
                    c4.metric('Itens com proteína nominal',int((prev['protein_suggestions']!='').sum()))
                    st.dataframe(relevant[['channel','plu','plu_item','item_name','family',
                                           'protein_suggestions','confidence','qty_sold','total_sold']].head(500),
                                 use_container_width=True,hide_index=True,height=360)
                    if st.button('✅ IMPORTAR MIX E CRIAR CATÁLOGO',type='primary',key='prot_mix_import_btn'):
                        try:
                            up.seek(0)
                            iid,n,total=import_protein_sales_mix(up,up.name,pstart,pend,inotes)
                            set_flash(f'Mix importado: ID {iid}, {n} linhas, {brl(total)}. Catálogo e sugestões atualizados.','success')
                            st.rerun()
                        except Exception as ex:st.error(str(ex))
            except Exception as ex:
                st.error(f'Não foi possível ler o arquivo: {ex}')

        initial_file=ROOT/'dados_iniciais'/'Mix_Produtos_Canal_Venda_OFICIAL.xlsx'
        if initial_file.exists():
            st.divider()
            st.caption('O pacote contém o relatório OFICIAL indicado pelo usuário para importação e tratamento nesta versão.')
            if st.button('IMPORTAR ARQUIVO ANEXO INICIAL DO PACOTE',key='prot_mix_initial'):
                try:
                    with initial_file.open('rb') as f:
                        iid,n,total=import_protein_sales_mix(f,initial_file.name,pstart,pend,
                            'Relatório oficial de Mix por Canal incluído na V11.2.1')
                    set_flash(f'Arquivo inicial importado: ID {iid}, {n} linhas, {brl(total)}.','success')
                    st.rerun()
                except Exception as ex:st.error(str(ex))

        st.divider()
        imports=protein_imports_df(False)
        if imports.empty:
            st.info('Nenhum Mix de Vendas importado ainda.')
        else:
            st.subheader('Importações realizadas')
            st.dataframe(imports,use_container_width=True,hide_index=True)
            iid_del=st.selectbox('Importação para desativar/excluir do cálculo',imports.ID.tolist(),
                key='prot_import_del_id',
                format_func=lambda x:f"ID {x} | {imports.loc[imports.ID==x,'Arquivo'].iloc[0]} | "
                                     f"{imports.loc[imports.ID==x,'De'].iloc[0]} a {imports.loc[imports.ID==x,'Até'].iloc[0]}")
            cc=st.checkbox('Confirmo desativar esta importação (linhas permanecem para auditoria)',key='prot_import_del_confirm')
            if st.button('DESATIVAR IMPORTAÇÃO',disabled=not cc,key='prot_import_del_btn'):
                c=db();c.execute("update protein_sales_imports set active=0 where id=?",(int(iid_del),));c.commit();c.close()
                set_flash('Importação desativada. Histórico preservado.','success');st.rerun()

    # ==========================================================
    # CATÁLOGO / FILTROS
    # ==========================================================
    with tcatalog:
        st.subheader('Itens — Peixaria, Sushi/Japonês, Poke e Rodízio')
        c1,c2,c3=st.columns([2,2,1])
        sq=c1.text_input('🔎 Pesquisar item / código',key='prot_catalog_search')
        fam_options=['Peixaria / Proteínas','Sushi / Japonês','Poke Kauai','Rodízio','Outros']
        fam_sel=c2.multiselect('Famílias',fam_options,
            default=['Peixaria / Proteínas','Sushi / Japonês','Poke Kauai','Rodízio'],key='prot_catalog_fam')
        only_unmapped=c3.checkbox('Só sem ficha',value=False,key='prot_catalog_unmapped')
        catalog=protein_catalog_df(sq,fam_sel,only_unmapped,5000)
        if catalog.empty:
            st.info('Nenhum item encontrado com os filtros.')
        else:
            st.dataframe(catalog,use_container_width=True,hide_index=True,height=520)
            st.caption('CONFIRMADO NO NOME = evidência do arquivo. INFERÊNCIA = sugestão de mercado, sempre exige validação. REVISAR MANUALMENTE = o nome não identifica proteína suficiente.')

    # ==========================================================
    # GRUPOS / COMBOS
    # ==========================================================
    with tgroups:
        st.subheader('Combos / Grupos de PLU e Proteínas Sugeridas')
        st.caption('Neste formato de relatório não existe coluna Tipo=Combo. Portanto o sistema trata PLU + PLU (Itens) como GRUPO. A proteína é consolidada pelas linhas do grupo, sem inventar uma receita.')
        imports=protein_imports_df(True)
        if imports.empty:
            st.info('Importe um Mix de Vendas primeiro.')
        else:
            gid=st.selectbox('Importação',imports.ID.tolist(),key='prot_group_import',
                format_func=lambda x:f"ID {x} | {imports.loc[imports.ID==x,'Arquivo'].iloc[0]}")
            groups=protein_groups_df(gid,True)
            gfilter=st.radio('Mostrar',['Todos os grupos relevantes','Com proteína sugerida','Sem proteína sugerida / alinhar manualmente'],
                             horizontal=True,key='prot_group_filter')
            if not groups.empty:
                if gfilter=='Com proteína sugerida':
                    groups=groups[groups['Proteínas Sugeridas'].fillna('').astype(str).str.strip()!='']
                elif gfilter=='Sem proteína sugerida / alinhar manualmente':
                    groups=groups[groups['Proteínas Sugeridas'].fillna('').astype(str).str.strip()=='']
                st.dataframe(groups,use_container_width=True,hide_index=True,height=500)
                export_buttons(groups,'GRUPOS_COMBOS_PROTEINAS','prot_groups_export')
            else:st.info('Sem grupos relevantes nesta importação.')

            st.markdown('**Interpretação automática de mercado**')
            st.caption('Philadelphia/Filadélfia sugere Salmão; California sugere Kani. Essas sugestões aparecem para acelerar o alinhamento, mas só entram no CMV depois de virarem Ficha Técnica validada.')

    # ==========================================================
    # FICHAS TÉCNICAS
    # ==========================================================
    with tsheets:
        st.subheader('Fichas Técnicas de Proteínas')
        st.caption('Esta é a fonte de verdade do consumo teórico. Cada Item/PLU pode ter uma ou várias proteínas e uma porção padrão. Ex.: Poke Mix → Salmão 60 g + Camarão 60 g.')

        c1,c2=st.columns([2,1])
        fs=c1.text_input('🔎 Pesquisar item para montar ficha',key='prot_sheet_search')
        ff=c2.multiselect('Família da venda',['Peixaria / Proteínas','Sushi / Japonês','Poke Kauai','Rodízio','Outros'],
                          default=['Peixaria / Proteínas','Sushi / Japonês','Poke Kauai','Rodízio'],key='prot_sheet_family')
        cat=protein_catalog_df(fs,ff,False,5000)
        if cat.empty:
            st.info('Nenhum item disponível.')
        else:
            mid=st.selectbox('Item / PLU',cat.ID.tolist(),key='prot_sheet_item',
                format_func=lambda x:f"{cat.loc[cat.ID==x,'Código'].iloc[0]} | "
                                     f"{cat.loc[cat.ID==x,'Item'].iloc[0]} | "
                                     f"{cat.loc[cat.ID==x,'Proteína Sugerida'].iloc[0] or 'SEM SUGESTÃO'}")
            selected=cat[cat.ID==mid].iloc[0]
            st.info(f"Família: {selected['Família']} | Sugestão: {selected['Proteína Sugerida'] or '—'} | Confiança: {selected['Confiança']}")

            labels,to_id,to_label=protein_product_options()
            if not labels:
                st.warning('Cadastre produtos de estoque antes de criar fichas.')
            else:
                plabel=st.selectbox('SKU interno da proteína',labels,key='prot_sheet_product')
                q1,q2,q3=st.columns(3)
                portion=q1.number_input('Porção por unidade vendida',min_value=0.0,value=0.0,step=0.001,
                                        format=num_format(),key='prot_sheet_portion')
                punit=q2.selectbox('Unidade da porção',['G','KG','UN'],key='prot_sheet_unit')
                margin=q3.number_input('Margem de erro %',min_value=0.0,value=5.0,step=0.1,key='prot_sheet_margin')
                snote=st.text_input('Observações / padrão de corte / montagem',key='prot_sheet_notes')
                if st.button('✅ SALVAR FICHA TÉCNICA',type='primary',key='prot_sheet_save'):
                    pid=to_id.get(plabel)
                    if portion<=0:st.error('A porção deve ser maior que zero.')
                    elif not pid:st.error('Selecione o SKU interno.')
                    else:
                        try:
                            save_protein_technical_sheet(int(mid),int(pid),portion,punit,margin,
                                'MANUAL','VALIDADO',snote)
                            # Garante que o SKU esteja disponível no controle físico de proteínas.
                            c=db()
                            c.execute("""insert into controlled_products(product_id,active,protein_family,updated_at)
                                       values(?,1,?,?)
                                       on conflict(product_id) do update set active=1,
                                       protein_family=case when coalesce(controlled_products.protein_family,'')=''
                                                           then excluded.protein_family else controlled_products.protein_family end,
                                       updated_at=excluded.updated_at""",
                                      (int(pid),str(selected['Proteína Sugerida'] or ''),
                                       datetime.now().isoformat(timespec='seconds')))
                            c.commit();c.close()
                            set_flash('Ficha técnica salva e SKU incluído no controle de proteínas.','success');st.rerun()
                        except Exception as ex:st.error(str(ex))

        st.divider()
        sq2=st.text_input('🔎 Pesquisar fichas existentes',key='prot_sheet_existing_search')
        sheets=technical_sheets_df(sq2)
        if sheets.empty:
            st.info('Nenhuma ficha técnica validada ainda.')
        else:
            st.dataframe(sheets.drop(columns=['product_id']),use_container_width=True,hide_index=True,height=400)
            sid=st.selectbox('Ficha para alterar / excluir',sheets.ID.tolist(),key='prot_sheet_edit_id',
                format_func=lambda x:f"{sheets.loc[sheets.ID==x,'Item'].iloc[0]} → {sheets.loc[sheets.ID==x,'Proteína'].iloc[0]}")
            sr=sheets[sheets.ID==sid].iloc[0]
            e1,e2,e3=st.columns(3)
            eq=e1.number_input('Nova porção',min_value=0.0,value=float(sr['Porção'] or 0),step=0.001,
                               format=num_format(),key='prot_sheet_edit_qty')
            eu=e2.selectbox('Unidade',['G','KG','UN'],
                index=['G','KG','UN'].index(str(sr['Unidade Porção'])) if str(sr['Unidade Porção']) in ['G','KG','UN'] else 0,
                key='prot_sheet_edit_unit')
            em=e3.number_input('Margem %',min_value=0.0,value=float(sr['Margem %'] or 0),step=0.1,key='prot_sheet_edit_margin')
            en=st.text_input('Observação',value=str(sr['Observações'] or ''),key='prot_sheet_edit_notes')
            b1,b2=st.columns(2)
            if b1.button('SALVAR ALTERAÇÃO',type='primary',key='prot_sheet_edit_save'):
                c=db();mrow=c.execute("""select pmc.id menu_item_id from protein_technical_sheets pts
                                         join protein_menu_catalog pmc on pmc.id=pts.menu_item_id where pts.id=?""",
                                      (int(sid),)).fetchone();c.close()
                try:
                    save_protein_technical_sheet(int(mrow['menu_item_id']),int(sr['product_id']),eq,eu,em,
                                                 'MANUAL','VALIDADO',en)
                    set_flash('Ficha técnica alterada.','success');st.rerun()
                except Exception as ex:st.error(str(ex))
            cf=st.checkbox('Confirmo excluir/desativar esta ficha',key='prot_sheet_del_confirm')
            if b2.button('EXCLUIR FICHA',disabled=not cf,key='prot_sheet_del'):
                c=db()
                try:
                    before=c.execute("select * from protein_technical_sheets where id=?",(int(sid),)).fetchone()
                    c.execute("update protein_technical_sheets set active=0,updated_at=? where id=?",
                              (datetime.now().isoformat(timespec='seconds'),int(sid)))
                    c.execute("""insert into protein_mapping_audit(event_date,module,entity_key,action,before_json,after_json)
                                 values(?,?,?,?,?,?)""",
                              (datetime.now().isoformat(timespec='seconds'),'FICHA TÉCNICA PROTEÍNA',
                               str(sid),'DESATIVAR',json.dumps(dict(before),ensure_ascii=False) if before else '{}','{}'))
                    c.commit();set_flash('Ficha técnica desativada. Histórico preservado.','success');st.rerun()
                except Exception as ex:c.rollback();st.error(str(ex))
                finally:c.close()

    # ==========================================================
    # VENDAS & CMV DE PROTEÍNAS
    # ==========================================================
    with tsales:
        st.subheader('Vendas & CMV Teórico das Proteínas')
        st.caption('O cálculo usa somente Fichas Técnicas validadas. Venda atribuída = receita do item distribuída entre as proteínas da ficha proporcionalmente ao CMV teórico de cada proteína. Venda relacionada continua visível e pode se repetir entre proteínas.')
        imports=protein_imports_df(True)
        if imports.empty:
            st.info('Importe um Mix de Vendas.')
        else:
            iid=st.selectbox('Importação para analisar',imports.ID.tolist(),key='prot_sales_import',
                format_func=lambda x:f"ID {x} | {imports.loc[imports.ID==x,'Arquivo'].iloc[0]} | "
                                     f"{imports.loc[imports.ID==x,'De'].iloc[0]} a {imports.loc[imports.ID==x,'Até'].iloc[0]}")
            det=protein_sales_cmv_df(iid)
            summ=protein_sales_cmv_summary(iid)

            c=db()
            unmapped=c.execute("""select coalesce(sum(psr.total_sold),0) total,count(*) n
                from protein_sales_rows psr
                join protein_menu_catalog pmc on pmc.item_code=psr.item_code
                where psr.import_id=? and (psr.family<>'Outros' or psr.protein_suggestions<>'')
                and not exists(select 1 from protein_technical_sheets pts
                               where pts.menu_item_id=pmc.id and pts.active=1)""",(int(iid),)).fetchone()
            c.close()

            if summ.empty:
                st.warning('Ainda não há fichas técnicas suficientes para calcular CMV desta importação.')
            else:
                k1,k2,k3,k4=st.columns(4)
                total_cmv=float(summ['CMV Proteína'].sum())
                attributed=float(summ['Venda Atribuída Proteína'].sum())
                zero_cost=int((det['Custo Médio']<=0).sum()) if 'Custo Médio' in det.columns else 0
                k1.metric('CMV Teórico Proteínas',brl(total_cmv))
                k2.metric('Venda Atribuída Proteínas',brl(attributed))
                k3.metric('CMV % Proteínas',f'{total_cmv/attributed*100:.2f}%' if attributed else '-')
                k4.metric('Venda relevante sem ficha',brl(float(unmapped['total'] or 0)),
                          help=f"{int(unmapped['n'] or 0)} linha(s) relevante(s) ainda sem ficha técnica.")
                if zero_cost:
                    st.warning(f'{zero_cost} linha(s) calculada(s) possuem Custo Médio = R$ 0,00. '
                               'O CMV e a Venda Atribuída dessas proteínas ficam incompletos até corrigir o custo do SKU.')

                st.markdown('### Resumo por proteína')
                st.dataframe(summ,use_container_width=True,hide_index=True,
                    column_config={
                        'CMV Proteína':st.column_config.NumberColumn(format='R$ %.2f'),
                        'Venda Atribuída Proteína':st.column_config.NumberColumn(format='R$ %.2f'),
                        'CMV %':st.column_config.NumberColumn(format='%.2f%%')
                    })
                export_buttons(summ,'CMV_PROTEINAS_RESUMO','prot_cmv_summary')

                st.markdown('### Detalhado por item vendido')
                st.dataframe(det,use_container_width=True,hide_index=True,height=480)
                export_buttons(det,'CMV_PROTEINAS_DETALHE','prot_cmv_detail')


    # ==========================================================
    # 1. PRODUTOS CONTROLADOS
    # ==========================================================
    with tc:
        q=st.text_input('🔎 Pesquisar produto para controlar',key='ctrl_search')
        allp=search_products_sql(q,2000,include_inactive=False)
        if allp.empty:
            st.info('Nenhum produto encontrado.')
        else:
            pid=st.selectbox('Produto',allp.id.tolist(),key='ctrl_pid_v111',
                format_func=lambda x:f"{int(allp.loc[allp.id==x,'Código'].iloc[0])} | "
                                     f"{allp.loc[allp.id==x,'Produto'].iloc[0]} | "
                                     f"{allp.loc[allp.id==x,'Unidade'].iloc[0]}")
            c=db();old=c.execute("select * from controlled_products where product_id=?",(int(pid),)).fetchone();c.close()
            c1,c2,c3,c4=st.columns(4)
            protein_options=['Salmão','Lombo Atum','Atum','Camarão','Peixe Branco / Ceviche','Tilápia',
                             'Polvo','Lula','Haddock','Kani','Frango','Pork','Carne / Filé Mignon','Outra']
            old_family=str(old['protein_family'] or '') if old else ''
            family_idx=protein_options.index(old_family) if old_family in protein_options else 0
            protein_family=c1.selectbox('Família da proteína',protein_options,index=family_idx,key='ctrl_family_v112')
            source_options=['PRODUCTION','SALES','BOTH']
            old_source=str(old['theoretical_source'] or 'PRODUCTION') if old else 'PRODUCTION'
            source_idx=source_options.index(old_source) if old_source in source_options else 0
            theo_source=c2.selectbox('Fonte do consumo teórico',source_options,index=source_idx,key='ctrl_source_v112',
                help='PRODUCTION = produção registrada; SALES = Mix diário + fichas técnicas; BOTH = soma as duas fontes.')
            target_yield=c3.number_input('Rendimento alvo %',min_value=0.0,max_value=100.0,
                value=float(old['target_yield_pct'] or 0) if old else 0.0,step=0.1,key='ctrl_yield_v111')
            tol=c4.number_input('Tolerância variação %',min_value=0.0,
                value=float(old['variance_tolerance_pct'] or 3) if old else 3.0,step=0.1,key='ctrl_tol_v111')
            note=st.text_input('Observações',value=str(old['notes'] or '') if old else '',key='ctrl_note_v111')
            if st.button('✅ SALVAR PROTEÍNA CONTROLADA',type='primary',key='ctrl_save_v111'):
                c=db()
                c.execute("""insert into controlled_products(product_id,active,target_yield_pct,variance_tolerance_pct,
                    protein_family,theoretical_source,notes,updated_at)
                    values(?,1,?,?,?,?,?,?)
                    on conflict(product_id) do update set active=1,
                    target_yield_pct=excluded.target_yield_pct,
                    variance_tolerance_pct=excluded.variance_tolerance_pct,
                    protein_family=excluded.protein_family,theoretical_source=excluded.theoretical_source,
                    notes=excluded.notes,updated_at=excluded.updated_at""",
                    (int(pid),round_entry(target_yield),round_entry(tol),protein_family,theo_source,note,
                     datetime.now().isoformat(timespec='seconds')))
                c.commit();c.close()
                set_flash('Proteína controlada salva.','success');st.rerun()

        c=db()
        ctrl=pd.read_sql_query("""select cp.product_id ID,p.code Código,p.name Produto,p.unit Unidade,
            cp.protein_family 'Família Proteína',cp.theoretical_source 'Fonte Teórica',
            cp.target_yield_pct 'Rendimento Alvo %',cp.variance_tolerance_pct 'Tolerância %',
            cp.notes Observações
            from controlled_products cp join products p on p.id=cp.product_id
            where cp.active=1 order by cp.protein_family,p.name""",c);c.close()
        if not ctrl.empty:
            st.subheader('Proteínas atualmente controladas')
            st.dataframe(ctrl,use_container_width=True,hide_index=True,height=320)
            did=st.selectbox('Remover do controle',ctrl.ID.tolist(),key='ctrl_del_id',
                format_func=lambda x:f"{ctrl.loc[ctrl.ID==x,'Código'].iloc[0]} | {ctrl.loc[ctrl.ID==x,'Produto'].iloc[0]}")
            cfm=st.checkbox('Confirmo remover este SKU do controle futuro',key='ctrl_del_confirm')
            if st.button('REMOVER DO CONTROLE',disabled=not cfm,key='ctrl_del'):
                c=db();c.execute("update controlled_products set active=0,updated_at=? where product_id=?",
                    (datetime.now().isoformat(timespec='seconds'),int(did)));c.commit();c.close()
                set_flash('Proteína removida do controle futuro. Histórico preservado.','success');st.rerun()

    # ==========================================================
    # 2. PADRÕES DE CORTE E PRODUÇÃO
    # ==========================================================
    with tp:
        st.subheader('Preparações / Produção Física')
        c=db();recipes=pd.read_sql_query("select id,name Nome,unit Unidade,notes Observações from production_recipes where active=1 order by name",c);c.close()

        r1,r2=st.columns(2)
        new_name=r1.text_input('Nova preparação',key='recipe_name_v111',placeholder='Ex.: Sashimi Salmão 5 peças')
        new_unit=r2.text_input('Unidade produzida',value='UN',key='recipe_unit_v111')
        if st.button('CRIAR PREPARAÇÃO',key='recipe_create_v111') and new_name.strip():
            c=db()
            try:
                c.execute("insert into production_recipes(name,unit,active) values(?,?,1)",
                          (new_name.strip(),new_unit.strip() or 'UN'))
                c.commit();set_flash('Preparação criada. Configure o padrão de corte abaixo.','success');st.rerun()
            except Exception as ex:st.error(str(ex))
            finally:c.close()

        c=db();recipes=pd.read_sql_query("select id,name Nome,unit Unidade,notes Observações from production_recipes where active=1 order by name",c)
        ctrl=pd.read_sql_query("""select cp.product_id,p.code,p.name,p.unit from controlled_products cp
                                  join products p on p.id=cp.product_id
                                  where cp.active=1 order by p.name""",c);c.close()

        if not recipes.empty:
            rid=st.selectbox('Preparação para configurar',recipes.id.tolist(),key='recipe_sel_v111',
                format_func=lambda x:f"{recipes.loc[recipes.id==x,'Nome'].iloc[0]} | {recipes.loc[recipes.id==x,'Unidade'].iloc[0]}")
            rr=recipes[recipes.id==rid].iloc[0]
            re1,re2=st.columns(2)
            edit_name=re1.text_input('Nome da preparação',value=str(rr['Nome']),key='recipe_edit_name_v111')
            edit_unit=re2.text_input('Unidade',value=str(rr['Unidade']),key='recipe_edit_unit_v111')
            if st.button('SALVAR NOME / UNIDADE',key='recipe_edit_save_v111'):
                c=db()
                try:
                    c.execute("update production_recipes set name=?,unit=? where id=?",
                              (edit_name.strip(),edit_unit.strip() or 'UN',int(rid)))
                    c.commit();set_flash('Preparação atualizada.','success');st.rerun()
                except Exception as ex:st.error(str(ex))
                finally:c.close()

            if not ctrl.empty:
                st.markdown('**Padrão de corte / ingrediente controlado**')
                ipid=st.selectbox('Ingrediente / SKU',ctrl.product_id.tolist(),key='recipe_ing_v111',
                    format_func=lambda x:f"{ctrl.loc[ctrl.product_id==x,'code'].iloc[0]} | "
                                         f"{ctrl.loc[ctrl.product_id==x,'name'].iloc[0]} | "
                                         f"{ctrl.loc[ctrl.product_id==x,'unit'].iloc[0]}")
                c=db()
                pri=c.execute("""select * from production_recipe_items where recipe_id=? and product_id=?""",
                              (int(rid),int(ipid))).fetchone()
                c.close()
                pri=dict(pri) if pri else {}

                g1,g2,g3=st.columns(3)
                grams=g1.number_input('Gramatura padrão por corte (g)',min_value=0.0,
                    value=float(pri.get('cut_grams',0) or 0),step=0.1,key='cut_grams_v111')
                cuts=g2.number_input('Unidades / cortes por preparação',min_value=0.0,
                    value=float(pri.get('cuts_per_output',0) or 0),step=1.0,key='cut_units_v111')
                margin=g3.number_input('Margem de erro permitida %',min_value=0.0,
                    value=float(pri.get('error_margin_pct',5) or 5),step=0.1,key='cut_margin_v111')

                product_unit=str(ctrl.loc[ctrl.product_id==ipid,'unit'].iloc[0])
                theoretical_per_output=_stock_qty_from_grams(grams*cuts,product_unit) if grams>0 and cuts>0 else 0
                st.info(f'Padrão calculado por 1 preparação: {grams:.3f} g × {cuts:.3f} cortes = '
                        f'{grams*cuts:.3f} g = {theoretical_per_output:.3f} {product_unit}')

                direct=st.number_input('Quantidade padrão direta por preparação (fallback)',min_value=0.0,
                    value=float(pri.get('qty_per_unit',theoretical_per_output) or theoretical_per_output),
                    step=0.001,format=num_format(),key='recipe_direct_qty_v111',
                    help='Só é usada se gramatura padrão ou número de cortes estiverem zerados.')

                if st.button('✅ SALVAR PADRÃO DE CORTE',type='primary',key='recipe_item_save_v111'):
                    qty_per=theoretical_per_output if grams>0 and cuts>0 else round_entry(direct)
                    c=db()
                    c.execute("""insert into production_recipe_items(
                        recipe_id,product_id,qty_per_unit,cut_grams,cuts_per_output,error_margin_pct)
                        values(?,?,?,?,?,?)
                        on conflict(recipe_id,product_id) do update set
                        qty_per_unit=excluded.qty_per_unit,
                        cut_grams=excluded.cut_grams,
                        cuts_per_output=excluded.cuts_per_output,
                        error_margin_pct=excluded.error_margin_pct""",
                        (int(rid),int(ipid),round_entry(qty_per),round_entry(grams),
                         round_entry(cuts),round_entry(margin)))
                    c.commit();c.close()
                    set_flash('Padrão de corte salvo.','success');st.rerun()

            c=db()
            lines=pd.read_sql_query("""select pri.id,pr.name Produção,p.code Código,p.name Produto,p.unit Unidade,
                pri.cut_grams 'Gramatura Corte g',pri.cuts_per_output 'Unidades/Cortes',
                pri.qty_per_unit 'Qtd por Preparação',pri.error_margin_pct 'Margem %'
                from production_recipe_items pri
                join production_recipes pr on pr.id=pri.recipe_id
                join products p on p.id=pri.product_id
                where pri.recipe_id=? order by p.name""",c,params=[int(rid)])
            c.close()
            if not lines.empty:
                st.dataframe(lines.drop(columns=['id']),use_container_width=True,hide_index=True)
                lid=st.selectbox('Padrão para excluir',lines.id.tolist(),key='recipe_line_del_id',
                    format_func=lambda x:f"{lines.loc[lines.id==x,'Produto'].iloc[0]} | "
                                         f"{lines.loc[lines.id==x,'Gramatura Corte g'].iloc[0]}g × "
                                         f"{lines.loc[lines.id==x,'Unidades/Cortes'].iloc[0]}")
                confirm_line=st.checkbox('Confirmo excluir este padrão',key='recipe_line_del_confirm')
                if st.button('EXCLUIR PADRÃO',disabled=not confirm_line,key='recipe_line_del'):
                    c=db();c.execute("delete from production_recipe_items where id=?",(int(lid),));c.commit();c.close()
                    set_flash('Padrão excluído. Histórico de fechamentos permanece.','success');st.rerun()

            confirm_recipe=st.checkbox('Confirmo desativar esta preparação',key='recipe_del_confirm_v111')
            if st.button('DESATIVAR PREPARAÇÃO',disabled=not confirm_recipe,key='recipe_del_v111'):
                c=db();c.execute("update production_recipes set active=0 where id=?",(int(rid),));c.commit();c.close()
                set_flash('Preparação desativada. Produções históricas preservadas.','success');st.rerun()

        st.divider()
        st.subheader('Produção do Dia e Conferência de Gramatura')
        c=db();recipes=pd.read_sql_query("select id,name Nome,unit Unidade from production_recipes where active=1 order by name",c);c.close()
        if not recipes.empty:
            pdte=st.date_input('Data da produção',date.today(),key='prod_day_v111')
            prid=st.selectbox('Preparação produzida',recipes.id.tolist(),key='prod_recipe_v111',
                format_func=lambda x:f"{recipes.loc[recipes.id==x,'Nome'].iloc[0]} | {recipes.loc[recipes.id==x,'Unidade'].iloc[0]}")
            c=db();oldout=c.execute("select * from production_output where work_date=? and recipe_id=?",
                                   (str(pdte),int(prid))).fetchone();c.close()
            qty_prod=st.number_input('Quantidade produzida',min_value=0.0,
                value=float(oldout['qty_produced'] or 0) if oldout else 0.0,
                step=0.001,format=num_format(),key='prod_qty_v111')

            c=db()
            pitems=pd.read_sql_query("""select pri.product_id,p.code Código,p.name Produto,p.unit Unidade,
                pri.cut_grams 'Gramatura Corte g',pri.cuts_per_output 'Unidades/Cortes',
                pri.qty_per_unit 'Qtd Padrão Direta',pri.error_margin_pct 'Margem %',
                coalesce(pua.actual_qty_used,0) 'Uso Real'
                from production_recipe_items pri join products p on p.id=pri.product_id
                left join production_usage_actual pua
                  on pua.work_date=? and pua.recipe_id=pri.recipe_id and pua.product_id=pri.product_id
                where pri.recipe_id=? order by p.name""",c,params=[str(pdte),int(prid)])
            c.close()

            if pitems.empty:
                st.warning('Esta preparação ainda não tem padrão de ingrediente/corte.')
            else:
                work=pitems.copy()
                work['Qtd Produzida']=qty_prod
                work['Cortes Totais']=work['Qtd Produzida']*work['Unidades/Cortes']
                work['Uso Teórico']=work.apply(
                    lambda r:round_entry(
                        qty_prod*_stock_qty_from_grams(float(r['Gramatura Corte g'] or 0)*float(r['Unidades/Cortes'] or 0),r['Unidade'])
                    ) if float(r['Gramatura Corte g'] or 0)>0 and float(r['Unidades/Cortes'] or 0)>0
                    else round_entry(qty_prod*float(r['Qtd Padrão Direta'] or 0)),axis=1)

                use_editor=st.data_editor(
                    work[['product_id','Código','Produto','Unidade','Gramatura Corte g','Unidades/Cortes',
                          'Margem %','Cortes Totais','Uso Teórico','Uso Real']],
                    use_container_width=True,hide_index=True,key='prod_usage_editor_v111',
                    disabled=['product_id','Código','Produto','Unidade','Gramatura Corte g','Unidades/Cortes',
                              'Margem %','Cortes Totais','Uso Teórico'],
                    column_config={'Uso Real':st.column_config.NumberColumn(
                        'Uso Real do Ingrediente',min_value=0.0,step=0.001,format=num_format())}
                )

                check=use_editor.copy()
                check['Gramatura Real g']=check.apply(
                    lambda r:_grams_from_stock_qty(r['Uso Real'],r['Unidade'])/float(r['Cortes Totais'])
                    if float(r['Uso Real'] or 0)>0 and float(r['Cortes Totais'] or 0)>0 else 0,axis=1)
                check['Erro %']=check.apply(
                    lambda r:(float(r['Gramatura Real g'])-float(r['Gramatura Corte g']))/
                             float(r['Gramatura Corte g'])*100
                    if float(r['Gramatura Corte g'] or 0)>0 and float(r['Gramatura Real g'] or 0)>0 else 0,axis=1)
                check['Status']=check.apply(
                    lambda r:'SEM USO REAL' if float(r['Uso Real'] or 0)<=0
                    else ('OK' if abs(float(r['Erro %']))<=float(r['Margem %'] or 0) else 'FORA DO PADRÃO'),axis=1)
                st.dataframe(check[['Produto','Gramatura Corte g','Gramatura Real g','Erro %','Margem %','Status']],
                             use_container_width=True,hide_index=True)

                if st.button('✅ SALVAR PRODUÇÃO E USO REAL',type='primary',key='prod_save_v111'):
                    c=db()
                    try:
                        c.execute('BEGIN IMMEDIATE')
                        c.execute("""insert into production_output(work_date,recipe_id,qty_produced,notes)
                                     values(?,?,?,?)
                                     on conflict(work_date,recipe_id) do update set
                                     qty_produced=excluded.qty_produced,notes=excluded.notes""",
                                  (str(pdte),int(prid),round_entry(qty_prod),'Controle V11.2'))
                        for _,r in use_editor.iterrows():
                            c.execute("""insert into production_usage_actual(work_date,recipe_id,product_id,actual_qty_used,updated_at)
                                         values(?,?,?,?,?)
                                         on conflict(work_date,recipe_id,product_id) do update set
                                         actual_qty_used=excluded.actual_qty_used,updated_at=excluded.updated_at""",
                                      (str(pdte),int(prid),int(r['product_id']),round_entry(r['Uso Real']),
                                       datetime.now().isoformat(timespec='seconds')))
                        c.commit();set_flash('Produção e uso real gravados. Padrão de corte conferido.','success');st.rerun()
                    except Exception as ex:c.rollback();st.error(str(ex))
                    finally:c.close()

                confirm_out=st.checkbox('Confirmo excluir esta produção do dia',key='prod_out_del_confirm')
                if st.button('EXCLUIR PRODUÇÃO DO DIA',disabled=not confirm_out,key='prod_out_del_v111'):
                    c=db()
                    try:
                        c.execute('BEGIN IMMEDIATE')
                        c.execute("delete from production_usage_actual where work_date=? and recipe_id=?",
                                  (str(pdte),int(prid)))
                        c.execute("delete from production_output where work_date=? and recipe_id=?",
                                  (str(pdte),int(prid)))
                        c.commit();set_flash('Produção do dia excluída.','success');st.rerun()
                    except Exception as ex:c.rollback();st.error(str(ex))
                    finally:c.close()

    # ==========================================================
    # 3. FECHAMENTO DIÁRIO
    # ==========================================================
    with td:
        c=db()
        ctrl=pd.read_sql_query("""select cp.product_id,p.code,p.name,p.unit,
            cp.protein_family,cp.theoretical_source,
            cp.target_yield_pct,cp.variance_tolerance_pct
            from controlled_products cp join products p on p.id=cp.product_id
            where cp.active=1 order by cp.protein_family,p.name""",c);c.close()
        if ctrl.empty:
            st.info('Configure ao menos um Produto Controlado.')
        else:
            dt=st.date_input('Data do fechamento',date.today(),key='close_day_v111')
            pid=st.selectbox('SKU controlado',ctrl.product_id.tolist(),key='close_pid_v111',
                format_func=lambda x:f"{ctrl.loc[ctrl.product_id==x,'code'].iloc[0]} | "
                                     f"{ctrl.loc[ctrl.product_id==x,'name'].iloc[0]} | "
                                     f"{ctrl.loc[ctrl.product_id==x,'unit'].iloc[0]}")
            unit=str(ctrl.loc[ctrl.product_id==pid,'unit'].iloc[0])
            prev=previous_sushi_closing(dt,int(pid))
            c=db();existing=c.execute("select * from sushi_control_daily where work_date=? and product_id=?",
                                     (str(dt),int(pid))).fetchone();c.close()
            ex=dict(existing) if existing else {}
            raw_cost=round_entry(current_cost(int(pid),dt))
            prod_usage=round_entry(production_theoretical_usage(dt,int(pid)))
            sales_usage=round_entry(daily_sales_mix_theoretical_usage(dt,int(pid)))
            source=str(ctrl.loc[ctrl.product_id==pid,'theoretical_source'].iloc[0] or 'PRODUCTION')
            if source=='SALES':
                recipe_usage=sales_usage
            elif source=='BOTH':
                recipe_usage=round_entry(prod_usage+sales_usage)
            else:
                recipe_usage=prod_usage
            default_purchases=product_entries_qty(dt,int(pid))

            st.info(f'Estoque inicial automático = fechamento real anterior. '
                    f'Custo médio bruto do SKU: {brl(raw_cost)} | Fonte teórica: {source} | '
                    f'Produção: {prod_usage:.3f} {unit} | Vendas (Mix diário): {sales_usage:.3f} {unit} | '
                    f'Consumo teórico usado: {recipe_usage:.3f} {unit}')

            st.markdown('### A. Estoque Central — Produto inteiro / bruto')
            a1,a2,a3=st.columns(3)
            raw_open=a1.number_input('Estoque inicial bruto',min_value=0.0,
                value=float(ex.get('central_raw_opening',prev['central_raw_closing_actual']) or 0),
                step=0.001,format=num_format(),key='raw_open_v111')
            purchases=a2.number_input('Compras / Recebimentos brutos',min_value=0.0,
                value=float(ex.get('purchases_raw',default_purchases) or default_purchases),
                step=0.001,format=num_format(),key='raw_purchases_v111',
                help='Default: entradas de estoque deste SKU no dia.')
            raw_to_cut=a3.number_input('Quantidade enviada ao corte',min_value=0.0,
                value=float(ex.get('raw_to_cut',0) or 0),
                step=0.001,format=num_format(),key='raw_cut_v111')

            b1,b2,b3=st.columns(3)
            trim=b1.number_input('Perda registrada no corte',min_value=0.0,
                value=float(ex.get('trim_loss',0) or 0),step=0.001,format=num_format(),key='trim_v111')
            clean=b2.number_input('Produto limpo obtido',min_value=0.0,
                value=float(ex.get('clean_output',0) or 0),step=0.001,format=num_format(),key='clean_out_v111')
            raw_other=b3.number_input('Outra perda de produto bruto',min_value=0.0,
                value=float(ex.get('central_raw_other_loss',0) or 0),step=0.001,format=num_format(),key='raw_other_loss_v111')

            raw_close=st.number_input('Fechamento real bruto / inteiro',min_value=0.0,
                value=float(ex.get('central_raw_closing_actual',0) or 0),
                step=0.001,format=num_format(),key='raw_close_v111')

            st.markdown('### B. Estoque Central — Produto limpo')
            c1,c2,c3,c4=st.columns(4)
            clean_open=c1.number_input('Inicial produto limpo',min_value=0.0,
                value=float(ex.get('central_clean_opening',prev['central_clean_closing_actual']) or 0),
                step=0.001,format=num_format(),key='clean_open_v111')
            transfer=c2.number_input('Transferência Central → Loja',min_value=0.0,
                value=float(ex.get('central_transfer_store',0) or 0),
                step=0.001,format=num_format(),key='transfer_v111')
            clean_loss=c3.number_input('Perda produto limpo na Central',min_value=0.0,
                value=float(ex.get('central_clean_loss',0) or 0),
                step=0.001,format=num_format(),key='clean_loss_v111')
            clean_close=c4.number_input('Fechamento real produto limpo',min_value=0.0,
                value=float(ex.get('central_clean_closing_actual',0) or 0),
                step=0.001,format=num_format(),key='clean_close_v111')

            st.markdown('### C. Estoque Loja')
            d1,d2,d3=st.columns(3)
            store_open=d1.number_input('Estoque inicial Loja',min_value=0.0,
                value=float(ex.get('store_opening',prev['store_closing_actual']) or 0),
                step=0.001,format=num_format(),key='store_open_v111')
            waste=d2.number_input('Perda registrada Loja',min_value=0.0,
                value=float(ex.get('recorded_waste',0) or 0),
                step=0.001,format=num_format(),key='store_waste_v111')
            store_close=d3.number_input('Fechamento real Loja',min_value=0.0,
                value=float(ex.get('store_closing_actual',0) or 0),
                step=0.001,format=num_format(),key='store_close_v111')
            sync_receipt=st.checkbox('Recebimento da Loja = Transferência da Central',value=True,
                key='sync_receipt_v111')
            if sync_receipt:
                receipts=transfer
                st.info(f'Recebimento Loja sincronizado: {receipts:.3f} {unit}')
            else:
                receipts=st.number_input('Recebimento da Central na Loja',min_value=0.0,
                    value=float(ex.get('store_receipts',0) or 0),
                    step=0.001,format=num_format(),key='store_receipts_v111')
            manual=st.number_input('Consumo teórico manual adicional',min_value=0.0,
                value=float(ex.get('manual_theoretical_usage',0) or 0),
                step=0.001,format=num_format(),key='manual_theory_v111')

            vals={
                'central_raw_opening':raw_open,'purchases_raw':purchases,'raw_to_cut':raw_to_cut,
                'central_raw_other_loss':raw_other,'trim_loss':trim,'clean_output':clean,
                'central_raw_closing_actual':raw_close,
                'central_clean_opening':clean_open,'central_transfer_store':transfer,
                'central_clean_loss':clean_loss,'central_clean_closing_actual':clean_close,
                'store_opening':store_open,'store_receipts':receipts,'recorded_waste':waste,
                'store_closing_actual':store_close,'manual_theoretical_usage':manual,
                'recipe_theoretical_usage':recipe_usage,'avg_cost':raw_cost,
                'cost_yield_pct':prior_or_target_yield(
                    dt,int(pid),float(ctrl.loc[ctrl.product_id==pid,'target_yield_pct'].iloc[0] or 0)
                )
            }
            met=sushi_control_metrics(vals)

            st.markdown('### Resultado calculado')
            r1,r2,r3,r4=st.columns(4)
            r1.metric('Fechamento Bruto Teórico',f"{met['central_raw_theoretical']:.3f} {unit}")
            r2.metric('Diferença Bruto Real x Teórico',f"{met['central_raw_variance']:.3f} {unit}")
            r3.metric('Rendimento do Corte',f"{met['yield_pct']:.2f}%")
            r4.metric('Balanço do Corte',f"{met['cut_mass_variance']:.3f} {unit}",
                      help='Enviado ao corte − produto limpo − perda registrada. Ideal próximo de zero.')

            r5,r6,r7,r8=st.columns(4)
            r5.metric('Fechamento Limpo Teórico',f"{met['central_clean_theoretical']:.3f} {unit}")
            r6.metric('Diferença Limpo Real x Teórico',f"{met['central_clean_variance']:.3f} {unit}")
            r7.metric('Custo Médio Bruto',brl(raw_cost))
            r8.metric('Custo Efetivo Produto Limpo',brl(met['clean_cost']))

            r9,r10,r11,r12=st.columns(4)
            r9.metric('Consumo Real Loja',f"{met['actual_usage']:.3f} {unit}")
            r10.metric('Consumo Teórico',f"{met['theoretical_usage']:.3f} {unit}")
            r11.metric('Fechamento Loja Teórico',f"{met['store_theoretical_close']:.3f} {unit}")
            r12.metric('Variação não explicada',f"{met['unexplained_variance']:.3f} {unit}")

            r13,r14,r15,r16=st.columns(4)
            r13.metric('CMV Real Item',brl(met['actual_usage_cost']))
            r14.metric('Perdas Conhecidas',brl(met['known_loss_cost']))
            r15.metric('Custo da Variação',brl(met['unexplained_cost']))
            r16.metric('Variação %',f"{met['variance_pct']:.2f}%")

            target=float(ctrl.loc[ctrl.product_id==pid,'target_yield_pct'].iloc[0] or 0)
            tol=float(ctrl.loc[ctrl.product_id==pid,'variance_tolerance_pct'].iloc[0] or 3)

            if raw_to_cut>0 and abs(met['cut_mass_variance'])>0.001:
                st.warning('O balanço do corte não fecha: quantidade enviada ao corte ≠ produto limpo + perda registrada. '
                           'A diferença é uma perda/ganho ainda não explicada.')
            if target>0 and raw_to_cut>0 and met['yield_pct']<target:
                st.warning(f'Rendimento abaixo da meta: {met["yield_pct"]:.2f}% x {target:.2f}%.')
            if met['theoretical_usage']>0 and abs(met['variance_pct'])>tol:
                st.error(f'Consumo fora da tolerância de {tol:.2f}%. Investigar gramatura, porcionamento, perda não lançada, contagem ou desvio.')
            elif met['theoretical_usage']>0:
                st.success('Consumo dentro da tolerância configurada.')

            notes=st.text_area('Observações do fechamento',value=str(ex.get('notes','') or ''),key='close_notes_v111')
            if st.button('✅ SALVAR / ALTERAR FECHAMENTO',type='primary',key='close_save_v111'):
                c=db()
                try:
                    c.execute('BEGIN IMMEDIATE')
                    c.execute("""insert into sushi_control_daily(
                        work_date,product_id,central_raw_opening,purchases_raw,raw_to_cut,central_raw_other_loss,
                        trim_loss,clean_output,central_raw_closing_actual,
                        central_clean_opening,central_transfer_store,central_clean_loss,central_clean_closing_actual,
                        store_opening,store_receipts,store_closing_actual,recorded_waste,
                        manual_theoretical_usage,avg_cost,notes,updated_at)
                        values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                        on conflict(work_date,product_id) do update set
                        central_raw_opening=excluded.central_raw_opening,
                        purchases_raw=excluded.purchases_raw,raw_to_cut=excluded.raw_to_cut,
                        central_raw_other_loss=excluded.central_raw_other_loss,trim_loss=excluded.trim_loss,
                        clean_output=excluded.clean_output,central_raw_closing_actual=excluded.central_raw_closing_actual,
                        central_clean_opening=excluded.central_clean_opening,
                        central_transfer_store=excluded.central_transfer_store,central_clean_loss=excluded.central_clean_loss,
                        central_clean_closing_actual=excluded.central_clean_closing_actual,
                        store_opening=excluded.store_opening,store_receipts=excluded.store_receipts,
                        store_closing_actual=excluded.store_closing_actual,recorded_waste=excluded.recorded_waste,
                        manual_theoretical_usage=excluded.manual_theoretical_usage,avg_cost=excluded.avg_cost,
                        notes=excluded.notes,updated_at=excluded.updated_at""",
                        (str(dt),int(pid),round_entry(raw_open),round_entry(purchases),round_entry(raw_to_cut),
                         round_entry(raw_other),round_entry(trim),round_entry(clean),round_entry(raw_close),
                         round_entry(clean_open),round_entry(transfer),round_entry(clean_loss),round_entry(clean_close),
                         round_entry(store_open),round_entry(receipts),round_entry(store_close),round_entry(waste),
                         round_entry(manual),round_entry(raw_cost),notes,datetime.now().isoformat(timespec='seconds')))
                    propagate_next_opening(str(dt),int(pid),raw_close,clean_close,store_close,connection=c)
                    c.commit();set_flash('Fechamento gravado/alterado. Se já existir próximo fechamento, os estoques iniciais foram sincronizados.','success');st.rerun()
                except Exception as ex:c.rollback();st.error(str(ex))
                finally:c.close()

    # ==========================================================
    # 4. HISTÓRICO / EDITAR / EXCLUIR
    # ==========================================================
    with th:
        h1,h2=st.columns(2)
        hq=h1.text_input('🔎 Pesquisar produto',key='hist_search_v111')
        hdate=h2.date_input('Mostrar a partir de',date.today()-timedelta(days=30),key='hist_date_v111')
        c=db()
        like='%'+hq.strip()+'%'
        hist=pd.read_sql_query("""select scd.id,scd.work_date Data,p.code Código,p.name Produto,p.unit Unidade,
            scd.central_raw_opening 'Central Bruto Inicial',
            scd.purchases_raw Compras,scd.raw_to_cut 'Enviado Corte',
            scd.central_raw_other_loss 'Outra Perda Bruto',
            scd.trim_loss 'Perda Corte',scd.clean_output 'Produto Limpo',
            scd.central_raw_closing_actual 'Central Bruto Final',
            scd.central_clean_opening 'Central Limpo Inicial',
            scd.central_transfer_store 'Transferência Loja',
            scd.central_clean_loss 'Perda Central Limpo',
            scd.central_clean_closing_actual 'Central Limpo Final',
            scd.store_opening 'Loja Inicial',scd.store_receipts 'Loja Recebimento',
            scd.recorded_waste 'Perda Loja',scd.store_closing_actual 'Loja Final',
            scd.avg_cost 'Custo Médio',scd.notes Observações
            from sushi_control_daily scd join products p on p.id=scd.product_id
            where scd.work_date>=? and (?='' or p.name like ? or cast(p.code as text) like ?)
            order by scd.work_date desc,p.name""",c,params=[str(hdate),hq.strip(),like,like]);c.close()
        if hist.empty:
            st.info('Nenhum fechamento encontrado.')
        else:
            st.dataframe(hist,use_container_width=True,hide_index=True,height=420)
            hid=st.selectbox('Registro para alterar/excluir',hist.id.tolist(),key='hist_id_v111',
                format_func=lambda x:f"{hist.loc[hist.id==x,'Data'].iloc[0]} | {hist.loc[hist.id==x,'Código'].iloc[0]} | {hist.loc[hist.id==x,'Produto'].iloc[0]}")
            hr=hist[hist.id==hid].iloc[0]
            st.caption('Altere diretamente abaixo. O próximo dia continuará usando o fechamento real deste registro como abertura.')
            cols_edit=['Central Bruto Inicial','Compras','Enviado Corte','Outra Perda Bruto','Perda Corte','Produto Limpo',
                       'Central Bruto Final','Central Limpo Inicial','Transferência Loja','Perda Central Limpo',
                       'Central Limpo Final','Loja Inicial','Loja Recebimento','Perda Loja','Loja Final','Custo Médio']
            edit_df=pd.DataFrame([{c:hr[c] for c in cols_edit}])
            hedge=st.data_editor(edit_df,use_container_width=True,hide_index=True,key='hist_editor_v111',
                column_config={c:st.column_config.NumberColumn(step=0.001,format=num_format()) for c in cols_edit})
            hnotes=st.text_input('Observações',value=str(hr['Observações'] or ''),key='hist_notes_v111')
            hb1,hb2=st.columns(2)
            if hb1.button('SALVAR ALTERAÇÃO DO FECHAMENTO',type='primary',key='hist_save_v111'):
                r=hedge.iloc[0]
                c=db()
                try:
                    c.execute('BEGIN IMMEDIATE')
                    c.execute("""update sushi_control_daily set
                        central_raw_opening=?,purchases_raw=?,raw_to_cut=?,central_raw_other_loss=?,
                        trim_loss=?,clean_output=?,central_raw_closing_actual=?,central_clean_opening=?,
                        central_transfer_store=?,central_clean_loss=?,central_clean_closing_actual=?,
                        store_opening=?,store_receipts=?,recorded_waste=?,store_closing_actual=?,
                        avg_cost=?,notes=?,updated_at=? where id=?""",
                        tuple(round_entry(r[c]) for c in cols_edit[:-1])+
                        (round_entry(r['Custo Médio']),hnotes,datetime.now().isoformat(timespec='seconds'),int(hid)))
                    _row=c.execute("select work_date,product_id,central_raw_closing_actual,central_clean_closing_actual,store_closing_actual from sushi_control_daily where id=?",(int(hid),)).fetchone()
                    propagate_next_opening(_row['work_date'],int(_row['product_id']),
                                           _row['central_raw_closing_actual'],_row['central_clean_closing_actual'],
                                           _row['store_closing_actual'],connection=c)
                    c.commit();set_flash('Fechamento alterado e próximo estoque inicial sincronizado.','success');st.rerun()
                except Exception as ex:c.rollback();st.error(str(ex))
                finally:c.close()
            hconfirm=st.checkbox('Confirmo excluir este fechamento',key='hist_del_confirm_v111')
            if hb2.button('EXCLUIR FECHAMENTO',disabled=not hconfirm,key='hist_del_v111'):
                c=db()
                try:
                    c.execute('BEGIN IMMEDIATE')
                    before=c.execute("select * from sushi_control_daily where id=?",(int(hid),)).fetchone()
                    c.execute("delete from sushi_control_daily where id=?",(int(hid),))
                    if before:
                        relink_after_deleted_closing(before['work_date'],int(before['product_id']),connection=c)
                    c.execute("""insert into correction_audit(event_date,module,record_id,action,before_json,after_json)
                                 values(?,?,?,?,?,?)""",
                              (datetime.now().isoformat(timespec='seconds'),'CONTROLE PRODUÇÃO',str(hid),'EXCLUIR FECHAMENTO',
                               json.dumps(dict(before),ensure_ascii=False) if before else '{}','{}'))
                    c.commit();set_flash('Fechamento excluído.','success');st.rerun()
                except Exception as ex:c.rollback();st.error(str(ex))
                finally:c.close()

    # ==========================================================
    # 5. ANÁLISE
    # ==========================================================
    with ta:
        a1,a2=st.columns(2)
        da=a1.date_input('De',date.today().replace(day=1),key='analysis_a_v111')
        dbb=a2.date_input('Até',date.today(),key='analysis_b_v111')
        c=db()
        base=pd.read_sql_query("""select scd.*,p.code,p.name Produto,p.unit Unidade,
            cp.target_yield_pct,cp.variance_tolerance_pct
            from sushi_control_daily scd
            join products p on p.id=scd.product_id
            left join controlled_products cp on cp.product_id=scd.product_id
            where scd.work_date between ? and ?
            order by scd.work_date,p.name""",c,params=[str(da),str(dbb)])
        c.close()

        rows=[]
        for _,r in base.iterrows():
            d=r.to_dict()
            d['recipe_theoretical_usage']=production_theoretical_usage(d['work_date'],int(d['product_id']))
            d['cost_yield_pct']=prior_or_target_yield(
                d['work_date'],int(d['product_id']),float(d.get('target_yield_pct',0) or 0))
            met=sushi_control_metrics(d)
            rows.append({
                'Data':d['work_date'],'Código':d['code'],'Produto':d['Produto'],'Unidade':d['Unidade'],
                'Custo Médio Bruto':d['avg_cost'],'Custo Limpo':met['clean_cost'],
                'Enviado Corte':d.get('raw_to_cut',0),'Produto Limpo':d.get('clean_output',0),
                'Rendimento %':met['yield_pct'],'Perda Corte':d.get('trim_loss',0),
                'Perdas Conhecidas Qtd':met['known_loss_qty'],'Custo Perdas':met['known_loss_cost'],
                'Consumo Real':met['actual_usage'],'Consumo Teórico':met['theoretical_usage'],
                'Variação Não Explicada':met['unexplained_variance'],'Variação %':met['variance_pct'],
                'CMV Real Item':met['actual_usage_cost'],'CMV Teórico Item':met['theoretical_usage_cost'],
                'Custo Variação':met['unexplained_cost'],
                'Central Bruto Teórico':met['central_raw_theoretical'],
                'Central Bruto Real':d.get('central_raw_closing_actual',0),
                'Central Limpo Teórico':met['central_clean_theoretical'],
                'Central Limpo Real':d.get('central_clean_closing_actual',0),
                'Loja Teórico':met['store_theoretical_close'],
                'Loja Real':d.get('store_closing_actual',0)
            })
        rep=pd.DataFrame(rows)

        if rep.empty:
            st.info('Sem fechamentos no período.')
        else:
            total_cmv=float(rep['CMV Real Item'].sum())
            total_loss=float(rep['Custo Perdas'].sum())
            total_var=float(rep['Custo Variação'].sum())
            sales=consolidated_sales_value(da,dbb)
            k1,k2,k3,k4=st.columns(4)
            k1.metric('CMV dos Itens Controlados',brl(total_cmv))
            k2.metric('Perdas Conhecidas',brl(total_loss))
            k3.metric('Variação Não Explicada',brl(total_var))
            k4.metric('CMV Controlados / Vendas',f'{total_cmv/sales*100:.2f}%' if sales else '-')

            st.dataframe(rep,use_container_width=True,hide_index=True,height=520)
            export_buttons(rep,'CONTROLE_PRODUCAO_SUSHI','sushi_analysis_v111')

            agg=rep.groupby(['Código','Produto','Unidade'],as_index=False).agg({
                'Enviado Corte':'sum','Produto Limpo':'sum','Perda Corte':'sum',
                'Perdas Conhecidas Qtd':'sum','Custo Perdas':'sum',
                'Consumo Real':'sum','Consumo Teórico':'sum',
                'Variação Não Explicada':'sum','CMV Real Item':'sum',
                'CMV Teórico Item':'sum','Custo Variação':'sum'
            })
            agg['Rendimento Período %']=agg.apply(
                lambda r:r['Produto Limpo']/r['Enviado Corte']*100 if r['Enviado Corte'] else 0,axis=1)
            agg['Variação Consumo %']=agg.apply(
                lambda r:r['Variação Não Explicada']/r['Consumo Teórico']*100 if r['Consumo Teórico'] else 0,axis=1)
            st.subheader('Resumo por SKU')
            st.dataframe(agg,use_container_width=True,hide_index=True)
            export_buttons(agg,'RESUMO_SKUS_CONTROLADOS','sushi_agg_v111')

            st.subheader('Conferência de Padrão de Corte')
            cut_frames=[]
            cursor=da
            while cursor<=dbb:
                x=production_cut_lines(cursor)
                if not x.empty:cut_frames.append(x)
                cursor+=timedelta(days=1)
            cutsdf=pd.concat(cut_frames,ignore_index=True) if cut_frames else pd.DataFrame()
            if cutsdf.empty:
                st.info('Sem produções com padrão de corte no período.')
            else:
                st.dataframe(cutsdf,use_container_width=True,hide_index=True,height=420)
                bad=cutsdf[cutsdf['Status Corte']=='FORA DO PADRÃO']
                if not bad.empty:
                    st.error(f'{len(bad)} linha(s) de produção ficaram fora da margem de gramatura configurada.')
                export_buttons(cutsdf,'PADRAO_CORTE','cut_analysis_v111')


elif page=='Central de Correções':
    st.title('Central de Correções e Exclusões')
    st.caption('Regra geral: tudo que for digitado ou importado pode ser corrigido ou excluído. Notas, inventários e estoque inicial usam reabertura segura quando a alteração afeta estoque.')
    mod=st.selectbox('Módulo',['Vendas','Retiradas','Perdas','Cotações','Contagens','Itens de Fornecedor'])

    if mod=='Vendas':
        c=db();df=pd.read_sql_query("select * from sales order by sale_date desc,id desc",c);c.close()
        st.dataframe(df,use_container_width=True,height=300)
        if not df.empty:
            rid=st.selectbox('Registro',df.id.tolist(),key='corr_sales');r=df[df.id==rid].iloc[0]
            d=st.text_input('Data',str(r.sale_date));store=st.text_input('Loja',str(r.store or 'GERAL'));net=st.number_input('Venda total',value=float(r.net_sales or 0));delivery=st.number_input('Delivery',value=float(r.delivery or 0));notes=st.text_area('Observações',str(r.notes or ''))
            a,b=st.columns(2)
            if a.button('SALVAR ALTERAÇÃO'):
                c=db();c.execute("update sales set sale_date=?,store=?,net_sales=?,gross_sales=?,delivery=?,notes=? where id=?",(d,store,net,net,delivery,notes,rid));c.commit();c.close();st.rerun()
            if b.button('EXCLUIR REGISTRO'):
                c=db();c.execute("delete from sales where id=?",(rid,));c.commit();c.close();st.rerun()

    elif mod=='Retiradas':
        c=db();df=pd.read_sql_query("select m.id,m.movement_date Data,p.code Código,p.name Produto,m.qty Quantidade,m.unit_cost Custo,m.reference Referência,m.notes Observações from movements m join products p on p.id=m.product_id where m.type='WITHDRAWAL' order by m.id desc",c);c.close()
        st.dataframe(df,use_container_width=True,height=300)
        if not df.empty:
            rid=st.selectbox('Registro',df.id.tolist(),key='corr_with');r=df[df.id==rid].iloc[0]
            d=st.text_input('Data/hora',str(r.Data));q=st.number_input('Quantidade (saída negativa)',value=float(r.Quantidade));cost=st.number_input('Custo',value=float(r.Custo or 0),format=num_format());ref=st.text_input('Referência',str(r['Referência'] or ''));obs=st.text_area('Observações',str(r['Observações'] or ''))
            a,b=st.columns(2)
            if a.button('SALVAR RETIRADA'):c=db();c.execute("update movements set movement_date=?,qty=?,unit_cost=?,reference=?,notes=? where id=?",(d,q,cost,ref,obs,rid));c.commit();c.close();st.rerun()
            if b.button('EXCLUIR RETIRADA'):c=db();c.execute("delete from movements where id=?",(rid,));c.commit();c.close();st.rerun()

    elif mod=='Perdas':
        c=db();df=pd.read_sql_query("select l.id,l.loss_date Data,p.code Código,p.name Produto,l.qty Quantidade,l.unit_cost Custo,l.cause Causa,l.notes Observações from losses l join products p on p.id=l.product_id order by l.id desc",c);c.close()
        st.dataframe(df,use_container_width=True,height=300)
        if not df.empty:
            rid=st.selectbox('Registro',df.id.tolist(),key='corr_loss');r=df[df.id==rid].iloc[0]
            d=st.text_input('Data',str(r.Data));q=st.number_input('Quantidade',min_value=0.0,value=float(r.Quantidade));cost=st.number_input('Custo',min_value=0.0,value=float(r.Custo or 0),format=num_format());cause=st.text_input('Causa',str(r.Causa or ''));obs=st.text_area('Observações',str(r['Observações'] or ''))
            a,b=st.columns(2)
            if a.button('SALVAR PERDA'):c=db();c.execute("update losses set loss_date=?,qty=?,unit_cost=?,cause=?,notes=? where id=?",(d,q,cost,cause,obs,rid));c.commit();c.close();st.rerun()
            if b.button('EXCLUIR PERDA'):c=db();c.execute("delete from losses where id=?",(rid,));c.commit();c.close();st.rerun()

    elif mod=='Cotações':
        c=db();df=pd.read_sql_query("select q.*,p.name Produto,s.legal_name Fornecedor from quotes q join products p on p.id=q.product_id left join suppliers s on s.id=q.supplier_id order by q.id desc",c);c.close()
        st.dataframe(df,use_container_width=True,height=300)
        if not df.empty:
            rid=st.selectbox('Registro',df.id.tolist(),key='corr_quote');r=df[df.id==rid].iloc[0]
            price=st.number_input('Preço oferta',min_value=0.0,value=float(r.offer_price or 0),format=num_format());freight=st.number_input('Frete',min_value=0.0,value=float(r.freight or 0));disc=st.number_input('Desconto',min_value=0.0,value=float(r.discount or 0));notes=st.text_area('Observações',str(r.notes or ''))
            a,b=st.columns(2)
            if a.button('SALVAR COTAÇÃO'):
                uc=(price+freight-disc)/(float(r.qty or 0)*float(r.conversion or 1)) if float(r.qty or 0)*float(r.conversion or 1) else 0
                c=db();c.execute("update quotes set offer_price=?,freight=?,discount=?,unit_cost=?,notes=? where id=?",(price,freight,disc,uc,notes,rid));c.commit();c.close();st.rerun()
            if b.button('EXCLUIR COTAÇÃO'):c=db();c.execute("delete from quotes where id=?",(rid,));c.commit();c.close();st.rerun()

    elif mod=='Contagens':
        c=db();df=pd.read_sql_query("select c.*,p.name Produto from counts c join products p on p.id=c.product_id order by c.id desc",c);c.close()
        st.dataframe(df,use_container_width=True,height=300)
        if not df.empty:
            rid=st.selectbox('Registro',df.id.tolist(),key='corr_count');r=df[df.id==rid].iloc[0]
            q=st.number_input('Quantidade contada',min_value=0.0,value=float(r.counted_qty or 0));target=st.number_input('Estoque alvo',min_value=0.0,value=float(r.target_stock or 0));notes=st.text_area('Observações',str(r.notes or ''))
            a,b=st.columns(2)
            if a.button('SALVAR CONTAGEM'):c=db();c.execute("update counts set counted_qty=?,target_stock=?,suggested_qty=?,notes=? where id=?",(q,target,max(0,target-q),notes,rid));c.commit();c.close();st.rerun()
            if b.button('EXCLUIR CONTAGEM'):c=db();c.execute("delete from counts where id=?",(rid,));c.commit();c.close();st.rerun()

    else:
        c=db();df=pd.read_sql_query("""select sci.id,s.legal_name Fornecedor,sci.supplier_code Código,sci.description Descrição,sci.barcode Barcode,sci.supplier_price Preço,sci.active Ativo
            from supplier_catalog_items sci join suppliers s on s.id=sci.supplier_id order by sci.id desc""",c);c.close()
        st.dataframe(df,use_container_width=True,height=300)
        if not df.empty:
            rid=st.selectbox('Registro',df.id.tolist(),key='corr_supitem');r=df[df.id==rid].iloc[0]
            desc=st.text_input('Descrição',str(r['Descrição']));bar=st.text_input('Barcode',str(r.Barcode or ''));price=st.number_input('Preço',min_value=0.0,value=float(r['Preço'] or 0),format=num_format())
            a,b=st.columns(2)
            if a.button('SALVAR ITEM'):c=db();c.execute("update supplier_catalog_items set description=?,barcode=?,supplier_price=?,updated_at=? where id=?",(desc,bar,price,datetime.now().isoformat(),rid));c.commit();c.close();st.rerun()
            if b.button('EXCLUIR ITEM'):c=db();c.execute("update supplier_catalog_items set active=0 where id=?",(rid,));c.commit();c.close();st.rerun()


elif page=='Config. Operacional':
    st.title('Configuração Operacional')
    st.caption('Configura categorias, corrige cadastro de produtos e permite reabrir entradas para correção com estorno seguro.')

    tabc,tabp,tabe=st.tabs(['Categorias','Produtos','Corrigir Entradas'])

    with tabc:
        c=db()
        catsdb=pd.read_sql_query("""select distinct coalesce(category,'SEM CATEGORIA') Categoria from products order by 1""",c)
        for cat in catsdb.Categoria.tolist():
            c.execute("""insert or ignore into category_settings(category,updated_at) values(?,?)""",
                      (cat,datetime.now().isoformat(timespec='seconds')))
        c.commit()
        cfgcat=pd.read_sql_query("""select category Categoria,
            include_inventory 'Inventário',
            include_purchase_reports 'Relatório Compras',
            include_cmv 'CMV',
            include_production 'Controle Produção'
            from category_settings order by category""",c);c.close()
        ed=st.data_editor(cfgcat,use_container_width=True,hide_index=True,key='cat_settings_editor',
            disabled=['Categoria'],
            column_config={
                'Inventário':st.column_config.CheckboxColumn(),
                'Relatório Compras':st.column_config.CheckboxColumn(),
                'CMV':st.column_config.CheckboxColumn(),
                'Controle Produção':st.column_config.CheckboxColumn()
            })
        if st.button('SALVAR CONFIGURAÇÃO DE CATEGORIAS',type='primary',key='save_cat_cfg'):
            c=db()
            for _,r in ed.iterrows():
                c.execute("""update category_settings set include_inventory=?,include_purchase_reports=?,
                             include_cmv=?,include_production=?,updated_at=? where category=?""",
                          (int(bool(r['Inventário'])),int(bool(r['Relatório Compras'])),
                           int(bool(r['CMV'])),int(bool(r['Controle Produção'])),
                           datetime.now().isoformat(timespec='seconds'),str(r['Categoria'])))
            c.commit();c.close();set_flash('Configuração de categorias salva.','success');st.rerun()

        st.divider()
        st.subheader('🔗 Unificar Categorias com Cadeia de Caracteres Equivalente')
        st.caption('Detecta automaticamente nomes que são iguais quando ignoramos caixa, acentos, pontuação e espaços. Ex.: PEIXARIA, peixaria e " Peixária ". Não une singular/plural ou nomes semanticamente diferentes sem sua decisão.')
        dup_groups=duplicate_category_groups()
        if not dup_groups:
            st.success('Nenhuma categoria com cadeia equivalente duplicada foi encontrada.')
        else:
            c=db()
            dup_rows=[]
            for normkey,variants in dup_groups.items():
                pcount=0;lcount=0
                for v in variants:
                    pcount+=int(c.execute("select count(*) n from products where category=?",(v,)).fetchone()['n'] or 0)
                    lcount+=int(c.execute("select count(*) n from loose_purchases where category=?",(v,)).fetchone()['n'] or 0)
                dup_rows.append({
                    'Chave normalizada':normkey,
                    'Variações encontradas':' | '.join(variants),
                    'Qtd nomes':len(variants),
                    'Produtos afetados':pcount,
                    'Compras avulsas afetadas':lcount
                })
            c.close()
            dupdf=pd.DataFrame(dup_rows)
            st.dataframe(dupdf,use_container_width=True,hide_index=True)

            norm_sel=st.selectbox('Grupo duplicado para unificar',list(dup_groups.keys()),
                                  key='cat_dup_group_v114',
                                  format_func=lambda x:' | '.join(dup_groups[x]))
            variants=dup_groups[norm_sel]
            canonical_existing=st.selectbox('Escolha o nome único que deve permanecer',variants,
                                             key='cat_dup_canonical_v114')
            custom_canonical=st.text_input('Ou informe outro nome canônico (opcional)',
                                           key='cat_dup_custom_v114',
                                           placeholder='Se preenchido, substitui a escolha acima')
            canonical=(custom_canonical.strip() or canonical_existing.strip())
            st.info('Após confirmar, produtos e compras avulsas passam para o nome escolhido. Inventários, movimentos, perdas, notas e controles históricos continuam ligados aos mesmos produtos e passam a refletir a categoria unificada automaticamente.')
            dup_reason=st.text_input('Motivo / observação da unificação',
                                     value='Padronização de categorias com cadeia equivalente',
                                     key='cat_dup_reason_v114')
            dup_confirm=st.checkbox(f'Confirmo unificar {len(variants)} nomes em "{canonical}"',
                                    key='cat_dup_confirm_v114')
            if st.button('UNIFICAR CATEGORIAS E CORRIGIR REFERÊNCIAS',type='primary',
                         disabled=not dup_confirm,key='cat_dup_merge_btn_v114'):
                try:
                    result=merge_category_group(variants,canonical,dup_reason)
                    set_flash(f'Categorias unificadas em {result["canonical"]}. '
                              f'{result["products"]} produto(s) corrigido(s).','success')
                    st.rerun()
                except Exception as ex:
                    st.error(str(ex))

        st.divider()
        st.subheader('Renomear / Mesclar Categorias')
        st.caption('Use para unir categorias equivalentes, por exemplo PEIXE → PEIXES. Produtos, compras avulsas e configurações passam para o novo nome.')
        c=db()
        _cats=[r['category'] for r in c.execute("select category from category_settings order by category").fetchall()]
        c.close()
        if _cats:
            old_cat=st.selectbox('Categoria atual',_cats,key='cat_merge_old')
            new_cat=st.text_input('Novo nome / categoria de destino',key='cat_merge_new',
                                  placeholder='Ex.: PEIXES')
            c=db();_ncat=c.execute("select count(*) n from products where category=?",(old_cat,)).fetchone()['n'];c.close()
            st.info(f'{_ncat} produto(s) serão alterados de {old_cat} para o novo nome.')
            cat_notes=st.text_input('Motivo / observação',key='cat_merge_notes')
            cat_confirm=st.checkbox('Confirmo renomear/mesclar esta categoria',key='cat_merge_confirm')
            if st.button('RENOMEAR / MESCLAR CATEGORIA',type='primary',
                         disabled=(not cat_confirm or not new_cat.strip()),key='cat_merge_btn'):
                try:
                    n=rename_merge_category(old_cat,new_cat.strip(),cat_notes)
                    set_flash(f'Categoria atualizada. {n} produto(s) migrados para {new_cat.strip()}.','success')
                    st.rerun()
                except Exception as ex:
                    st.error(str(ex))

        st.subheader('Criar Categoria')
        new_only=st.text_input('Nome da nova categoria',key='cat_create_name')
        if st.button('CRIAR CATEGORIA',disabled=not new_only.strip(),key='cat_create_btn'):
            c=db()
            c.execute("insert or ignore into category_settings(category,updated_at) values(?,?)",
                      (new_only.strip(),datetime.now().isoformat(timespec='seconds')))
            c.commit();c.close();set_flash('Categoria criada.','success');st.rerun()

        c=db()
        ah=pd.read_sql_query("""select event_date Data,old_category "Categoria Anterior",
            new_category "Nova Categoria",products_affected "Produtos Alterados",notes Observações
            from category_alias_audit order by id desc limit 100""",c)
        c.close()
        if not ah.empty:
            with st.expander('Histórico de renomeações / mesclagens'):
                st.dataframe(ah,use_container_width=True,hide_index=True)

    with tabp:
        q=st.text_input('🔎 Pesquisar produto',key='cfg_product_search')
        pro=search_products_sql(q,1000,include_inactive=True)
        if not pro.empty:
            ped=st.data_editor(pro[['id','Código','Produto','Marca','Categoria','Subcategoria','Unidade','Custo','Ativo']],
                use_container_width=True,hide_index=True,height=520,key='cfg_product_editor',
                disabled=['id','Código'],
                column_config={
                    'Categoria':st.column_config.SelectboxColumn(
                        'Categoria',
                        options=sorted(list(set(
                            products('').Categoria.dropna().astype(str).tolist()
                            + allowed_categories('include_inventory')
                        )))
                    ),
                    'Custo':st.column_config.NumberColumn('Custo Médio Vigente',min_value=0.0,step=0.001,format='R$ '+num_format()),
                    'Ativo':st.column_config.CheckboxColumn()
                })
            if st.button('SALVAR ALTERAÇÕES DE PRODUTOS',type='primary',key='cfg_prod_save'):
                c=db()
                try:
                    c.execute('BEGIN IMMEDIATE')
                    for _,r in ped.iterrows():
                        pid=int(r['id'])
                        c.execute("""update products set name=?,brand=?,category=?,subcategory=?,unit=?,active=? where id=?""",
                                  (str(r['Produto'] or '').strip(),str(r['Marca'] or '').strip(),
                                   str(r['Categoria'] or '').strip(),str(r['Subcategoria'] or '').strip(),
                                   str(r['Unidade'] or '').strip(),int(bool(r['Ativo'])),pid))
                        new_cost=round_entry(r['Custo'] or 0)
                        old_cost_row=c.execute("select current_cost from cost_master where product_id=?",(pid,)).fetchone()
                        old_cost=float(old_cost_row['current_cost'] or 0) if old_cost_row else 0.0
                        if abs(new_cost-old_cost)>0.000001:
                            now=datetime.now().isoformat(timespec='seconds')
                            c.execute("""insert into cost_master(product_id,current_cost,updated_at,notes)
                                         values(?,?,?,?)
                                         on conflict(product_id) do update set current_cost=excluded.current_cost,
                                         updated_at=excluded.updated_at,notes=excluded.notes""",
                                      (pid,new_cost,now,'Correção manual Config. Operacional'))
                            c.execute("""insert into cost_history(product_id,event_date,cost,source,reference,notes)
                                         values(?,?,?,?,?,?)""",
                                      (pid,now,new_cost,'CORREÇÃO MANUAL','Config. Operacional',
                                       f'Custo anterior {old_cost:.3f}'))
                    c.commit();clear_data_cache()
                    set_flash('Cadastros de produtos atualizados.','success');st.rerun()
                except Exception as ex:
                    c.rollback();st.error(str(ex))
                finally:c.close()

    with tabe:
        c=db()
        nfs=pd.read_sql_query("""select i.id,i.number NF,i.issue_date Emissão,i.status Status,
            s.legal_name Fornecedor,i.total Valor
            from invoices i left join suppliers s on s.id=i.supplier_id
            order by i.id desc limit 300""",c);c.close()
        if nfs.empty:
            st.info('Nenhuma nota cadastrada.')
        else:
            nf_id=st.selectbox('Nota para corrigir',nfs.id.tolist(),key='corr_nf_id',
                format_func=lambda x:f"NF {nfs.loc[nfs.id==x,'NF'].iloc[0]} | {nfs.loc[nfs.id==x,'Fornecedor'].iloc[0]} | {nfs.loc[nfs.id==x,'Status'].iloc[0]}")
            status=str(nfs.loc[nfs.id==nf_id,'Status'].iloc[0]).upper()
            if status=='ENTRADA':
                st.warning('A nota já movimentou estoque. Para corrigir, primeiro reabra; o sistema estorna a entrada e recalcula custos.')
                if st.button('REABRIR NOTA PARA CORRIGIR',type='primary',key='corr_reopen'):
                    reopen_invoice(int(nf_id));set_flash('Nota reaberta e estoque/custos da entrada estornados.','success');st.rerun()
            else:
                labels,label_to_id,id_to_label=invoice_product_options()
                c=db()
                it=pd.read_sql_query("""select ii.id,ii.description 'Item NF',ii.barcode Barcode,
                    coalesce(nullif(ii.commercial_unit,''),ii.xml_unit,'') 'Un. Comercial',
                    coalesce(nullif(ii.stock_unit,''),p.unit,'') 'Un. Estoque',
                    ii.xml_qty 'Qtd Fiscal',ii.xml_total 'Valor Item',
                    coalesce(ii.multiplier,1) 'Fator Mult.',coalesce(ii.conversion,1) 'Fator Conv.',
                    ii.product_id from invoice_items ii left join products p on p.id=ii.product_id
                    where ii.invoice_id=? order by ii.id""",c,params=[int(nf_id)]);c.close()
                if it.empty:
                    st.info('Nota sem itens.')
                else:
                    it['Produto Associado']=it.product_id.apply(
                        lambda x:id_to_label.get(int(x),'— NÃO ASSOCIADO —') if pd.notna(x) else '— NÃO ASSOCIADO —')
                    ed=st.data_editor(it[['id','Item NF','Barcode','Un. Comercial','Un. Estoque','Qtd Fiscal',
                        'Valor Item','Fator Mult.','Fator Conv.','Produto Associado']],
                        use_container_width=True,hide_index=True,height=500,key='corr_items_editor',
                        disabled=['id'],
                        column_config={
                            'Produto Associado':st.column_config.SelectboxColumn(options=labels),
                            'Qtd Fiscal':st.column_config.NumberColumn(step=0.001,format=num_format()),
                            'Valor Item':st.column_config.NumberColumn(step=0.001,format='R$ '+num_format()),
                            'Fator Mult.':st.column_config.NumberColumn(step=0.001,format=num_format()),
                            'Fator Conv.':st.column_config.NumberColumn(step=0.001,format=num_format())
                        })
                    if st.button('SALVAR CORREÇÕES DA ENTRADA',type='primary',key='corr_save_items'):
                        try:
                            res=save_invoice_grid(int(nf_id),ed,label_to_id,True)
                            set_flash('Correções salvas. Confira e dê entrada novamente na tela de Notas / XML.','success');st.rerun()
                        except Exception as ex:st.error(str(ex))

elif page=='Assistente IA':
    st.title('Assistente IA - Sem Assinatura Paga')
    st.caption('Usa a faixa gratuita da Gemini API quando uma chave gratuita é configurada. Os limites do plano gratuito são definidos pelo Google.')
    st.info('No modo local, a chave da IA pode ser configurada por variável de ambiente GEMINI_API_KEY. A chave não precisa ser gravada no banco.')
    q=st.text_area('Pergunte qualquer coisa',height=120,placeholder='Ex.: Qual categoria mais pesa nas compras? Como está meu CMV? Explique a diferença entre custo médio e último custo.')
    if st.button('PERGUNTAR À IA',type='primary') and q.strip():
        try:
            ans=ask_free_ai(q.strip())
            st.markdown(ans)
            app_log('Assistente IA','Pergunta',q[:200])
        except Exception as e:st.error(str(e))

elif page=='Etiquetas':
    st.title('Etiquetas - Código de Barras e Impressão')
    st.caption('Regra automática: produtos pesáveis usam código interno; demais produtos usam o código de barras do fornecedor. Você pode revisar/alterar o código antes de imprimir.')
    LOGO_DIR=DATA_DIR/'logos';LOGO_DIR.mkdir(exist_ok=True)
    logo_file=st.file_uploader('Logo em miniatura',type=['png','jpg','jpeg'],key='label_logo2')
    logo_path=None
    if logo_file:
        logo_path=LOGO_DIR/('logo_etiqueta.'+logo_file.name.split('.')[-1].lower());logo_path.write_bytes(logo_file.read());confirm_success('Logo salvo.')
    elif list(LOGO_DIR.glob('logo_etiqueta.*')):
        logo_path=list(LOGO_DIR.glob('logo_etiqueta.*'))[0]

    st.subheader('1. Selecionar produtos')
    allp=products('');cats=sorted(allp.Categoria.unique().tolist());sc=st.multiselect('Filtrar categorias',cats,key='labelcats4');d=allp if not sc else allp[allp.Categoria.isin(sc)]
    search=st.text_input('🔎 Filtrar produtos por código, nome ou categoria',key='labelsearch4')
    if search:d=d[d.apply(lambda r:search.lower() in (str(r.Código)+' '+r.Produto+' '+r.Categoria).lower(),axis=1)]
    selected=st.multiselect('Produtos para impressão',d.id.tolist(),format_func=lambda x:f"{int(d.loc[d.id==x,'Código'].iloc[0])} - {d.loc[d.id==x,'Produto'].iloc[0]} | {d.loc[d.id==x,'Categoria'].iloc[0]}")

    st.subheader('2. Layout')
    origem=st.text_input('Origem / fornecedor / produção',value='Estoque interno',key='label_origin4')
    validade=st.date_input('Validade',date.today()+timedelta(days=7),key='label_valid4')
    c1,c2,c3,c4=st.columns(4);w=c1.number_input('Largura (mm)',20.0,150.0,60.0,key='labw4');h=c2.number_input('Altura (mm)',15.0,120.0,40.0,key='labh4');cols=c3.number_input('Colunas',1,6,3,key='labcols4');copies=c4.number_input('Cópias por produto',1,100,1,key='labcopies4')
    c5,c6=st.columns(2);gap=c5.number_input('Espaço (mm)',0.0,15.0,2.0,key='labgap4');margin=c6.number_input('Margem (mm)',0.0,25.0,5.0,key='labmargin4')

    if selected:
        rows=[];c=db()
        for pid in selected:
            pr=c.execute('select * from products where id=?',(pid,)).fetchone()
            bc,rule=preferred_barcode_for_label(pid)
            rows.append({'id':pid,'code':pr['code'],'name':pr['name'],'category':pr['category'],
                         'internal_barcode':pr['internal_barcode'],'barcode':bc,'rule':rule,
                         'origin':origem,'validity':validade.strftime('%d/%m/%Y')})
        c.close()
        editor=pd.DataFrame(rows)[['id','code','name','category','rule','barcode']]
        editor.columns=['id','Código','Produto','Categoria','Regra','Código de barras para imprimir']
        edited=st.data_editor(editor,use_container_width=True,hide_index=True,
            disabled=['id','Código','Produto','Categoria','Regra'],
            column_config={'Código de barras para imprimir':st.column_config.TextColumn('Código de barras para imprimir',help='Você pode informar/corrigir o código antes da impressão.')},
            key='label_editor4')
        final_rows=[]
        missing=[]
        for _,rr in edited.iterrows():
            base=next(x for x in rows if int(x['id'])==int(rr['id']))
            base['barcode']=str(rr['Código de barras para imprimir'] or '').strip()
            if not base['barcode']:missing.append(base['name'])
            final_rows.append(base)
        if missing:
            st.warning('Sem barcode para impressão: '+', '.join(missing[:20])+'. Para itens não pesáveis, cadastre o barcode do fornecedor ou informe-o na grade.')
        else:
            confirm_success('Todos os produtos possuem código de barras para impressão.')

        st.subheader('3. Gerar e imprimir')
        pdf=label_pdf([r for r in final_rows if r['barcode']],w,h,cols,gap,margin,copies,'Automático',logo_path)
        st.download_button('BAIXAR PDF DAS ETIQUETAS',pdf,'ETIQUETAS_PRODUTOS.pdf','application/pdf')

        # HTML com SVG real do código de barras + print() do navegador.
        html_items=[]
        for r in final_rows:
            if not r['barcode']:continue
            try:
                kind='EAN13' if str(r['barcode']).isdigit() and len(str(r['barcode']))==13 else 'Code128'
                drawing=createBarcodeDrawing(kind,value=str(r['barcode']),barHeight=12*mm,humanReadable=True)
                svg=renderSVG.drawToString(drawing).decode('utf-8') if isinstance(renderSVG.drawToString(drawing),bytes) else renderSVG.drawToString(drawing)
            except Exception:
                svg=f"<div>{r['barcode']}</div>"
            html_items.append(f"""<div class="lbl"><div class="nm">{r['name']}</div>
            <div>Origem: {origem}</div><div>Validade: {validade.strftime('%d/%m/%Y')}</div>
            <div>Regra: {r['rule']}</div><div class="bc">{svg}</div></div>""")
        html=f"""<html><head><style>
        @page{{margin:{margin}mm}} body{{font-family:Arial;margin:0}}
        .grid{{display:grid;grid-template-columns:repeat({int(cols)},{w}mm);gap:{gap}mm}}
        .lbl{{width:{w}mm;height:{h}mm;border:1px solid #111;box-sizing:border-box;padding:2mm;font-size:8pt;overflow:hidden}}
        .nm{{font-weight:bold;font-size:9pt}} .bc svg{{max-width:95%;height:auto;max-height:{max(8,h-20)}mm}}
        @media print{{button{{display:none}}}}
        </style></head><body><button onclick="window.print()">🖨️ IMPRIMIR</button><div class="grid">{''.join(html_items)}</div></body></html>"""

        st.markdown('**Botão de impressão:** abre o diálogo da impressora do aparelho que está acessando o sistema.')
        if st.button('🖨️ IMPRIMIR ETIQUETAS',type='primary',key='print_labels4'):
            components.html(html,height=700,scrolling=True)
            app_log('Etiquetas','Impressão',f'{len(final_rows)} produtos')
    else:
        st.info('Selecione um ou mais produtos para habilitar a impressão.')


elif page=='Usuários & Acessos':
    st.title('Usuários & Acessos')
    st.caption('Cadastre usuários, defina perfil e módulos liberados. Senhas são armazenadas com scrypt + salt, nunca em texto puro.')

    auth=current_user()
    if not auth or auth.get('role')!='ADMIN':
        st.error('Somente administradores podem acessar este módulo.')
        st.stop()

    tab_new,tab_manage,tab_me=st.tabs(['Novo Usuário','Gerenciar Usuários','Minha Senha'])

    with tab_new:
        st.subheader('Criar usuário')
        with st.form('create_user_form_v115'):
            u1,u2=st.columns(2)
            username=u1.text_input('Login')
            full_name=u2.text_input('Nome completo')
            email=st.text_input('E-mail (opcional)')
            role=st.selectbox('Perfil',list(ROLE_DEFAULT_MODULES.keys()),index=3)
            default_mods=list(ROLE_DEFAULT_MODULES.get(role,[]))
            modules=st.multiselect('Módulos liberados',ALL_MODULES,
                                   default=default_mods if role!='ADMIN' else ALL_MODULES)
            p1,p2=st.columns(2)
            password=p1.text_input('Senha inicial',type='password')
            password2=p2.text_input('Confirmar senha',type='password')
            force_change=st.checkbox('Exigir troca de senha no primeiro acesso',value=True)
            create_btn=st.form_submit_button('CRIAR USUÁRIO',type='primary')
        if create_btn:
            try:
                if password!=password2:raise ValueError('As senhas não conferem.')
                create_user(username,full_name,password,role,email,modules,force_change)
                app_log('Usuários','Criar usuário',username)
                set_flash(f'Usuário {username} criado.','success');st.rerun()
            except Exception as ex:st.error(str(ex))

    with tab_manage:
        c=db()
        users=pd.read_sql_query("""select id,username Login,full_name Nome,email Email,role Perfil,
            active Ativo,allowed_modules Módulos,must_change_password 'Troca Obrigatória',
            last_login 'Último Login',created_at Criado
            from app_users order by active desc,full_name,username""",c)
        c.close()
        if users.empty:
            st.info('Nenhum usuário cadastrado.')
        else:
            overview=users.copy()
            overview['Módulos']=overview['Módulos'].apply(
                lambda x:len(json.loads(x or '[]')) if str(x or '').strip().startswith('[') else 0
            )
            overview['Ativo']=overview['Ativo'].apply(lambda x:'SIM' if int(x or 0) else 'NÃO')
            overview['Troca Obrigatória']=overview['Troca Obrigatória'].apply(lambda x:'SIM' if int(x or 0) else 'NÃO')
            st.dataframe(overview,use_container_width=True,hide_index=True,height=350)

            uid=st.selectbox('Usuário para editar',users.id.tolist(),key='user_manage_uid_v115',
                format_func=lambda x:f"{users.loc[users.id==x,'Nome'].iloc[0]} | "
                                     f"{users.loc[users.id==x,'Login'].iloc[0]} | "
                                     f"{users.loc[users.id==x,'Perfil'].iloc[0]}")
            row=users[users.id==uid].iloc[0]
            try:current_modules=json.loads(row['Módulos'] or '[]')
            except Exception:current_modules=[]
            if not current_modules:current_modules=list(ROLE_DEFAULT_MODULES.get(str(row['Perfil']).upper(),[]))

            e1,e2=st.columns(2)
            ename=e1.text_input('Nome completo',value=str(row['Nome'] or ''),key=f'user_name_{uid}')
            eemail=e2.text_input('E-mail',value=str(row['Email'] or ''),key=f'user_email_{uid}')
            roles=list(ROLE_DEFAULT_MODULES.keys())
            erole=st.selectbox('Perfil',roles,index=roles.index(str(row['Perfil']).upper()) if str(row['Perfil']).upper() in roles else 3,
                               key=f'user_role_{uid}')
            eactive=st.checkbox('Usuário ativo',value=bool(int(row['Ativo'] or 0)),key=f'user_active_{uid}')
            emods=st.multiselect('Módulos liberados',ALL_MODULES,
                                 default=ALL_MODULES if erole=='ADMIN' else [m for m in current_modules if m in ALL_MODULES],
                                 key=f'user_modules_{uid}')
            if erole=='ADMIN':
                st.info('ADMIN sempre possui acesso a todos os módulos.')
            confirm_edit=st.checkbox('Confirmo salvar as alterações deste usuário',key=f'user_confirm_edit_{uid}')
            if st.button('SALVAR USUÁRIO',type='primary',disabled=not confirm_edit,key=f'user_save_{uid}'):
                try:
                    if int(uid)==int(auth['id']) and not eactive:
                        raise ValueError('Você não pode desativar o próprio usuário durante a sessão.')
                    update_user_record(uid,ename,eemail,erole,eactive,emods)
                    app_log('Usuários','Alterar usuário',f'ID {uid}')
                    set_flash('Usuário atualizado.','success');st.rerun()
                except Exception as ex:st.error(str(ex))

            st.divider()
            st.markdown('**Redefinir senha**')
            np1,np2=st.columns(2)
            newp=np1.text_input('Nova senha',type='password',key=f'user_reset_pw_{uid}')
            newp2=np2.text_input('Confirmar nova senha',type='password',key=f'user_reset_pw2_{uid}')
            must=st.checkbox('Exigir troca no próximo acesso',value=True,key=f'user_reset_must_{uid}')
            creset=st.checkbox('Confirmo redefinir a senha deste usuário',key=f'user_reset_confirm_{uid}')
            if st.button('REDEFINIR SENHA',disabled=not creset,key=f'user_reset_btn_{uid}'):
                try:
                    if newp!=newp2:raise ValueError('As senhas não conferem.')
                    reset_user_password(uid,newp,must)
                    app_log('Usuários','Redefinir senha',f'ID {uid}')
                    set_flash('Senha redefinida.','success');st.rerun()
                except Exception as ex:st.error(str(ex))

    with tab_me:
        st.subheader('Alterar minha senha')
        with st.form('my_password_form_v115'):
            oldp=st.text_input('Senha atual',type='password')
            np=st.text_input('Nova senha',type='password')
            np2=st.text_input('Confirmar nova senha',type='password')
            btn=st.form_submit_button('ALTERAR MINHA SENHA',type='primary')
        if btn:
            try:
                if np!=np2:raise ValueError('As novas senhas não conferem.')
                change_own_password(auth['id'],oldp,np)
                user,_=authenticate_user(auth['username'],np)
                st.session_state['_auth_user']=user
                app_log('Segurança','Alterar senha própria',auth['username'])
                set_flash('Senha alterada com sucesso.','success');st.rerun()
            except Exception as ex:st.error(str(ex))


elif page=='Logs':
    st.title('Logs do Sistema')
    st.caption('Registro de operações importantes com data/hora, usuário, dispositivo, módulo e ação.')
    c=db();d=pd.read_sql_query("select log_date Data,user_name Usuário,device Dispositivo,module Módulo,action Ação,details Detalhes from app_logs order by id desc",c);c.close()
    st.dataframe(d,use_container_width=True,height=600)
    if not d.empty:
        buf=io.BytesIO();d.to_excel(buf,index=False);st.download_button('Exportar logs',buf.getvalue(),'LOGS_SISTEMA.xlsx')

elif page=='Configurações':
    st.subheader('Precisão dos lançamentos')
    _dec=decimal_places()
    _new_dec=st.selectbox('Casas decimais dos lançamentos',[0,1,2,3],index=_dec,
        help='Quantidade, fatores, conversões, custos e valores digitados serão gravados com no máximo esta quantidade de casas decimais.')
    if st.button('SALVAR CASAS DECIMAIS',key='save_decimal_places'):
        c=db()
        c.execute("""insert into settings(key,value) values('decimal_places',?)
                     on conflict(key) do update set value=excluded.value""",(str(int(_new_dec)),))
        c.commit();c.close()
        set_flash(f'Precisão configurada para {_new_dec} casa(s) decimal(is).','success')
        st.rerun()

    st.subheader('Associações históricas')
    st.caption('Aproveita as associações que você já fez em notas antigas sem alterar os lançamentos históricos.')
    if st.button('APROVEITAR ASSOCIAÇÕES JÁ GRAVADAS',key='backfill_mappings_v105'):
        try:
            _bf=backfill_invoice_mappings_from_history()
            set_flash(f"Regras revisadas: {_bf['scanned']} fornecedor/SKU | {_bf['created']} novas | {_bf['updated']} preservadas/completadas.",'success')
            st.rerun()
        except Exception as ex:
            st.error(f'Não foi possível aproveitar o histórico: {ex}')

    st.subheader('AUTODIAGNÓSTICO V10')
    if st.button('EXECUTAR AUTODIAGNÓSTICO',type='primary',key='v10_health'):
        _health=system_health()
        st.dataframe(_health,use_container_width=True,hide_index=True)
        if (_health['Status']=='ERRO').any():
            st.error('Há erro estrutural que precisa ser corrigido antes de continuar.')
        elif (_health['Status']=='ATENÇÃO').any():
            st.warning('Há divergências operacionais para revisar.')
        else:
            confirm_success('Estrutura principal validada.')

    st.title('Configurações')
    st.info('Modo LOCAL: todos os dados são gravados no arquivo hnt_foodservice_v3.db dentro desta pasta. Faça backups periódicos em Configurações.')
    st.subheader('INTEGRIDADE DE ENTIDADES / RELACIONAMENTOS')
    _rel=entity_integrity_report()
    st.dataframe(_rel,use_container_width=True,hide_index=True)
    if st.button('RECONSTRUIR CUSTOS AUSENTES',key='rebuild_cost_master_v101'):
        _n=rebuild_missing_cost_master()
        confirm_success(f'{_n} custo(s) mestre reconstruído(s) a partir das entradas de estoque.')
        st.rerun()


    st.subheader('Configurações locais de IA e SEFAZ')
    st.code('GEMINI_API_KEY = "sua_chave_gratuita"\nSEFAZ_PFX_PASSWORD = "senha_do_pfx"\nSEFAZ_PFX_BASE64 = "conteudo_base64_do_pfx"',language='toml')
    st.title('Configurações / Aparelho / SEFAZ / Backup')
    c=db();cfg={r['key']:r['value'] for r in c.execute('select * from settings').fetchall()};c.close()
    t1,t2,t3=st.tabs(['Empresa / SEFAZ','Aparelho / Usuário','Backup'])
    with t1:
        st.info('Não existe Token/API Key do SEFAZ para este fluxo. A autenticação é feita pelo certificado A1 PFX/P12 + senha.')
        cnpj=st.text_input('CNPJ',cfg.get('cnpj',''))
        uf=st.text_input('Código UF IBGE',cfg.get('uf','33'))
        amb=st.selectbox('Ambiente',['Produção','Homologação'],index=1 if cfg.get('ambiente')=='Homologação' else 0)
        pfx=st.file_uploader('Certificado A1 PFX/P12',type=['pfx','p12'])
        test_pw=st.text_input('Senha do PFX para testar agora',type='password',key='cfg_sefaz_test_pw_v113')
        b1,b2=st.columns(2)
        if b1.button('SALVAR CONFIGURAÇÃO SEFAZ',type='primary'):
            c=db()
            for k,v in [('cnpj',cnpj),('uf',uf),('ambiente',amb)]:
                c.execute('insert into settings(key,value) values(?,?) on conflict(key) do update set value=excluded.value',(k,v))
            if pfx:
                path=CERT_DIR/'certificado.pfx'
                path.write_bytes(pfx.getvalue())
                c.execute("insert into settings(key,value) values('pfx_path',?) on conflict(key) do update set value=excluded.value",(str(path),))
            c.commit();c.close();app_log('Configurações','SEFAZ atualizado');confirm_success('Configuração SEFAZ salva.')
        if b2.button('TESTAR CERTIFICADO A1'):
            try:
                saved_pfx=resolve_sefaz_pfx()
                pwd=test_pw or resolve_sefaz_password()
                if not pwd:raise ValueError('Informe a senha do PFX para o teste.')
                info=pfx_certificate_info(saved_pfx,pwd)
                if not info['has_private_key']:raise ValueError('Certificado sem chave privada.')
                if info['days'] is not None and info['days']<0:
                    st.error(f"Certificado expirado em {info['expires']}.")
                else:
                    st.success(f"Certificado válido. Expira em {info['expires']} | dias restantes: {info['days']}")
                    st.caption('Titular: '+info['subject'])
            except Exception as ex:st.error(str(ex))
        st.caption('Para sincronização automática sem digitar a senha em cada abertura, configure a variável de ambiente SEFAZ_PFX_PASSWORD no Windows. O sistema também aceita st.secrets.')
    with t2:
        nome=st.text_input('Nome do usuário / operador',cfg.get('nome_usuario','Operador'))
        devices=['Computador','Notebook','Tablet','Celular','Terminal de Estoque'];current=cfg.get('tipo_dispositivo','Computador');idx=devices.index(current) if current in devices else 0
        device=st.selectbox('Aparelho',devices,index=idx);mode=st.selectbox('Modo da interface',['Automático','Compacto','Desktop'])
        if st.button('Salvar configuração do aparelho'):
            c=db()
            for k,v in [('nome_usuario',nome),('tipo_dispositivo',device),('modo_interface',mode)]:c.execute('insert into settings(key,value) values(?,?) on conflict(key) do update set value=excluded.value',(k,v))
            c.commit();c.close();app_log('Configurações','Aparelho atualizado',device);confirm_success('Aparelho configurado.')
        st.info('A interface Streamlit é responsiva. Para celular/tablet na mesma rede, use INICIAR_REDE.bat e abra o IP do servidor na porta 8501.')
    with t3:
        st.subheader('Exportar backup')
        if DB.exists():st.download_button('Baixar banco completo',DB.read_bytes(),f"BACKUP_HNT_{datetime.now().strftime('%Y%m%d_%H%M')}.db")
        st.subheader('Importar / restaurar backup')
        st.warning('A restauração substitui o banco atual. O sistema cria uma cópia automática antes da troca.')
        bkp=st.file_uploader('Arquivo de backup .db',type=['db'],key='dbrestore')
        if bkp and st.button('RESTAURAR BANCO',type='primary'):
            before=ROOT/f"BACKUP_ANTES_RESTAURAR_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
            if DB.exists():before.write_bytes(DB.read_bytes())
            DB.write_bytes(bkp.read());confirm_success('Banco restaurado. Reinicie o sistema.');
    confirm_success('Sem licença, sem chave de ativação e sem prazo de validade.')
    st.info('Para acesso externo pela internet, use a implantação cloud/Supabase descrita em ACESSO_MULTIPLATAFORMA.md.')

