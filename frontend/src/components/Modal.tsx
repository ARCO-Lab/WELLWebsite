import React, { useEffect, useState } from "react";

interface ModalProps {
  isOpen: boolean;
  onClose: () => void;
  children: React.ReactNode;
  type: "weather" | "logger" | "quality"; // to pass to the analysis API
  subtypes?: string[]; // optional, for future use
  analysisType: "recent" | "alltime"
  data: any;
  weatherTab?: "graph" | "windrose";
  setWeatherTab?: (tab: "graph" | "windrose") => void;
}

type AiAnalysisResponse = { analysis: string } | string | null;

const Modal: React.FC<ModalProps> = ({ isOpen, onClose, children, type, subtypes, analysisType, weatherTab, setWeatherTab}) => {
  const [tabAnalysis, setTabAnalysis] = useState<{ [tab: string]: AiAnalysisResponse }>({});
  const [tabLoading, setTabLoading] = useState<{ [tab: string]: boolean }>({});
  const [tabRequested, setTabRequested] = useState<{ [tab: string]: boolean }>({});

  const fetchAnalysis = async () => {
    const tab = weatherTab || "graph";
    try {
      setTabLoading(prev => ({ ...prev, [tab]: true }));
      setTabRequested(prev => ({ ...prev, [tab]: true }));

      // Build URL
      const params = new URLSearchParams();
      params.append("type", type);

      let endpoint = `/api/analysis/${analysisType}`;
      if (
        analysisType === "alltime" &&
        type === "weather" &&
        weatherTab === "windrose"
      ) {
        endpoint = "/api/analysis/wind";
        // Only send wind/gust as subtypes
        const hasWind = subtypes?.some(s => s.toLowerCase().includes("wind speed"));
        const hasGust = subtypes?.some(s => s.toLowerCase().includes("gust speed"));
        if (hasWind) params.append("subtypes", "wind");
        if (hasGust) params.append("subtypes", "gust");
      } else if (subtypes && subtypes.length > 0) {
        subtypes.forEach((s) => params.append("subtypes", s));
      }

      const res = await fetch(`${endpoint}?${params.toString()}`);
      const json = await res.json();
      setTabAnalysis(prev => ({ ...prev, [tab]: json }));
    } catch (err) {
      setTabAnalysis(prev => ({ ...prev, [tab]: "Failed to load analysis." }));
    } finally {
      setTabLoading(prev => ({ ...prev, [tab]: false }));
    }
  };



  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  useEffect(() => {
    if (!isOpen) {
      setTabAnalysis({});
      setTabLoading({});
      setTabRequested({});
    }
  }, [isOpen]);


  function renderFormattedAnalysis(analysis: string) {
    // Normalize headings: ensure all are surrounded by ** and end with :
    let normalized = analysis.replace(
      /^([A-Za-z ]+):/gm,
      (_, heading) => `**${heading.trim()}**:`
    );

    // Match sections like **HEADER:** followed by content, up until the next **HEADER:**
    const regex = /\*\*(.+?)\*\*\s*:?([\s\S]*?)(?=(\*\*[^*]+\*\*:|$))/g;
    const result = [];
    let match;

    while ((match = regex.exec(normalized)) !== null) {
      const headingRaw = match[1].trim().replace(/:$/, "");
      const heading = headingRaw.charAt(0).toUpperCase() + headingRaw.slice(1);
      const content = match[2].trim();

      result.push(
        <div key={heading} className="mb-4">
          <h4 className="font-bold text-base text-black">{heading}</h4>
          {content.split("\n").map((line, idx) => {
            const trimmed = line.trim();
            if (!trimmed) return null;

            // Handle bullet points with **bold label**: description
            const bulletMatch = /^\s*-\s*\*\*(.+?)\*\*\s*:?(.+)?$/.exec(trimmed);
            if (bulletMatch) {
              return (
                <div key={idx} className="flex items-start text-sm text-black mb-1">
                  <span className="mr-2">•</span>
                  <span>
                    <span className="font-semibold">{bulletMatch[1].trim()}:</span>
                    {bulletMatch[2] ? ` ${bulletMatch[2].trim()}` : ""}
                  </span>
                </div>
              );
            }

            // Handle regular bullet points
            const simpleBullet = /^\s*-\s*(.+)$/.exec(trimmed);
            if (simpleBullet) {
              const html = simpleBullet[1].replace(/\*\*(.+?)\*\*/g, "<b>$1</b>");
              return (
                <div key={idx} className="flex items-start text-sm text-black mb-1">
                  <span className="mr-2">•</span>
                  <span dangerouslySetInnerHTML={{ __html: html }} />
                </div>
              );
            }

            // Handle regular lines with **bold** text
            const html = trimmed.replace(/\*\*(.+?)\*\*/g, "<b>$1</b>");
            return (
              <div key={idx} className="text-sm text-black mb-1" dangerouslySetInnerHTML={{ __html: html }} />
            );
          })}
        </div>
      );
    }

    // Fallback if no sections matched
    if (result.length === 0) {
      const html = analysis.replace(/\*\*(.+?)\*\*/g, "<b>$1</b>");
      return (
        <pre className="whitespace-pre-wrap text-sm text-black" dangerouslySetInnerHTML={{ __html: html }} />
      );
    }

    return result;
  }

  if (!isOpen) return null;

  const tab = weatherTab || "graph";
  const aiAnalysis = tabAnalysis[tab];
  const loading = tabLoading[tab];
  const analysisRequested = tabRequested[tab];

  return (
    <>
      {/* Overlay */}
      <div
        onClick={onClose}
        className="fixed inset-0 z-40 transition-opacity bg-black/40"
      />

      {/* Modal content */}
      <div className="fixed inset-0 z-50 flex items-center justify-center pointer-events-none">
        <div
          onClick={(e) => e.stopPropagation()}
          className="relative pointer-events-auto bg-white p-6 rounded-lg shadow-lg border border-gray-300
          w-full h-full max-w-[calc(100vw-40px)] max-h-[calc(100vh-40px)] m-0 overflow-y-auto"
        >
          {/* Main content */}
          {React.isValidElement(children)
            ? React.cloneElement(children as React.ReactElement<any>, { modalOpen: isOpen, inModal: true, weatherTab, setWeatherTab, })
            : children}

          {/* AI Analysis trigger & output */}
          <div className="mt-6 p-4 bg-blue-50 border border-blue-200 rounded">
            <h3 className="text-md text-black font-bold mb-2">AI Analysis</h3>

            {!analysisRequested ? (
              <button
                onClick={fetchAnalysis}
                className="px-4 py-2 text-sm font-semibold text-white bg-blue-600 rounded hover:bg-blue-700"
              >
                Run AI Analysis
              </button>
            ) : loading ? (
              <p className="text-sm text-gray-600">Analyzing data...</p>
            ) : (
              aiAnalysis && typeof aiAnalysis === "object" && aiAnalysis.analysis
                ? renderFormattedAnalysis(aiAnalysis.analysis)
                : <pre className="text-sm text-gray-800 whitespace-pre-wrap">{JSON.stringify(aiAnalysis, null, 2)}</pre>
            )}
          </div>
        </div>
      </div>
    </>
  );
};

export default Modal;
