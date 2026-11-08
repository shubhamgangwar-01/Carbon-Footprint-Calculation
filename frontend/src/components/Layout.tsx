import { BookOpen, Calculator, FolderOpen, Leaf, LogIn, LogOut, Menu, Shield, X } from "lucide-react";
import { useState } from "react";
import { Link, NavLink, Outlet, useNavigate } from "react-router-dom";
import { currentUser, logout } from "../services/api";

export default function Layout() {
  const [open, setOpen] = useState(false);
  const nav = useNavigate();
  const user = currentUser();
  const link = ({ isActive }: { isActive: boolean }) =>
    `flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium ${isActive ? "bg-mint-100 text-forest-800" : "text-slate-600 hover:bg-slate-100"}`;
  const items = (
    <>
      <NavLink to="/calculator/basic" className={link} onClick={() => setOpen(false)}><Calculator size={16} />Calculator</NavLink>
      <NavLink to="/conferences" className={link} onClick={() => setOpen(false)}><FolderOpen size={16} />My conferences</NavLink>
      <NavLink to="/methodology" className={link} onClick={() => setOpen(false)}><BookOpen size={16} />Methodology & data</NavLink>
      {user?.role === "admin" && <NavLink to="/admin" className={link} onClick={() => setOpen(false)}><Shield size={16} />Admin</NavLink>}
      {user && user.role !== "guest" ? (
        <button className="flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium text-slate-600 hover:bg-slate-100"
          onClick={() => { logout(); nav("/"); window.location.reload(); }}><LogOut size={16} />Sign out</button>
      ) : (
        <NavLink to="/login" className={link} onClick={() => setOpen(false)}><LogIn size={16} />Sign in</NavLink>
      )}
    </>
  );
  return (
    <div className="flex min-h-screen flex-col">
      <header className="sticky top-0 z-40 border-b border-slate-200 bg-white/90 backdrop-blur">
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6">
          <Link to="/" className="flex items-center gap-2 font-semibold text-forest-800">
            <span className="rounded-lg bg-forest-700 p-1.5 text-white"><Leaf size={18} /></span>
            <span className="hidden sm:inline">Conference Carbon Calculator</span><span className="sm:hidden">CCC</span>
          </Link>
          <nav className="hidden items-center gap-1 md:flex">{items}</nav>
          <button className="btn-ghost md:hidden" aria-label="Menu" onClick={() => setOpen(!open)}>{open ? <X size={20} /> : <Menu size={20} />}</button>
        </div>
        {open && <nav className="flex flex-col gap-1 border-t border-slate-200 bg-white px-4 py-3 md:hidden">{items}</nav>}
      </header>
      <main className="flex-1"><Outlet /></main>
      <footer className="border-t border-slate-200 bg-white">
        <div className="mx-auto flex max-w-7xl flex-col gap-1 px-4 py-6 text-xs text-slate-500 sm:px-6 md:flex-row md:justify-between">
          <p>Emission factors: CEA CO₂ Baseline v22.0 · UK DESNZ 2026 · India GHG Program · Poore & Nemecek (2018) / OWID · ICMR-NIN.</p>
          <p>GHG Protocol & ISO 14064-1 aligned · results are unverified estimates.</p>
        </div>
      </footer>
    </div>
  );
}
