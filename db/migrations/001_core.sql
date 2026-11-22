-- InvestWatch core schema (docs/backend-integration.md §5a, D4: Postgres = record envelope + text, MinIO = binaries).
-- Applied in order by db/load.py (compose service `loader`) on every start. Idempotent.

-- One row per loader stage run (db/load.py --stage init|score); finished_at null = still running.
create table if not exists load_runs (
  id bigserial primary key,
  started_at timestamptz not null,
  finished_at timestamptz,
  model_version text,
  stats jsonb
);
alter table load_runs add column if not exists stage text;
alter table load_runs add column if not exists total int;
alter table load_runs add column if not exists done int;

-- Collector record envelope (D2/D12): one row per source_url.
create table if not exists items (
  id text primary key,
  url text not null unique,
  source text,
  origin text,
  platform text,
  channel text,
  author text,
  sponsor text,
  title text,
  text jsonb not null,
  links text[],
  media jsonb,
  source_meta jsonb,
  query_keywords text[],
  published_at timestamptz,
  fetched_at timestamptz,
  analyzed_at timestamptz,     -- sent to ai-service (also when out of scope and without a finding)
  created_at timestamptz not null default now()
);
create index if not exists items_fetched_at on items (fetched_at);

-- ai-service AnalysisResult mapped to the frontend Finding (result = full Finding without status overlay).
create table if not exists findings (
  id text primary key,
  item_id text not null references items (id) on delete cascade,
  model_version text,
  analyzed_at timestamptz,
  result jsonb not null,
  scoring_input jsonb,
  modules int[],
  risk_score real,
  risk_level text,
  status text not null default 'NEW',
  updated_at timestamptz not null default now()
);
create index if not exists findings_item_id on findings (item_id);
create index if not exists findings_risk_level on findings (risk_level);
create index if not exists findings_status on findings (status);
create index if not exists findings_modules on findings using gin (modules);

-- Analyst decisions only; the import/model entries stay in findings.result.history.
create table if not exists finding_history (
  id bigserial primary key,
  finding_id text not null references findings (id) on delete cascade,
  at timestamptz not null,
  status text not null,
  "user" text not null,
  comment text
);
create index if not exists finding_history_finding on finding_history (finding_id);

create table if not exists thresholds (
  id serial primary key,
  version text not null,
  values jsonb not null,
  updated_at timestamptz not null,
  active boolean not null default false
);

-- KNF registry (ml/src/investwatch_ml/knf_register.json or data/knf_entities.json).
create table if not exists knf_entities (
  name text primary key,
  aliases text[],
  category text,
  country text,
  supervisor text,
  registered_at text,
  address text,
  source_url text
);

-- PoC brand groups (db/linking.py GROUPS). KPIs are computed by the API from findings and monitor data.
create table if not exists entities (
  id text primary key,
  name text not null,
  registry_names text[] not null,
  domains text[],
  social_handles jsonb
);

create table if not exists item_entities (
  item_id text not null references items (id) on delete cascade,
  entity_id text not null references entities (id) on delete cascade,
  author_is_entity boolean not null default false,
  primary key (item_id, entity_id)
);

-- Website monitor (monitor/ -> data/monitor/*).
create table if not exists monitored_pages (
  page_id text primary key,
  entity_id text references entities (id) on delete cascade,
  url text not null,
  label text
);

create table if not exists page_snapshots (
  id text primary key,
  page_id text not null references monitored_pages (page_id) on delete cascade,
  entity_id text,
  url text,
  fetched_at timestamptz,
  text_sha256 text,
  text text,
  risk_warning jsonb,
  screenshots jsonb,           -- {viewport: MinIO key in bucket "screens"}
  legibility jsonb,
  legibility_check jsonb,
  mock boolean not null default false
);
create index if not exists page_snapshots_page on page_snapshots (page_id, fetched_at desc);

create table if not exists page_changes (
  id text primary key,
  page_id text not null references monitored_pages (page_id) on delete cascade,
  entity_id text,
  from_snapshot text,
  to_snapshot text,
  detected_at timestamptz,
  summary text,
  added_lines jsonb,
  removed_lines jsonb,
  style_changes jsonb,
  assessment jsonb,
  mock boolean not null default false
);

-- Objects in MinIO referenced by items.media[].key and page_snapshots.screenshots.
create table if not exists media_objects (
  bucket text not null,
  key text not null,
  content_type text,
  size bigint,
  meta jsonb,
  primary key (bucket, key)
);
