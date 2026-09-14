"use client";
import Link from "next/link";
import { usePathname,useRouter } from "next/navigation";
import { LayoutDashboard,FileText,Layers,CalendarDays,Link2,Settings,LogOut,Menu,X,ChevronDown } from "lucide-react";
import { useEffect,useState } from "react";
import { clearAccessToken,getUsername } from "../lib/auth";
import { getDashboardOverview,ApiError } from "../lib/api";
import BrandMark from "./BrandMark";

const nav=[{label:"Overview",href:"/dashboard",icon:LayoutDashboard},{label:"Content",href:"/content",icon:FileText},{label:"Campaigns",href:"/campaigns",icon:Layers},{label:"Calendar",href:"/content?filter=scheduled",icon:CalendarDays}];
const manage=[{label:"Accounts",href:"/accounts",icon:Link2},{label:"Settings",href:"/settings",icon:Settings}];
function initials(value:string){return value.trim().slice(0,1).toUpperCase()||"S"}
export default function AppShell({children}:{children:React.ReactNode}){
 const path=usePathname(); const router=useRouter(); const [open,setOpen]=useState(false); const [brand,setBrand]=useState("Workspace"); const [username,setUsername]=useState<string|null>(null);
 useEffect(()=>{const token=sessionStorage.getItem("socialpilot_access_token");setUsername(getUsername()); if(!token){router.replace("/login");return;} getDashboardOverview(token).then(x=>setBrand(x.workspace.name||"Workspace")).catch(e=>{if(e instanceof ApiError&&e.status===401){clearAccessToken();router.replace("/login")}})},[router]);
 const active=(href:string)=>path===href||((href==="/content")&&path.startsWith("/content"));
 const signOut=()=>{clearAccessToken();router.replace("/login")};
 return <div className="app-shell"><aside className={`app-sidebar ${open?"open":""}`}><div className="sidebar-head"><Link href="/dashboard" className="brand"><BrandMark/><span>socialpilot</span></Link><button className="icon-button mobile-only" onClick={()=>setOpen(false)}><X size={18}/></button></div><div className="workspace-switch"><span className="workspace-avatar">{initials(brand)}</span><span><strong>{brand}</strong><small>Workspace</small></span><ChevronDown size={14}/></div><nav className="side-nav"><p>WORKSPACE</p>{nav.map(({label,href,icon:Icon})=><Link key={href} href={href} onClick={()=>setOpen(false)} className={active(href)?"active":""}><Icon size={17}/><span>{label}</span></Link>)}<p>MANAGE</p>{manage.map(({label,href,icon:Icon})=><Link key={href} href={href} onClick={()=>setOpen(false)} className={active(href)?"active":""}><Icon size={17}/><span>{label}</span></Link>)}</nav><div className="sidebar-bottom"><div className="profile-chip"><span className="profile-avatar">{initials(username||brand)}</span><span><strong>{username?`@${username}`:"Your profile"}</strong><small>{username?"Personal workspace":"Set a username in Settings"}</small></span></div><button className="signout" onClick={signOut}><LogOut size={16}/> Sign out</button></div></aside><div className="app-main"><header className="app-topbar"><button className="icon-button mobile-only" onClick={()=>setOpen(true)}><Menu size={20}/></button><div className="topbar-title">{path.startsWith("/content")?"Content":path.startsWith("/campaigns")?"Campaigns":path.startsWith("/accounts")?"Accounts":path.startsWith("/settings")?"Settings":"Overview"}</div><div className="topbar-actions"><Link className="topbar-link" href="/settings">Profile</Link><Link className="topbar-create" href="/campaigns">Create <span>+</span></Link></div></header><main className="app-content">{children}</main></div></div>
}
