export interface PreviewQuestion {
  stem: string;
  options?: { label: string; content: string; is_correct?: boolean }[];
  answer: string;
  analysis: string;
  question_type: string;
  confidence: number;
  suggested_node_ids?: string[];
  ai_corrected?: boolean;
  source_line?: number;
}