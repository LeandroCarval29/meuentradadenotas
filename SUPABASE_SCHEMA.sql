-- HNT FoodService BI - estrutura base para PostgreSQL/Supabase
-- Execute em um projeto de TESTE antes de produção.
create table if not exists products(
 id bigserial primary key, code bigint unique not null, internal_barcode text unique,
 name text not null, brand text default '', category text, subcategory text, unit text,
 active boolean default true, notes text default ''
);
create table if not exists product_barcodes(id bigserial primary key,product_id bigint references products(id),barcode text unique,description text);
create table if not exists suppliers(id bigserial primary key,cnpj text unique,legal_name text,trade_name text,ie text,address text,phone text,email text,active boolean default true);
create table if not exists invoices(id bigserial primary key,access_key text unique,number text,series text,issue_date date,entry_date timestamptz,supplier_id bigint references suppliers(id),total numeric(14,2),status text default 'PENDENTE',notes text,source text default 'XML');
create table if not exists invoice_items(id bigserial primary key,invoice_id bigint references invoices(id),supplier_code text,barcode text,description text,ncm text,cfop text,xml_unit text,xml_qty numeric(18,6),xml_unit_value numeric(18,8),xml_total numeric(14,2),product_id bigint references products(id),multiplier numeric(18,8) default 1,conversion numeric(18,8) default 1,converted_qty numeric(18,6),converted_unit_cost numeric(18,8));
create table if not exists mappings(id bigserial primary key,supplier_id bigint references suppliers(id),supplier_code text,supplier_barcode text,supplier_description text,product_id bigint references products(id),multiplier numeric(18,8),conversion numeric(18,8),unique(supplier_id,supplier_code));
create table if not exists movements(id bigserial primary key,product_id bigint references products(id),movement_date timestamptz,type text,qty numeric(18,6),unit_cost numeric(18,8),reference text,notes text);
create table if not exists losses(id bigserial primary key,product_id bigint references products(id),loss_date date,qty numeric(18,6),unit_cost numeric(18,8),cause text,notes text);
create table if not exists inventory(id bigserial primary key,inventory_date date,product_id bigint references products(id),counted_qty numeric(18,6),avg_cost_3m numeric(18,8),total_value numeric(14,2),notes text);
create table if not exists sales(id bigserial primary key,sale_date date,store text default 'GERAL',net_sales numeric(14,2),gross_sales numeric(14,2),service numeric(14,2),delivery numeric(14,2),notes text,unique(sale_date,store));
create table if not exists purchase_schedule(id bigserial primary key,product_id bigint references products(id),order_day text,supply_group text,frequency text,target_stock numeric(18,6),min_stock numeric(18,6),active boolean default true,notes text,unique(product_id,order_day,supply_group));
create table if not exists counts(id bigserial primary key,count_date date,product_id bigint references products(id),order_day text,supply_group text,counted_qty numeric(18,6),target_stock numeric(18,6),suggested_qty numeric(18,6),notes text);
create table if not exists quotes(id bigserial primary key,quote_id text,quote_date date,product_id bigint references products(id),supplier_id bigint references suppliers(id),qty numeric(18,6),purchase_unit text,conversion numeric(18,8),offer_price numeric(14,2),freight numeric(14,2),discount numeric(14,2),unit_cost numeric(18,8),lead_days integer,valid_until date,notes text);
create table if not exists dfe_docs(id bigserial primary key,nsu text unique,schema text,access_key text,issuer_cnpj text,issuer_name text,issue_date date,total numeric(14,2),status text,xml_path text,received_at timestamptz);
create table if not exists settings(key text primary key,value text);
create table if not exists cost_master(id bigserial primary key,product_id bigint unique references products(id),current_cost numeric(18,8),updated_at timestamptz,notes text);
create table if not exists stock_policy(id bigserial primary key,product_id bigint unique references products(id),lead_days numeric(8,2) default 7,review_days numeric(8,2) default 7,service_factor numeric(8,4) default 1.65,notes text);
