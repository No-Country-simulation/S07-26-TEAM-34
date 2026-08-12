import { useState } from "react";
import { BottomCTA } from "./components/BottomCTA";
import { DimensionsTimeline } from "./components/DimensionsTimeline";
import { Footer } from "./components/Footer";
import { FocusHeader } from "./components/FocusHeader";
import { Header } from "./components/Header";
import { Hero } from "./components/Hero";
import { WhatYouGet } from "./components/WhatYouGet";
import { ResultsSection } from "./components/results/ResultsSection";
import { SurveySection } from "./components/survey/SurveySection";
import type { ResultadoResponse } from "./types";

type View = "landing" | "survey" | "results";

function App() {
  const [view, setView] = useState<View>("landing");
  const [resultado, setResultado] = useState<ResultadoResponse | null>(null);

  function startSurvey() {
    setView("survey");
    window.scrollTo({ top: 0 });
  }

  function backToLanding() {
    setView("landing");
    setResultado(null);
  }

  function handleResultado(r: ResultadoResponse) {
    setResultado(r);
    setView("results");
    window.scrollTo({ top: 0 });
  }

  if (view === "survey") {
    return (
      <div className="min-h-screen">
        <FocusHeader onBack={backToLanding} />
        <SurveySection onResultado={handleResultado} />
      </div>
    );
  }

  if (view === "results" && resultado) {
    return (
      <div className="min-h-screen">
        <FocusHeader onBack={backToLanding} label="Nuevo diagnóstico" />
        <ResultsSection resultado={resultado} />
      </div>
    );
  }

  return (
    <div id="top" className="min-h-screen">
      <Header onStart={startSurvey} />
      <Hero onStart={startSurvey} />
      <DimensionsTimeline />
      <WhatYouGet />
      <BottomCTA onStart={startSurvey} />
      <Footer />
    </div>
  );
}

export default App;
