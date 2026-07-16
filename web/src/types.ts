export type Perspective = 'product' | 'technical'

export interface Question {
  id: string
  text_local: string
  text_zh: string
  tier: string
  funnel: string
  value_score: number
  query_scope: string
}

export interface Citation {
  url: string
  domain: string
  source_type: string
}

export interface Answer {
  question_id: string
  provider: string
  model: string
  raw_text: string
  is_mock: boolean
  search_grounded: boolean
  source_urls: string[]
}

export interface Analysis {
  question_id: string
  brand_mentioned: boolean
  brand_recommended: boolean
  brand_position: number | null
  sentiment: string
  citations: Citation[]
}

export interface SegmentMetrics {
  visibility_rate: number
  recommendation_rate: number | null
  sov: number
  avg_position: number | null
  citation_rate: number
  questions_checked: number
  source_type_summary: Record<string, number>
}

export interface Report {
  meta: {
    run_id: string
    model: string
    mode: string
    generated_at: string
    web_search_enabled: boolean
    providers: string[]
  }
  brand_profile: {
    brand_name: string
    category: string
    market: string
    language: string
    website_url: string
  }
  questions: Question[]
  answers: Answer[]
  analyses: Analysis[]
  metrics: {
    branded: SegmentMetrics
    unbranded: SegmentMetrics
    competitor_ranking: Array<{ name: string; mention_count: number; sov: number }>
    source_type_summary: Record<string, number>
  }
  fanout_queries: Array<{
    id: string
    parent_question_id: string
    text_local: string
    text_zh: string
    fanout_type: string
    is_mock: boolean
  }>
  fanout_answers: Answer[]
  fanout_metrics: {
    parents_selected: number
    queries_generated: number
    queries_checked: number
    mention_coverage: number
    recommendation_coverage: number
    parent_fanout_coverage: number
    grounded_rate: number
  }
  site_audit: {
    pages_checked: number
    snapshot_mode: boolean
    has_es_mx_hreflang: boolean
    spanish_content_found: boolean
    llms_txt_found: boolean
    likely_js_dependent: boolean
    raw_html_text_chars: number
    issues: Array<{ code: string; severity: string; detail: string }>
  }
  gaps: Array<{ gap_type: string; severity: string; title: string; evidence: string[] }>
  recommendations: Array<{
    priority: string
    action: string
    reason: string
    expected_impact: string
    effort: string
  }>
}

export interface LiveEvent {
  type: 'started' | 'question' | 'result' | 'completed' | 'error'
  message?: string
  question?: Question
  answer?: Answer
  analysis?: Analysis
  metrics?: unknown
  completed?: number
  total?: number
}
