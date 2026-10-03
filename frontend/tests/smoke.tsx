import React, { act, useState } from "react";
import { createRoot } from "react-dom/client";
import { api } from "../src/api";
import { useRun } from "../src/hooks/useRun";
import { usePreviewSelection } from "../src/pages/preview/usePreviewSelection";
import { Ledger } from "../src/pages/preview/Ledger";
import { Inspector } from "../src/pages/preview/Inspector";
import { FolderBrowser } from "../src/components/FolderBrowser";
import { demoBootstrap, demoPlan } from "../src/demo/fixtures";
import type { Run, PreviewItem } from "../src/types";

Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true, EventSource: undefined });
const fixture = document.getElementById("fixture")!;
const results: string[] = [];
const runtimeErrors: string[] = [];
window.addEventListener("error",event=>runtimeErrors.push(event.message));
window.addEventListener("unhandledrejection",event=>runtimeErrors.push(String(event.reason)));
const assert = (value: unknown, message: string) => { if (!value) throw new Error(message); };
const root = createRoot(fixture);
const flush = () => act(async () => { await Promise.resolve(); });
const snapshot: Run = { id:"run",kind:"preview",state:"running",completed:0,total:1,current_file:"",message:"Working",plan_id:null,report_id:null,error:null };
let currentRun: ReturnType<typeof useRun>;
function RunHarness({id = "run"}: {id?: string}) { currentRun = useRun(id, (run) => { results.push(`terminal:${run.id}`); }); return <span>{currentRun.error || currentRun.run?.state}</span>; }

