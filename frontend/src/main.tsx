import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import {
  BarChart3,
  Bot,
  Download,
  History,
  Loader2,
  Plus,
  Send,
  Sparkles,
  Trash2,
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
import { FormEvent, useEffect, useMemo, useState } from "react";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

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
};

const testQuestions = [
  "전기요금 예측을 위해 기상청 API를 호출해줘",
  "부동산 순자산 분석을 위해 부동산 통계 API를 호출해줘",
  "최근 금리와 경제 상황을 Tavily로 검색해서 내 분석과 연결해줘",
];

const defaultCashflows: CashflowDraft[] = [
  ...Array.from({ length: 12 }, (_, index) => {
    const month = `${index + 1}`.padStart(2, "0");
    return [
      { date: `2025-${month}-01`, amount: "3000000", type: "income" as const, category: "월급", description: "" },
      { date: `2025-${month}-10`, amount: "650000", type: "income" as const, category: "연금", description: "" },
      {
        date: `2025-${month}-05`,
        amount: `${950000 + index * 15000}`,
        type: "expense" as const,
        category: "생활비",
        description: "",
      },
      {
        date: `2025-${month}-18`,
        amount: `${130000 + (index % 4) * 25000}`,
        type: "expense" as const,
        category: "전기요금",
        description: "계절성 공과금",
      },
    ];
  }).flat(),
];

function App() {
  const [title, setTitle] = useState("12개월 현금흐름 분석");
  const [forecastMonths, setForecastMonths] = useState(6);
  const [cashflows, setCashflows] = useState<CashflowDraft[]>(defaultCashflows);
  const [assets, setAssets] = useState<AssetDraft[]>([
    { type: "cash", name: "예금", current_value: "12000000" },
    { type: "real_estate", name: "아파트", current_value: "420000000" },
  ]);
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
                                {message.suggestionStatus && (
                                  <span className="suggestion-debug" title={message.suggestionReason ?? undefined}>
                                    추천 {message.suggestionStatus}
                                  </span>
                                )}
                              </div>
                            ))}
                            {chatLoading && <div className="message assistant">답변 생성 중...</div>}
                          </div>
                          <div className="test-question-buttons">
                            {testQuestions.map((item) => (
                              <button type="button" key={item} disabled={chatLoading} onClick={() => void sendChatMessage(item)}>
                                {item}
                              </button>
                            ))}
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

function buildInitialSuggestedQuestions(analysis: AnalysisResponse | null) {
  if (!analysis) return [];
  const forecastMonths = analysis.result.data_quality.forecast_months;
  return [
    "월별 순현금흐름을 알려줘",
    "카테고리별 지출을 보여줘",
    `${forecastMonths}개월 뒤 순자산은 얼마야?`,
  ];
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
