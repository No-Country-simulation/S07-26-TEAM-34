import { useRef, useState } from "react";
import { Footer } from "./components/Footer";
import { Header } from "./components/Header";
import { Hero } from "./components/Hero";
import { HowItWorks } from "./components/HowItWorks";
import { ResultsSection } from "./components/results/ResultsSection";
import { SurveySection } from "./components/survey/SurveySection";
import type { ResultadoResponse } from "./types";

function App() {
  const [resultado, setResultado] = useState<ResultadoResponse | null>(null);
  const resultsRef = useRef<HTMLDivElement>(null);

  function handleResultado(r: ResultadoResponse) {
    setResultado(r);
    requestAnimationFrame(() => {
      resultsRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  }

  return (
    <div id="top" className="min-h-screen">
      <Header />
      <Hero />
      <HowItWorks />
      <SurveySection onResultado={handleResultado} />
      <div ref={resultsRef}>
        <ResultsSection resultado={resultado} />
      </div>
      <Footer />
    </div>
  );
}

export default App;
