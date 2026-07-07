"use client";

import { useEffect, useRef, useState } from "react";

let mermaidModule: any = null;

async function getMermaid() {
  if (!mermaidModule) {
    mermaidModule = await import("mermaid");
    mermaidModule.default.initialize({
      startOnLoad: false,
      theme: "default",
      securityLevel: "loose",
      fontFamily: "inherit",
    });
  }
  return mermaidModule.default;
}

interface Props {
  chart: string;
}

export default function MermaidBlock({ chart }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    if (!ref.current) return;
    setError(false);
    ref.current.innerHTML = chart;

    getMermaid()
      .then((mermaid) =>
        mermaid.run({ nodes: [ref.current!], suppressErrors: true })
      )
      .catch(() => setError(true));
  }, [chart]);

  if (error) {
    return (
      <div className="my-2 p-3 rounded-lg bg-danger/10 dark:bg-danger/10 border border-danger/20 dark:border-danger/20 text-xs text-danger dark:text-danger">
        <p className="font-medium mb-1">图表渲染失败</p>
        <pre className="whitespace-pre-wrap">{chart}</pre>
      </div>
    );
  }

  return (
    <div className="my-2 flex justify-center overflow-x-auto py-2">
      <div
        ref={ref}
        className="mermaid max-w-full"
        style={{ minWidth: "200px" }}
      >
        {chart}
      </div>
    </div>
  );
}
