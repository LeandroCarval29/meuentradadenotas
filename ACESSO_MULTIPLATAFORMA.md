# Acesso multiplataforma

## Opção 1 — pronta agora: rede local

Use `INICIAR_REDE.bat` no computador que ficará como servidor.

O sistema escuta em `0.0.0.0:8501`. Outros computadores, tablets e celulares na mesma rede podem abrir:

`http://IP_DO_SERVIDOR:8501`

Todos usam o mesmo banco SQLite salvo no computador servidor. Isso significa que os dados permanecem gravados entre reinicializações, desde que a pasta do sistema não seja apagada.

Recomendações:
- deixe o computador servidor ligado;
- faça backup diário do arquivo `hnt_foodservice_v3.db`;
- não coloque a pasta em OneDrive/Google Drive enquanto o banco estiver aberto;
- configure o Firewall do Windows para permitir Python/porta 8501 apenas na rede privada.

## Opção 2 — acesso pela internet: PostgreSQL/Supabase

Para uso fora da loja/rede local, a arquitetura recomendada é migrar o SQLite para PostgreSQL e hospedar o aplicativo em um servidor Python/Streamlit.

O Supabase oferece Postgres e disponibiliza a connection string no painel **Connect**. Para backend persistente em rede IPv4, a documentação recomenda o pooler em modo de sessão; para servidor com IPv6, uma conexão direta também é possível.

Arquivo incluído: `SUPABASE_SCHEMA.sql`.

### O que ainda precisa ser feito para o modo Supabase

1. Criar um projeto no Supabase.
2. Executar `SUPABASE_SCHEMA.sql` no SQL Editor.
3. Migrar os dados do SQLite atual para Postgres.
4. Alterar o adaptador de banco do aplicativo para PostgreSQL.
5. Hospedar o aplicativo Python em um servidor acessível pela internet.
6. Configurar autenticação, perfis de usuário, backup e Row Level Security antes de colocar em produção.

A V4.1 entregue continua funcionando integralmente em SQLite e rede local; o schema cloud está incluído para não recomeçar a modelagem quando a migração for feita.

Referência oficial: https://supabase.com/docs/guides/database/connecting-to-postgres
