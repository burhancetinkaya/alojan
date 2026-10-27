"use client";
import { createContext, useContext, useEffect, useState } from "react";
import type { Agent, Draft } from "@/lib/api";

type Memory = {
  session: string | null;
  drafts: Map<string, { saved: Agent; draft: Draft }>;
};
const Context = createContext<Memory | null>(null);

// Above route pages so browser history cannot destroy an unsaved editor draft.
export function DraftMemory({ children }: { children: React.ReactNode }) {
  const [memory] = useState<Memory>(() => ({
    session: null,
    drafts: new Map(),
  }));
  useEffect(() => {
    const warn = (event: BeforeUnloadEvent) => {
      if (memory.drafts.size) event.preventDefault();
    };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [memory]);
  return <Context.Provider value={memory}>{children}</Context.Provider>;
}

export function useDraftMemory() {
  const memory = useContext(Context);
  if (!memory) throw new Error("Draft memory provider required");
  return memory;
}
