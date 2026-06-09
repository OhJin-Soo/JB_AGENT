import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import {
  BarChart3,
  Bot,
  FileDown,
  Download,
  History,
  Loader2,
  Plus,
  Send,
  Sparkles,
  Trash2,
  Upload,
  Wallet,
} from "lucide-react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import "./styles.css";
import { FormEvent, useEffect, useMemo, useRef, useState } from "react";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8001";

type CashflowType = "income" | "expense";

type CashflowDraft = {
  date: string;
  amount: string;
  type: CashflowType;
  category: string;
  description: string;
};

type AssetDraft = {
  type: "cash" | "pension" | "real_estate" | "other";
  name: string;
  current_value: string;
};

type CsvUploadResult = {
  title: string;
  cashflows: CashflowDraft[];
  assets: AssetDraft[];
};

type ForecastPoint = {
  month: string;
  income: number;
  expense: number;
  net_cashflow: number;
  cumulative_cashflow: number;
  net_worth: number;
};

type AnalysisResponse = {
  id: number | null;
  title: string;
  created_at: string;
  result: {
    forecast: ForecastPoint[];
    summary: string;
    data_quality: Record<string, string | number>;
  };
};

type ChatMessage = {
  role: "user" | "assistant";
  content: string;
  evidence?: string[];
  confidence?: string;
  suggestedActions?: string[];
  suggestionStatus?: string;
  suggestionReason?: string | null;
  toolPlanStatus?: string;
  toolPlanReason?: string | null;
  toolCalls?: string[];
};

