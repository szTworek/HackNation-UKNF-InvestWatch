export type Module = 'M1' | 'M2' | 'M3'
export type Severity = 'low' | 'medium' | 'high'
export type Channel = 'ad' | 'social' | 'website'
export type Platform = 'google_ads' | 'meta_ads' | 'bing_ads' | 'youtube' | 'tiktok' | 'website'

export interface RegistryEntry { name: string; category: string; country: string }

export interface Entity {
  id: string
  name: string
  registry_entries: RegistryEntry[]
  domains: string[]
  monitored_pages: number
  social_handles: Record<string, string>
  kpis: { items: number; findings_open: number; alerts_new: number; risk_score: number; pages_changed_7d: number }
}

export interface EntityDetail extends Entity {
  modules: Record<Module, { findings: number; avg_score: number }>
  platforms: Record<string, number>
}

export interface RuleHit { rule_id: string; label: string; evidence: string; section: string; span: [number, number] | null }

export interface Finding {
  id: string
  item_id: string
  entity_id: string
  module: Module
  score: number
  severity: Severity
  rule_hits: RuleHit[]
  model: string
  created_at: string
}

export interface Item {
  id: string
  entity_ids: string[]
  channel: Channel
  platform: Platform
  source_url: string
  author: string
  author_is_entity: boolean
  published_at: string | null
  fetched_at: string
  text: Record<string, string>
  mock: boolean
}

export interface ItemWithFindings extends Item { findings: Finding[] }

export interface RiskWarning { present: boolean; cfd_loss_pct: number | null; text: string | null; above_fold: boolean }

export interface PageSnapshot {
  id: string
  page_id: string
  entity_id: string
  url: string
  fetched_at: string
  text_sha256: string
  text: string
  risk_warning: RiskWarning
  mock: boolean
}

export type ChangeKind = 'text' | 'risk_warning_changed' | 'risk_warning_removed' | 'page_removed'

export interface PageChange {
  id: string
  page_id: string
  entity_id: string
  from_snapshot: string
  to_snapshot: string
  detected_at: string
  kinds: ChangeKind[]
  summary: string
  added_lines: string[]
  removed_lines: string[]
  mock: boolean
}

export interface PageChangeDetail extends PageChange { from: PageSnapshot; to: PageSnapshot }

export interface MonitoredPage { page_id: string; url: string; label: string; last_snapshot: PageSnapshot | null; changes: PageChange[] }

export interface Alert {
  id: string
  created_at: string
  entity_id: string
  kind: 'finding' | 'page_change'
  severity: Severity
  title: string
  ref: { finding_id: string | null; change_id: string | null }
  status: 'new' | 'ack' | 'closed'
}

export interface Overview {
  totals: { entities: number; items: number; findings: number; alerts_new: number; pages: number; page_changes_30d: number }
  findings_by_day: ({ date: string } & Record<Module, number>)[]
  items_by_platform: Record<string, number>
  heatmap: ({ entity_id: string } & Record<Module, number>)[]
  top_rules: { rule_id: string; label: string; count: number }[]
}

export interface ItemsPage { total: number; items: ItemWithFindings[] }
export interface ScanResult { items_new: number; findings_new: number; alerts_new: number }
