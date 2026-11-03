export interface AnswerReference {
  number: number;
  chunk_id: string;
  document_name: string;
  source_type: string;
  text: string;
  page: number | null;
  chunk_index: number | null;
  sheet: string | null;
  row: number | null;
}