function App() {
  const [title, setTitle] = useState("현금흐름 분석");
  const [forecastMonths, setForecastMonths] = useState(6);
  const [cashflows, setCashflows] = useState<CashflowDraft[]>([]);
  const [assets, setAssets] = useState<AssetDraft[]>([]);
  const [analysis, setAnalysis] = useState<AnalysisResponse | null>(null);
  const [history, setHistory] = useState<AnalysisResponse[]>([]);
  const [activeTab, setActiveTab] = useState<"analysis" | "history">("analysis");
  const [chatOpen, setChatOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [question, setQuestion] = useState("");
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [chatLoading, setChatLoading] = useState(false);
  const [suggestedQuestions, setSuggestedQuestions] = useState<string[]>([]);
  const csvInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    void loadHistory();
  }, []);

  const latest = analysis?.result.forecast.at(-1);
  const totalNet = latest?.cumulative_cashflow ?? 0;
  const chartData = useMemo(() => analysis?.result.forecast ?? [], [analysis]);

  async function loadHistory() {
    const response = await fetch(`${API_BASE_URL}/history`);
    if (response.ok) {
      setHistory(await response.json());
    }
  }

  async function submitAnalysis(event: FormEvent) {
    event.preventDefault();
    if (cashflows.length === 0) {
      setError("CSV를 업로드하거나 현금흐름을 직접 추가하세요.");
      return;
    }
    setLoading(true);
    setError("");
    try {
      const payload = {
        title,
        forecast_months: forecastMonths,
        save: true,
        cashflows: cashflows.map((item) => ({
          date: item.date,
          amount: Number(item.amount),
          type: item.type,
          category: item.category,
          description: item.description || null,
        })),
        assets: assets
          .filter((asset) => asset.name && Number(asset.current_value) >= 0)
          .map((asset) => ({
            type: asset.type,
            name: asset.name,
            current_value: Number(asset.current_value),
          })),
      };
      const response = await fetch(`${API_BASE_URL}/analyses`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail?.[0]?.msg ?? data.detail ?? "분석 생성에 실패했습니다.");
      }
      const data = await response.json();
      setAnalysis(data);
      setChatMessages([]);
      setSuggestedQuestions([]);
      setActiveTab("analysis");
      await loadHistory();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "알 수 없는 오류가 발생했습니다.");
    } finally {
      setLoading(false);
    }
  }

  async function sendQuestion(event: FormEvent) {
    event.preventDefault();
    if (!question.trim()) return;
    await sendChatMessage(question.trim());
  }

  async function sendChatMessage(nextQuestion: string) {
    setQuestion("");
    setSuggestedQuestions([]);
    const conversation = chatMessages.map((message) => ({
      role: message.role,
      content: message.content,
    }));
    setChatMessages((messages) => [...messages, { role: "user", content: nextQuestion }]);
    setChatLoading(true);
    try {
      const response = await fetch(`${API_BASE_URL}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: nextQuestion, analysis_id: analysis?.id ?? null, conversation }),
      });
      const data = await response.json();
      setSuggestedQuestions((data.suggested_questions ?? []).slice(0, 3));
      setChatMessages((messages) => [
        ...messages,
        {
          role: "assistant",
          content: data.answer,
          evidence: data.evidence ?? [],
          confidence: data.confidence,
          suggestedActions: data.suggested_actions ?? [],
          suggestionStatus: data.suggestion_status,
          suggestionReason: data.suggestion_reason,
          toolPlanStatus: data.tool_plan_status,
          toolPlanReason: data.tool_plan_reason,
          toolCalls: data.tool_calls ?? [],
        },
      ]);
    } finally {
      setChatLoading(false);
    }
  }

  function updateCashflow(index: number, patch: Partial<CashflowDraft>) {
    setCashflows((items) => items.map((item, itemIndex) => (itemIndex === index ? { ...item, ...patch } : item)));
  }

  function updateAsset(index: number, patch: Partial<AssetDraft>) {
    setAssets((items) => items.map((item, itemIndex) => (itemIndex === index ? { ...item, ...patch } : item)));
  }

  async function handleCsvUpload(file: File) {
    const parsed = await parseCsvUpload(file);
    setCashflows(parsed.cashflows);
    if (parsed.assets.length > 0) {
      setAssets(parsed.assets);
    }
    if (!title.trim() || title === "현금흐름 분석") {
      setTitle(parsed.title);
    }
    setError("");
  }

  const visibleSuggestedQuestions =
    chatMessages.length === 0 ? buildInitialSuggestedQuestions(analysis) : suggestedQuestions;

  return (
    <main className="app-shell">
      <section className="workspace">
        <aside className="input-panel">
          <div className="brand">
            <Wallet size={28} />
            <div>
              <h1>JB Agent</h1>
              <p>개인 현금흐름 예측</p>
            </div>
          </div>

          <form onSubmit={submitAnalysis} className="form-stack">
            <label className="field">
              <span>분석명</span>
              <input value={title} onChange={(event) => setTitle(event.target.value)} />
            </label>

            <label className="field">
              <span>예측 기간</span>
              <input
                type="number"
                min={1}
                max={120}
                value={forecastMonths}
                onChange={(event) => setForecastMonths(Number(event.target.value))}
              />
            </label>

            <div className="csv-upload-panel">
              <div className="section-title">
                <span>CSV 업로드</span>
                <a className="sample-link" href="/sample_cashflow_upload.csv" download>
                  <FileDown size={15} />
                  샘플 CSV
                </a>
              </div>
              <p className="upload-hint">현금흐름과 자산을 CSV로 불러와 입력 테이블을 채울 수 있습니다.</p>
              <input
                ref={csvInputRef}
                type="file"
                accept=".csv,text/csv"
                onChange={async (event) => {
                  const file = event.target.files?.[0];
                  if (!file) return;
                  try {
                    await handleCsvUpload(file);
                  } catch (caught) {
                    setError(caught instanceof Error ? caught.message : "CSV를 읽을 수 없습니다.");
                  } finally {
                    event.target.value = "";
                  }
                }}
                hidden
              />
              <button
                type="button"
                className="secondary-button"
                onClick={() => csvInputRef.current?.click()}
              >
                <Upload size={16} />
                CSV 불러오기
              </button>
            </div>

            <div className="section-title">
              <span>현금흐름</span>
              <button
                type="button"
                className="icon-button"
                title="현금흐름 추가"
                onClick={() =>
                  setCashflows((items) => [
                    ...items,
                    { date: "2026-04-01", amount: "0", type: "expense", category: "", description: "" },
                  ])
                }
              >
                <Plus size={16} />
              </button>
            </div>

            <div className="rows">
              {cashflows.map((item, index) => (
                <div className="cashflow-row" key={`${item.date}-${index}`}>
                  <input type="date" value={item.date} onChange={(event) => updateCashflow(index, { date: event.target.value })} />
                  <select value={item.type} onChange={(event) => updateCashflow(index, { type: event.target.value as CashflowType })}>
                    <option value="income">수입</option>
                    <option value="expense">지출</option>
                  </select>
                  <input value={item.category} placeholder="카테고리" onChange={(event) => updateCashflow(index, { category: event.target.value })} />
                  <input type="number" value={item.amount} onChange={(event) => updateCashflow(index, { amount: event.target.value })} />
                  <button
                    type="button"
                    className="icon-button danger"
                    title="삭제"
                    onClick={() => setCashflows((items) => items.filter((_, itemIndex) => itemIndex !== index))}
                  >
                    <Trash2 size={15} />
                  </button>
                </div>
              ))}
            </div>

            <div className="section-title">
              <span>자산</span>
              <button
                type="button"
                className="icon-button"
                title="자산 추가"
                onClick={() => setAssets((items) => [...items, { type: "cash", name: "", current_value: "0" }])}
              >
                <Plus size={16} />
              </button>
            </div>

            <div className="rows">
              {assets.map((asset, index) => (
                <div className="asset-row" key={`${asset.name}-${index}`}>
                  <select value={asset.type} onChange={(event) => updateAsset(index, { type: event.target.value as AssetDraft["type"] })}>
                    <option value="cash">현금</option>
                    <option value="pension">연금</option>
                    <option value="real_estate">부동산</option>
                    <option value="other">기타</option>
                  </select>
                  <input value={asset.name} placeholder="자산명" onChange={(event) => updateAsset(index, { name: event.target.value })} />
                  <input type="number" value={asset.current_value} onChange={(event) => updateAsset(index, { current_value: event.target.value })} />
                </div>
              ))}
            </div>

            {error && <p className="error-text">{error}</p>}

            <button className="primary-button" disabled={loading}>
              {loading ? <Loader2 className="spin" size={18} /> : <Sparkles size={18} />}
              분석 실행
            </button>
          </form>
        </aside>

        <section className="result-panel">
          <nav className="tabs">
            <button className={activeTab === "analysis" ? "active" : ""} onClick={() => setActiveTab("analysis")}>
              <BarChart3 size={17} /> 분석
            </button>
            <button className={activeTab === "history" ? "active" : ""} onClick={() => setActiveTab("history")}>
              <History size={17} /> 히스토리
            </button>
          </nav>

          {activeTab === "analysis" && (
            <section className={`content-area analysis-workspace ${chatOpen ? "chat-visible" : ""}`}>
              {analysis ? (
                <>
                  <div className="dashboard-column">
                    <div className="summary-grid">
                      <Metric label="예상 누적 현금흐름" value={formatCurrency(totalNet)} />
                      <Metric label="예측 순자산" value={formatCurrency(latest?.net_worth ?? 0)} />
                      <Metric label="예측 개월" value={`${analysis.result.data_quality.forecast_months}개월`} />
                    </div>

                    <div className="summary-band">
                      <p>{analysis.result.summary}</p>
                      <div className="summary-actions">
                        <button
                          type="button"
                          className={`toggle-chat-button ${chatOpen ? "active" : ""}`}
                          onClick={() => setChatOpen((isOpen) => !isOpen)}
                        >
                          <Bot size={16} /> 채팅
                        </button>
                        {analysis.id && (
                          <a className="download-link" href={`${API_BASE_URL}/reports/analyses/${analysis.id}.pdf`}>
                            <Download size={16} /> PDF
                          </a>
                        )}
                      </div>
                    </div>

                    <div className={`dashboard-main ${chatOpen ? "chat-visible" : ""}`}>
                      <div className="charts-column">
                        <div className="chart-block">
                          <h2>월별 수입/지출</h2>
                          <ResponsiveContainer width="100%" height={280}>
                            <AreaChart data={chartData}>
                              <CartesianGrid strokeDasharray="3 3" />
                              <XAxis dataKey="month" />
                              <YAxis tickFormatter={(value) => `${Number(value) / 10000}만`} />
                              <Tooltip formatter={(value) => formatCurrency(Number(value))} />
                              <Legend />
                              <Area type="monotone" dataKey="income" name="수입" stroke="#2563eb" fill="#bfdbfe" />
                              <Area type="monotone" dataKey="expense" name="지출" stroke="#dc2626" fill="#fecaca" />
                            </AreaChart>
                          </ResponsiveContainer>
                        </div>

                        <div className="chart-block">
                          <h2>순자산 추이</h2>
                          <ResponsiveContainer width="100%" height={260}>
                            <LineChart data={chartData}>
                              <CartesianGrid strokeDasharray="3 3" />
                              <XAxis dataKey="month" />
                              <YAxis tickFormatter={(value) => `${Number(value) / 10000}만`} />
                              <Tooltip formatter={(value) => formatCurrency(Number(value))} />
                              <Line type="monotone" dataKey="net_worth" name="순자산" stroke="#0f766e" strokeWidth={3} dot={false} />
                            </LineChart>
                          </ResponsiveContainer>
                        </div>
                      </div>

                      {chatOpen && (
                        <aside className="side-chat">
                          <div className="inline-chat-header">
                            <div>
                              <h2>분석 질문</h2>
                              <p>현재 분석 결과를 기준으로 답변합니다.</p>
                            </div>
                            <button type="button" className="ghost-button" onClick={() => setChatOpen(false)}>
                              닫기
                            </button>
                          </div>
                          <div className="messages inline">
                            {chatMessages.length === 0 && (
                              <EmptyState title="질문 없음" description="예: 6개월 뒤 순자산은 어떻게 돼?" />
                            )}
                            {chatMessages.map((message, index) => (
                              <div className={`message ${message.role}`} key={`${message.role}-${index}`}>
                                <p>{message.content}</p>
                                {message.confidence && (
                                  <span className={`confidence ${message.confidence}`}>신뢰도 {message.confidence}</span>
                                )}
                                {message.evidence && message.evidence.length > 0 && (
                                  <ul className="message-list">
                                    {message.evidence.slice(0, 4).map((item) => (
                                      <li key={item}>{item}</li>
                                    ))}
                                  </ul>
                                )}
                                {message.suggestedActions && message.suggestedActions.length > 0 && (
                                  <div className="suggested-actions">
                                    {message.suggestedActions.slice(0, 2).map((item) => (
                                      <span key={item}>{item}</span>
                                    ))}
                                  </div>
                                )}
                                {(message.suggestionStatus || message.toolPlanStatus) && (
                                  <div className="debug-details">
                                    {message.suggestionStatus && (
                                      <span title={message.suggestionReason ?? undefined}>
                                        추천 {formatDebugStatus(message.suggestionStatus)}
                                        {message.suggestionReason ? `: ${message.suggestionReason}` : ""}
                                      </span>
                                    )}
                                    {message.toolPlanStatus && (
                                      <span title={message.toolPlanReason ?? undefined}>
                                        tool {formatDebugStatus(message.toolPlanStatus)}
                                        {message.toolCalls && message.toolCalls.length > 0
                                          ? `: ${message.toolCalls.map(formatToolCallLabel).join(", ")}`
                                          : ""}
                                        {message.toolPlanReason ? ` (${message.toolPlanReason})` : ""}
                                      </span>
                                    )}
                                  </div>
                                )}
                              </div>
                            ))}
                            {chatLoading && <div className="message assistant">답변 생성 중...</div>}
                          </div>
                          {visibleSuggestedQuestions.length > 0 && (
                            <div className="question-suggestions">
                              {visibleSuggestedQuestions.slice(0, 3).map((item) => (
                                <button
                                  type="button"
                                  key={item}
                                  disabled={chatLoading}
                                  onClick={() => void sendChatMessage(item)}
                                >
                                  {item}
                                </button>
                              ))}
                            </div>
                          )}
                          <form className="chat-form inline" onSubmit={sendQuestion}>
                            <input
                              value={question}
                              onChange={(event) => setQuestion(event.target.value)}
                              placeholder="예: 내 순현금흐름은 안정적인가?"
                            />
                            <button className="icon-button solid" title="전송">
                              <Send size={18} />
                            </button>
                          </form>
                        </aside>
                      )}
                    </div>
                  </div>
                </>
              ) : (
                <EmptyState title="분석 결과 없음" description="왼쪽 입력값으로 첫 분석을 실행하세요." />
              )}
            </section>
          )}

          {activeTab === "history" && (
            <section className="content-area">
              <div className="history-list">
                {history.map((item) => (
                  <button
                    key={item.id}
                    className="history-item"
                    onClick={() => {
                      setAnalysis(item);
                      setActiveTab("analysis");
                    }}
                  >
                    <strong>{item.title}</strong>
                    <span>{new Date(item.created_at).toLocaleString("ko-KR")}</span>
                    <p>{item.result.summary}</p>
                  </button>
                ))}
                {history.length === 0 && <EmptyState title="저장된 분석 없음" description="분석을 저장하면 여기에 표시됩니다." />}
              </div>
            </section>
          )}
        </section>
      </section>
    </main>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="metric">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function EmptyState({ title, description }: { title: string; description: string }) {
  return (
    <div className="empty-state">
      <strong>{title}</strong>
      <span>{description}</span>
    </div>
  );
}

function formatCurrency(value: number) {
  return `${Math.round(value).toLocaleString("ko-KR")}원`;
}

function formatDebugStatus(status: string) {
  const labels: Record<string, string> = {
    generated: "LLM 생성",
    fallback_generated: "fallback 생성",
    llm_generated: "LLM 생성",
    llm_planned: "LLM 계획",
    llm_unavailable: "LLM 응답 없음",
    parse_error: "파싱 실패",
    invalid_tool: "허용되지 않은 tool",
    empty_by_llm: "LLM 0개 반환",
    filtered: "필터링됨",
    no_analysis: "분석 없음",
    none: "없음",
  };
  return labels[status] ?? status;
}

function formatToolCallLabel(name: string) {
  const labels: Record<string, string> = {
    get_analysis_summary: "분석 요약 조회",
    get_monthly_forecast: "월별 예측 조회",
    get_category_forecast: "카테고리 예측 조회",
    fetch_weather_context: "기상 정보 조회",
    fetch_real_estate_context: "부동산 외부 데이터 조회",
    search_web_context: "외부 정보 검색",
  };
  return labels[name] ?? name;
}

function buildInitialSuggestedQuestions(analysis: AnalysisResponse | null) {
  if (!analysis) return [];
  const forecastMonths = analysis.result.data_quality.forecast_months;
  return [
    "월별 순현금흐름을 알려줘",
    "카테고리별 지출을 보여줘",
    `${forecastMonths}개월 뒤 순자산은 얼마야?`,
  ];
}

function parseCsvUpload(file: File): Promise<CsvUploadResult> {
  return file.text().then((text) => {
    const rows = parseCsvRows(text);
    if (rows.length === 0) {
      throw new Error("CSV에 데이터가 없습니다.");
    }

    const headers = rows[0].map((value) => normalizeHeader(value));
    const cashflows: CashflowDraft[] = [];
    const assets: AssetDraft[] = [];

    for (const row of rows.slice(1)) {
      if (row.every((value) => value.trim() === "")) continue;
      const record = buildRecord(headers, row);
      if (isAssetRecord(record)) {
        const asset = parseAssetRecord(record);
        if (asset) assets.push(asset);
        continue;
      }
      const cashflow = parseCashflowRecord(record);
      if (cashflow) cashflows.push(cashflow);
    }

    if (cashflows.length === 0) {
      throw new Error("CSV에서 현금흐름 행을 찾지 못했습니다.");
    }

    return {
      title: file.name.replace(/\.[^.]+$/, "").replace(/[_-]+/g, " ").trim() || "CSV 업로드 분석",
      cashflows,
      assets,
    };
  });
}

function parseCsvRows(text: string): string[][] {
  const rows: string[][] = [];
  let row: string[] = [];
  let cell = "";
  let inQuotes = false;

  for (let index = 0; index < text.length; index += 1) {
    const char = text[index];
    const nextChar = text[index + 1];

    if (char === '"') {
      if (inQuotes && nextChar === '"') {
        cell += '"';
        index += 1;
      } else {
        inQuotes = !inQuotes;
      }
      continue;
    }

    if (char === "," && !inQuotes) {
      row.push(cell);
      cell = "";
      continue;
    }

    if ((char === "\n" || char === "\r") && !inQuotes) {
      if (char === "\r" && nextChar === "\n") {
        index += 1;
      }
      row.push(cell);
      if (row.some((value) => value.trim() !== "")) {
        rows.push(row);
      }
      row = [];
      cell = "";
      continue;
    }

    cell += char;
  }

  if (cell.length > 0 || row.length > 0) {
    row.push(cell);
    if (row.some((value) => value.trim() !== "")) {
      rows.push(row);
    }
  }

  return rows;
}

function buildRecord(headers: string[], row: string[]) {
  const record: Record<string, string> = {};
  headers.forEach((header, index) => {
    if (!header) return;
    record[header] = (row[index] ?? "").trim();
  });
  return record;
}

function normalizeHeader(value: string) {
  return value.trim().toLowerCase().replace(/\s+/g, "_");
}

function isAssetRecord(record: Record<string, string>) {
  const recordType = normalizeRecordType(record.record_type ?? record.type ?? "");
  return (
    recordType === "asset" ||
    Boolean(record.asset_type || record.asset_name || record.asset_value || record.current_value || record.region_code)
  );
}

function parseCashflowRecord(record: Record<string, string>): CashflowDraft | null {
  const dateValue = record.date || record.날짜 || "";
  const typeValue = normalizeCashflowType(record.type || record.수입지출 || "");
  const categoryValue = record.category || record.카테고리 || "";
  const amountValue = parseAmount(record.amount || record.금액 || "");
  if (!dateValue || !typeValue || !categoryValue || amountValue === null) {
    return null;
  }

  return {
    date: dateValue,
    type: typeValue,
    category: categoryValue,
    amount: String(amountValue),
    description: record.description || record.설명 || "",
  };
}

function parseAssetRecord(record: Record<string, string>): AssetDraft | null {
  const assetType = normalizeAssetType(record.asset_type || record.자산유형 || record.type || "");
  const name = record.asset_name || record.name || record.자산명 || "";
  const value = parseAmount(record.asset_value || record.current_value || record.가치 || record.amount || "");
  if (!assetType || !name || value === null) {
    return null;
  }

  return {
    type: assetType,
    name,
    current_value: String(value),
  };
}

function normalizeRecordType(value: string) {
  const normalized = value.trim().toLowerCase();
  if (["asset", "자산"].includes(normalized)) return "asset";
  if (["cashflow", "flow", "현금흐름", "거래"].includes(normalized)) return "cashflow";
  return normalized;
}

function normalizeCashflowType(value: string): CashflowType | "" {
  const normalized = value.trim().toLowerCase();
  if (["income", "inflow", "수입"].includes(normalized)) return "income";
  if (["expense", "outflow", "지출"].includes(normalized)) return "expense";
  return "";
}

function normalizeAssetType(value: string): AssetDraft["type"] | "" {
  const normalized = value.trim().toLowerCase();
  if (["cash", "현금", "예금", "저축"].includes(normalized)) return "cash";
  if (["pension", "연금"].includes(normalized)) return "pension";
  if (["real_estate", "부동산", "아파트", "주택"].includes(normalized)) return "real_estate";
  if (["other", "기타"].includes(normalized)) return "other";
  return "";
}

function parseAmount(value: string) {
  const numeric = Number(value.replace(/,/g, "").trim());
  if (!Number.isFinite(numeric) || numeric < 0) return null;
  return numeric;
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
