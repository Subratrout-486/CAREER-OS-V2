"use client";

import { useState } from "react";
import { ArrowUpRight, Bell, BriefcaseBusiness, CheckCircle2, ChevronRight, Command, FileText, Gauge, Search, Sparkles, Target, UserRound } from "lucide-react";
import { motion } from "motion/react";

const nav = ["Overview", "Jobs", "Matches", "Resume Studio", "Applications", "Agents", "Interview", "Learning"];

export default function Home() {
  const [active, setActive] = useState("Overview");
  const [command, setCommand] = useState("");
  const [message, setMessage] = useState("");

  const runCommand = (e: React.FormEvent) => {
    e.preventDefault();
    const value = command.trim();
    if (!value) return;
    setMessage(`Command queued: ${value}`);
    setCommand("");
  };

  return (
    <main className="min-h-screen px-4 py-4 sm:px-6 lg:px-8">
      <div className="mx-auto flex max-w-[1500px] gap-5">
        <aside className="hidden w-60 shrink-0 flex-col border-r border-white/10 pr-5 lg:flex">
          <div className="mb-8 flex items-center gap-3 px-2 pt-2">
            <div className="grid h-9 w-9 place-items-center rounded-xl bg-white text-black"><Sparkles size={18}/></div>
            <div><div className="font-semibold tracking-tight">CareerOS</div><div className="text-xs text-[var(--muted)]">AI career operating system</div></div>
          </div>
          <nav className="space-y-1" aria-label="Primary navigation">
            {nav.map((item, i) => (
              <button key={item} onClick={() => setActive(item)} className={`flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left text-sm transition ${active === item ? "bg-white/8 text-white" : "text-[var(--muted)] hover:bg-white/5 hover:text-white"}`}>
                {[Gauge, Search, Target, FileText, BriefcaseBusiness, Sparkles, UserRound, ArrowUpRight][i]({ size: 16 })}
                <span>{item}</span>
              </button>
            ))}
          </nav>
          <div className="mt-auto rounded-2xl border border-white/10 bg-white/[.035] p-4">
            <div className="mb-2 flex items-center gap-2 text-xs font-medium text-white"><CheckCircle2 size={14} className="text-[var(--success)]"/> System boundary</div>
            <p className="text-xs leading-5 text-[var(--muted)]">CareerOS V2 remains the source of truth. UI actions must call real capabilities.</p>
          </div>
        </aside>

        <section className="min-w-0 flex-1">
          <header className="mb-8 flex items-center justify-between gap-4">
            <div className="lg:hidden flex items-center gap-2 font-semibold"><div className="grid h-8 w-8 place-items-center rounded-lg bg-white text-black"><Sparkles size={16}/></div>CareerOS</div>
            <form onSubmit={runCommand} className="hidden max-w-xl flex-1 md:flex">
              <div className="flex w-full items-center gap-2 rounded-xl border border-white/10 bg-white/[.035] px-3 py-2 text-sm focus-within:border-white/20">
                <Command size={15} className="text-[var(--muted)]"/><input value={command} onChange={e=>setCommand(e.target.value)} className="min-w-0 flex-1 bg-transparent outline-none placeholder:text-[var(--muted)]" placeholder="Ask CareerOS…" aria-label="Ask CareerOS"/><kbd className="rounded border border-white/10 px-1.5 py-0.5 text-[10px] text-[var(--muted)]">⌘K</kbd>
              </div>
            </form>
            <div className="flex items-center gap-2"><button type="button" aria-label="Notifications" className="grid h-10 w-10 place-items-center rounded-xl border border-white/10 bg-white/[.03] text-[var(--muted)] hover:text-white"><Bell size={17}/></button><button type="button" className="flex items-center gap-2 rounded-xl border border-white/10 bg-white/[.03] px-3 py-2 text-sm"><span className="grid h-6 w-6 place-items-center rounded-full bg-white/10">S</span><span className="hidden sm:inline">Subrat</span></button></div>
          </header>

          <div className="mb-8">
            <p className="mb-2 text-sm text-[var(--muted)]">Tuesday · Command Center</p>
            <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">Good morning, Subrat <span aria-hidden>👋</span></h1>
            <p className="mt-2 max-w-2xl text-[var(--muted)]">Your career workspace is ready. Real job intelligence and application actions will appear here as the V2 API is connected.</p>
          </div>

          <motion.div initial={{opacity:0,y:8}} animate={{opacity:1,y:0}} className="mb-6 overflow-hidden rounded-3xl border border-white/10 bg-gradient-to-br from-white/[.08] to-white/[.025] p-5 sm:p-7">
            <div className="flex flex-col justify-between gap-7 md:flex-row md:items-end">
              <div><div className="mb-3 flex items-center gap-2 text-xs font-medium uppercase tracking-[.18em] text-[var(--accent)]"><Sparkles size={14}/> Career intelligence</div><h2 className="max-w-2xl text-2xl font-semibold tracking-tight">One workspace for discovering, preparing and applying.</h2><p className="mt-2 max-w-xl text-sm leading-6 text-[var(--muted)]">No fake scores or placeholder jobs. This shell is intentionally waiting for the real CareerOS V2 pipeline.</p></div>
              <button type="button" onClick={()=>setMessage("V2 job pipeline is not connected to this UI yet.")} className="inline-flex items-center justify-center gap-2 rounded-xl bg-white px-4 py-2.5 text-sm font-semibold text-black transition hover:bg-white/90">Check pipeline <ArrowUpRight size={16}/></button>
            </div>
          </motion.div>

          <div className="mb-6 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            {[['Jobs','—','Available after API connection'],['Strong matches','—','Evidence-backed only'],['Applications','—','Tracked from V2'],['Ready to apply','—','Approval boundary']].map(([label,value,sub],i)=><motion.div key={label} initial={{opacity:0,y:10}} animate={{opacity:1,y:0}} transition={{delay:i*.05}} className="rounded-2xl border border-white/10 bg-[var(--panel)] p-4"><div className="text-sm text-[var(--muted)]">{label}</div><div className="mt-3 text-3xl font-semibold tracking-tight">{value}</div><div className="mt-1 text-xs text-[var(--muted)]">{sub}</div></motion.div>)}
          </div>

          <div className="grid gap-6 xl:grid-cols-[1.5fr_1fr]">
            <section className="rounded-2xl border border-white/10 bg-[var(--panel)] p-5"><div className="mb-5 flex items-center justify-between"><div><h3 className="font-semibold">Top opportunities</h3><p className="mt-1 text-xs text-[var(--muted)]">Only verified data will populate this list.</p></div><button type="button" onClick={()=>setActive("Jobs")} className="text-xs text-[var(--muted)] hover:text-white">Open jobs <ChevronRight size={14} className="inline"/></button></div><div className="rounded-xl border border-dashed border-white/10 p-8 text-center"><Target className="mx-auto mb-3 text-[var(--muted)]" size={22}/><p className="text-sm">No live jobs connected yet.</p><p className="mt-1 text-xs text-[var(--muted)]">Next integration step: connect this workspace to the V2 job pipeline.</p></div></section>
            <section className="rounded-2xl border border-white/10 bg-[var(--panel)] p-5"><h3 className="font-semibold">Agent activity</h3><div className="mt-5 space-y-4"><Agent name="Job Scout" detail="Awaiting live job source"/><Agent name="Fit Scorer" detail="Awaiting job + evidence payload"/><Agent name="Resume Tailor" detail="Awaiting selected opportunity"/><Agent name="ATS Auditor" detail="Approval boundary protected"/></div></section>
          </div>

          <form onSubmit={runCommand} className="mt-6 md:hidden flex items-center gap-2 rounded-xl border border-white/10 bg-white/[.035] px-3 py-2"><Command size={15} className="text-[var(--muted)]"/><input value={command} onChange={e=>setCommand(e.target.value)} className="min-w-0 flex-1 bg-transparent py-1 text-sm outline-none placeholder:text-[var(--muted)]" placeholder="Ask CareerOS…"/><button className="text-xs text-white">Run</button></form>
          {message && <div role="status" className="mt-4 rounded-xl border border-white/10 bg-white/[.04] px-4 py-3 text-sm text-[var(--muted)]">{message}</div>}
        </section>
      </div>
    </main>
  );
}

function Agent({name, detail}:{name:string;detail:string}) { return <div className="flex items-start gap-3"><span className="mt-1 h-2 w-2 rounded-full bg-[var(--warning)] shadow-[0_0_12px_rgba(242,200,107,.45)]"/><div className="min-w-0"><div className="text-sm font-medium">{name}</div><div className="text-xs text-[var(--muted)]">{detail}</div></div></div>; }