async function runTests() {
  const realTimeout = window.setTimeout;
  const realClear = window.clearTimeout;
  const timers = new Map<number, () => void>();
  let sequence = 0;
  window.setTimeout = ((fn: () => void) => {timers.set(++sequence,fn); return sequence;}) as typeof window.setTimeout;
  window.clearTimeout = (id) => { if (id !== undefined) timers.delete(id); };
  const tick = async () => { const pending = [...timers.values()]; timers.clear(); await act(async () => { pending.forEach(fn=>fn()); }); };
  let requests = 0;
  api.run = async () => { requests++; if (requests <= 5) throw Error("Offline"); return {...snapshot,state:"completed"}; };
  await act(async () => root.render(<RunHarness />));
  for(let i=0;i<4;i++) await tick();
  assert(requests === 5 && timers.size === 0, "Polling must stop after five consecutive failures");
  assert(fixture.textContent?.includes("Automatic retries paused"), "Retry guidance visible");
  await act(async () => currentRun.retry());
  assert(currentRun!.run?.state === "completed", "Manual retry recovers failed polling");
  assert(results.filter(x=>x==="terminal:run").length === 1, "Terminal callback called once");
  results.push("PASS bounded polling and manual retry recovery");
  await act(async()=>root.render(<span />));
  let resolveOld!: (value: Run) => void;
  api.run = (id) => id === "old" ? new Promise(resolve=>{resolveOld=resolve;}) : Promise.resolve({...snapshot,id,state:"completed"});
  await act(async()=>root.render(<RunHarness id="old" />));
  await act(async()=>root.render(<RunHarness id="new" />));
  await act(async()=>resolveOld({...snapshot,id:"old",state:"completed"}));
  assert(currentRun!.run?.id === "new", "Old run cannot replace new run");
  results.push("PASS stale polling response ignored");
  await act(async()=>root.render(<span />));
  class FakeEvents {
    static latest: FakeEvents;
    listeners = new Map<string, (event: MessageEvent) => void>();
    onerror: (() => void) | null = null;
    closed = false;
    constructor() { FakeEvents.latest = this; }
    addEventListener(name: string, callback: (event: MessageEvent) => void) { this.listeners.set(name, callback); }
    close() { this.closed = true; }
    emit(name: string, value: Run) { this.listeners.get(name)?.(new MessageEvent(name,{data:JSON.stringify(value)})); }
  }
  Object.assign(globalThis,{EventSource:FakeEvents});
  api.run=async()=>snapshot;
  await act(async()=>root.render(<RunHarness />));
  assert(FakeEvents.latest.listeners.has("run.snapshot"),"Named snapshot listener installed");
  await act(async()=>FakeEvents.latest.emit("run.progress",{...snapshot,completed:1}));
  assert(currentRun!.run?.completed===1,"Named progress event updates hook");
  await act(async()=>FakeEvents.latest.emit("run.completed",{...snapshot,state:"completed"}));
  assert(FakeEvents.latest.closed && timers.size===0,"Terminal event closes stream and polling");
  results.push("PASS named SSE progress and terminal cleanup");
  Object.assign(globalThis,{EventSource:undefined});
  window.setTimeout = realTimeout; window.clearTimeout = realClear;

  const plan = {...demoPlan,items:Array.from({length:10000},(_,i)=>({...demoPlan.items[0],id:String(i),current_name:`source-${i}.pdf`,proposed_name:`target-${i}.pdf`,status:"ready" as const} ))};
  let selection: ReturnType<typeof usePreviewSelection>;
  function SelectionHarness() {
    const [selected,setSelected]=useState(new Set<string>());
    const [activeId,setActiveId]=useState("0");
    selection=usePreviewSelection(plan,selected,setSelected,activeId);
    return <Ledger plan={plan} {...selection} error="" onPageChange={selection.setPage} totalItems={selection.totalItems} onQueryChange={selection.setQuery} onToggle={selection.toggle} onSelectVisible={selection.selectVisible} onClear={()=>setSelected(new Set())} onActivate={setActiveId} onDismissError={()=>{}} />;
  }
  await act(async()=>root.render(<SelectionHarness />));
  assert(fixture.querySelectorAll('[role="option"]').length===50,"Large preview DOM bounded to 50 rows");
  const clickButton = (label: string) => { const button = [...fixture.querySelectorAll('button')].find(button=>button.textContent===label); assert(button,`Missing button ${label}`); button!.click(); };
  await act(async()=>clickButton("Select page"));
  await act(async()=>clickButton("Next page"));
  assert(selection!.selected.size===50 && selection!.visibleItems[0].id==="50","Selection retained across pages");
  assert(selection!.activeId === "50", "Paging moves active evidence onto current page");
  const row = fixture.querySelector<HTMLElement>('[role="option"]')!;
  await act(async()=>row.dispatchEvent(new KeyboardEvent("keydown",{key:"End",bubbles:true,cancelable:true})));
  assert(selection!.activeId === "99" && document.activeElement?.getAttribute("data-id") === "99", "End focuses last row on current page");
  await act(async()=>document.activeElement!.dispatchEvent(new KeyboardEvent("keydown",{key:"ArrowDown",bubbles:true,cancelable:true})));
  assert(selection!.activeId === "99", "Arrow navigation remains inside current page");
  const checkbox = fixture.querySelector<HTMLInputElement>('input[type="checkbox"]')!;
  const space = new KeyboardEvent("keydown",{key:" ",bubbles:true,cancelable:true});
  checkbox.dispatchEvent(space);
  assert(!space.defaultPrevented, "Row handler preserves native checkbox Space activation");
  await act(async()=>selection.toggle("50"));
  await act(async()=>selection.setQuery("source-9999"));
  assert(selection!.selected.size===51 && selection!.visibleItems.length===1,"Selection retained across filtering");
  assert(selection!.activeId === "9999", "Filtering keeps active evidence on a visible row");
  await act(async()=>selection.setQuery(""));
  assert(selection!.selected.has("50"),"Off-page selected ID retained");
  results.push("PASS 10,000-item preview DOM and selection across pages/filtering");

  let resolveDetail!: (value: PreviewItem)=>void;
  api.item=(_plan,id)=> id==="0" ? new Promise(resolve=>{resolveDetail=resolve;}) : Promise.resolve({...plan.items[1],metadata:{title:"New evidence"}});
  await act(async()=>root.render(<Inspector plan={plan} item={plan.items[0]} />));
  await act(async()=>root.render(<Inspector plan={plan} item={plan.items[1]} />));
  await act(async()=>resolveDetail({...plan.items[0],metadata:{title:"Stale evidence"}}));
  await flush();
  assert(fixture.textContent?.includes("New evidence") && !fixture.textContent?.includes("Stale evidence"),"Inspector ignores stale details");
  await act(async()=>fixture.querySelector("img")?.dispatchEvent(new Event("error")));
  assert(fixture.textContent?.includes("First page unavailable"),"Thumbnail has explicit error state");
  results.push("PASS inspector race and thumbnail error state");
  let resolveFolder!: (value: {path:string;parent:null;entries:[];pdf_count:number}) => void;
  api.filesystem=(path)=>path==="/old" ? new Promise(resolve=>{resolveFolder=resolve;}) : Promise.resolve({path,parent:null,entries:[],pdf_count:7});
  const folderProps={bootstrap:demoBootstrap,open:true,onClose:()=>{},onChoose:()=>{}};
  await act(async()=>root.render(<FolderBrowser {...folderProps} initialPath="/old" />));
  await act(async()=>root.render(<FolderBrowser {...folderProps} initialPath="/new" />));
  await act(async()=>resolveFolder({path:"/old",parent:null,entries:[],pdf_count:1}));
  assert(document.querySelector<HTMLInputElement>('input[aria-label="Folder path"]')?.value==="/new","Stale folder response ignored");
  assert(document.body.textContent?.includes("7 PDFs in this folder"),"Selected folder count stays current");
  results.push("PASS folder navigation stale response guard");
  await act(async()=>root.unmount());
  assert(runtimeErrors.length === 0, `Unexpected runtime errors: ${runtimeErrors.join(", ")}`);
  document.getElementById("results")!.textContent=results.join("\n");
  document.body.dataset.result="passed";
}
runTests().catch(error=>{document.getElementById("results")!.textContent=String(error.stack??error);document.body.dataset.result="failed";});
