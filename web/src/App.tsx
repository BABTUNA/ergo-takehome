import { useEffect, useState } from "react";
import { DealView } from "./DealView";
import { PipelineList } from "./PipelineList";

function useHashRoute(): string {
  const [hash, setHash] = useState(window.location.hash);
  useEffect(() => {
    const onChange = () => setHash(window.location.hash);
    window.addEventListener("hashchange", onChange);
    return () => window.removeEventListener("hashchange", onChange);
  }, []);
  return hash;
}

export default function App() {
  const hash = useHashRoute();
  const dealMatch = hash.match(/^#\/deal\/([a-z0-9-]+)/);
  return (
    <div className="shell">
      {dealMatch ? <DealView slug={dealMatch[1]} /> : <PipelineList />}
    </div>
  );
}
