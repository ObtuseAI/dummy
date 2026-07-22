import { useState } from 'react';
import { BrowserRouter, Routes, Route, Link, NavLink } from 'react-router-dom';
import { useStatus } from './hooks/useStatus';
import Home from './screens/Home';
import ModelPanel from './screens/ModelPanel';
import OperatorControl from './screens/OperatorControl';
import Markets from './screens/Markets';
import Forecasts from './screens/Forecasts';
import Strategies from './screens/Strategies';
import Orders from './screens/Orders';
import Positions from './screens/Positions';
import Risk from './screens/Risk';
import Logs from './screens/Logs';
import Proof from './screens/Proof';
import RepoHarvester from './screens/RepoHarvester';
import Adapters from './screens/Adapters';
import Kalshi from './screens/Kalshi';
import KalshiReal from './screens/KalshiReal';
import StrategyCandidates from './screens/StrategyCandidates';
import ProposedTrades from './screens/ProposedTrades';
import BlockedOrders from './screens/BlockedOrders';
import Firewall from './screens/Firewall';
import CapsExposure from './screens/CapsExposure';
import StrategyScan from './screens/StrategyScan';
import FirewallRehearsal from './screens/FirewallRehearsal';
import LiveSubmit from './screens/LiveSubmit';
import ArchivedStageView from '@dummy-archive-route';
import VNextObservatory from './VNextObservatory';

const ARCHIVE_SURFACE_ENABLED = import.meta.env.VITE_DUMMY_ARCHIVE_SURFACE === 'offline-dev';
const ARCHIVE_ONLY_LABELS = new Set(['Adapters', 'Strategy Scan', 'Proposed Trades']);
const links = ['Home','Model Panel','Operator Control','Markets','Forecasts','Strategies','Orders','Positions','Risk','Logs','Proof','Repo Harvester','Adapters','Kalshi','Kalshi Real','Strategy Candidates','Strategy Scan','Proposed Trades','Blocked Orders','Firewall','Firewall Rehearsal','Caps & Exposure','Live Submit','V6 Dashboard','V7 Dashboard','V8 Dashboard','V10 Dashboard','V11 Dashboard','V12 Dashboard','V13 Dashboard','V14 Dashboard','V15 Dashboard','V16 Dashboard','V17 Dashboard','V18 Dashboard','V19 Dashboard','V20 Dashboard','V21 Dashboard','V22 Dashboard','V23 Dashboard','V24 Dashboard','V25 Dashboard','V26 Dashboard','V27 Dashboard','V28 Dashboard','V29 Dashboard','V30 Dashboard','V31 Dashboard','V32 Dashboard','V33 Dashboard','V37 Dashboard','V38 Dashboard','V39 Dashboard','V40 Dashboard','V41 Dashboard','V42 Dashboard','V43 Dashboard','V44 Dashboard','V45 Dashboard','V46 Dashboard','V47 Dashboard','V48 Dashboard','V49 Dashboard','V50 Dashboard','V51 Dashboard','V52 Dashboard','V53 Dashboard','V54 Dashboard','V55 Dashboard','V56 Dashboard','V57 Dashboard','V58 Dashboard','V59 Dashboard','V60 Dashboard','V61 Dashboard','V62 Dashboard','V63 Dashboard','V64 Dashboard','V65 Dashboard','V66 Dashboard','V67 Dashboard','V68 Dashboard','V69 Dashboard','V70 Dashboard','V71 Dashboard','V72 Dashboard','V73 Dashboard','V74 Dashboard','V75 Dashboard','V76 Dashboard','V77 Dashboard','V78 Dashboard','V79 Dashboard','V80 Dashboard','V81 Dashboard','V82 Dashboard','V83 Dashboard','V84 Dashboard','V85 Dashboard','V86 Dashboard','V87 Dashboard','V88 Dashboard','V89 Dashboard','V90 Dashboard','V91 Dashboard','V92 Dashboard','V93 Dashboard','V94 Dashboard','V95 Dashboard','V96 Dashboard','V97 Dashboard','V98 Dashboard','V99 Dashboard','V100 Dashboard','V101 Dashboard','V102 Dashboard','V103 Dashboard','V104 Dashboard','V105 Dashboard','V106 Dashboard','V107 Dashboard','V108 Dashboard','V109 Dashboard','V110 Dashboard','V111 Dashboard','V112 Dashboard','V113 Dashboard','V114 Dashboard','V115 Dashboard','V116 Dashboard','V117 Dashboard','V118 Dashboard','V119 Dashboard','V120 Dashboard','V121 Dashboard','V122 Dashboard','V123 Dashboard','V124 Dashboard','V125 Dashboard','V126 Dashboard','V127 Dashboard','V128 Dashboard','V129 Dashboard','V130 Dashboard','V131 Dashboard','V132 Dashboard','V133 Dashboard','V134 Dashboard','V135 Dashboard','V136 Dashboard','V137 Dashboard','V138 Dashboard','V139 Dashboard','V140 Dashboard','V141 Dashboard','V142 Dashboard','V143 Dashboard','V144 Dashboard','V145 Dashboard','V146 Dashboard','V147 Dashboard','V148 Dashboard','V149 Dashboard','V150 Dashboard','V151 Dashboard','V152 Dashboard','V153 Dashboard','V154 Dashboard','V155 Dashboard','V156 Dashboard','V157 Dashboard','V158 Dashboard','V159 Dashboard','V160 Dashboard','V161 Dashboard','V162 Dashboard','V163 Dashboard','V164 Dashboard','V165 Dashboard','V166 Dashboard','V167 Dashboard','V168 Dashboard','V169 Dashboard','V170 Dashboard','V171 Dashboard','V172 Dashboard','V173 Dashboard','V174 Dashboard','V175 Dashboard','V176 Dashboard','V177 Dashboard','V178 Dashboard','V179 Dashboard','V180 Dashboard','V181 Dashboard','V182 Dashboard','V183 Dashboard','V184 Dashboard','V185 Dashboard','V186 Dashboard','V187 Dashboard','V188 Dashboard','V189 Dashboard','V190 Dashboard','V191 Dashboard','V192 Dashboard','V193 Dashboard','V194 Dashboard','V195 Dashboard','V196 Dashboard','V197 Dashboard','V198 Dashboard','V199 Dashboard','V200 Dashboard','V201 Dashboard','V202 Dashboard','V203 Dashboard','V204 Dashboard','V205 Dashboard','V206 Dashboard','V207 Dashboard','V208 Dashboard','V209 Dashboard','V210 Dashboard','V211 Dashboard','V212 Dashboard','V213 Dashboard','V214 Dashboard','V215 Dashboard','V216 Dashboard','V217 Dashboard','V218 Dashboard','V219 Dashboard','V220 Dashboard','V221 Dashboard','V222 Dashboard','V223 Dashboard','V224 Dashboard','V225 Dashboard','V226 Dashboard','V227 Dashboard','V228 Dashboard','V229 Dashboard','V230 Dashboard','V231 Dashboard','V232 Dashboard','V233 Dashboard','V234 Dashboard','V235 Dashboard','V236 Dashboard','V237 Dashboard','V238 Dashboard','V239 Dashboard','V240 Dashboard','V241 Dashboard','V242 Dashboard','V243 Dashboard','V244 Dashboard','V245 Dashboard','V246 Dashboard','V247 Dashboard','V248 Dashboard','V249 Dashboard','V250 Dashboard','V251 Dashboard','V252 Dashboard','V253 Dashboard','V254 Dashboard','V255 Dashboard','V256 Dashboard','V257 Dashboard','V258 Dashboard','V259 Dashboard','V260 Dashboard','V261 Dashboard','V262 Dashboard','V263 Dashboard','V264 Dashboard','V265 Dashboard','V266 Dashboard','V267 Dashboard','V268 Dashboard','V269 Dashboard','V270 Dashboard','V271 Dashboard','V272 Dashboard','V273 Dashboard','V274 Dashboard','V275 Dashboard','V276 Dashboard','V277 Dashboard','V278 Dashboard','V279 Dashboard','V280 Dashboard','V281 Dashboard','V282 Dashboard','V283 Dashboard','V284 Dashboard','V285 Dashboard','V286 Dashboard','V287 Dashboard','V288 Dashboard','V289 Dashboard','V290 Dashboard','V291 Dashboard','V292 Dashboard','V293 Dashboard','V294 Dashboard','V295 Dashboard','V296 Dashboard','V297 Dashboard','V298 Dashboard','V299 Dashboard','V300 Dashboard','V301 Dashboard','V302 Dashboard','V303 Dashboard','V304 Dashboard'];

function linkPath(label) {
  if (label === 'Home') return '/';
  if (label === 'Caps & Exposure') return '/caps-exposure';
  return `/${label.toLowerCase().replace(/ /g, '-')}`;
}

function NotFound() {
  return <div className="rounded bg-gray-800 p-6"><h1 className="text-2xl font-bold">Page not found</h1><p className="mt-2 text-gray-400">This dashboard route does not exist.</p><Link className="mt-4 inline-block text-blue-400" to="/">Return home</Link></div>;
}

function ArchiveDisabled() {
  return (
    <div className="rounded border border-amber-800 bg-amber-950/30 p-6">
      <h1 className="text-2xl font-bold text-amber-200">Historical stage archive is offline</h1>
      <p className="mt-2 text-sm text-gray-300">
        Production does not mount the V3–V304 archive. Use the explicit loopback-only
        offline development launcher when historical reports need to be inspected.
      </p>
    </div>
  );
}

function LegacyDashboardRoute(props) {
  return ARCHIVE_SURFACE_ENABLED ? <ArchivedStageView {...props} /> : <ArchiveDisabled />;
}

function ArchiveOnly({ children }) {
  return ARCHIVE_SURFACE_ENABLED ? children : <ArchiveDisabled />;
}

function DashboardNavigation({ mode }) {
  const [query, setQuery] = useState('');
  const isArchiveLink = label => /^V\d+ Dashboard$/.test(label) || ARCHIVE_ONLY_LABELS.has(label);
  const archiveLinks = links.filter(isArchiveLink);
  const primaryLinks = links.filter(label => !isArchiveLink(label));
  const filteredArchiveLinks = archiveLinks.filter(label => label.toLowerCase().includes(query.toLowerCase()));
  const navClass = ({ isActive }) => isActive
    ? 'rounded bg-blue-900 px-2 py-1 text-blue-100'
    : 'rounded px-2 py-1 hover:bg-gray-800 hover:text-blue-300';

  return (
    <header className="border-b border-gray-700 bg-gray-950">
      <div className="flex items-center justify-between gap-4 border-b border-gray-800 px-4 py-2 text-sm">
        <span className="font-semibold text-cyan-300">Dummy operator dashboard</span>
        <span className={`rounded px-3 py-1 font-semibold ${mode === 'AUTONOMOUS_LIVE_CAPPED' ? 'bg-red-900 text-red-100' : 'bg-gray-800 text-amber-200'}`}>
          Mode: {mode}
        </span>
      </div>
      <nav className="flex flex-wrap gap-1 p-3 text-sm">
        <NavLink to="/vnext-observatory" className={navClass}>vNext Observatory</NavLink>
        {primaryLinks.map(label => <NavLink key={label} to={linkPath(label)} className={navClass}>{label}</NavLink>)}
      </nav>
      {ARCHIVE_SURFACE_ENABLED && <details className="border-t border-gray-800 px-4 py-2">
        <summary className="cursor-pointer text-sm font-semibold text-gray-300">Stage Archive ({archiveLinks.length})</summary>
        <input
          className="my-3 w-full max-w-sm rounded border border-gray-700 bg-gray-900 px-3 py-2 text-sm"
          placeholder="Search archived stage dashboards"
          value={query}
          onChange={event => setQuery(event.target.value)}
        />
        <div className="flex max-h-48 flex-wrap gap-1 overflow-y-auto pb-2 text-xs">
          {filteredArchiveLinks.map(label => <NavLink key={label} to={linkPath(label)} className={navClass}>{label}</NavLink>)}
        </div>
      </details>}
    </header>
  );
}

export default function App() {
  const status = useStatus();
  const mode = status?.account_mode || status?.mode || 'UNKNOWN';
  return (
    <BrowserRouter>
      <div className="min-h-screen bg-gray-900 text-gray-100">
        <DashboardNavigation mode={mode} />
        <main className="p-4">
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/model-panel" element={<ModelPanel />} />
            <Route path="/operator-control" element={<OperatorControl />} />
            <Route path="/markets" element={<Markets />} />
            <Route path="/forecasts" element={<Forecasts />} />
            <Route path="/strategies" element={<Strategies />} />
            <Route path="/orders" element={<Orders />} />
            <Route path="/positions" element={<Positions />} />
            <Route path="/risk" element={<Risk />} />
            <Route path="/logs" element={<Logs />} />
            <Route path="/proof" element={<Proof />} />
            <Route path="/repo-harvester" element={<RepoHarvester />} />
            <Route path="/adapters" element={<ArchiveOnly><Adapters /></ArchiveOnly>} />
            <Route path="/kalshi" element={<Kalshi />} />
            <Route path="/kalshi-real" element={<KalshiReal />} />
            <Route path="/strategy-candidates" element={<StrategyCandidates />} />
            <Route path="/strategy-scan" element={<ArchiveOnly><StrategyScan /></ArchiveOnly>} />
            <Route path="/proposed-trades" element={<ArchiveOnly><ProposedTrades /></ArchiveOnly>} />
            <Route path="/blocked-orders" element={<BlockedOrders />} />
            <Route path="/firewall" element={<Firewall />} />
            <Route path="/firewall-rehearsal" element={<FirewallRehearsal />} />
            <Route path="/caps-exposure" element={<CapsExposure />} />
            <Route path="/live-submit" element={<LiveSubmit />} />
            <Route path="/vnext-observatory" element={<VNextObservatory />} />
            <Route path="/v6-dashboard" element={<LegacyDashboardRoute version={6} />} />
            <Route path="/v7-dashboard" element={<LegacyDashboardRoute version={7} />} />
            <Route path="/v8-dashboard" element={<LegacyDashboardRoute version={8} />} />
            <Route path="/v10-dashboard" element={<LegacyDashboardRoute version={10} />} />
            <Route path="/v11-dashboard" element={<LegacyDashboardRoute version={11} />} />
            <Route path="/v12-dashboard" element={<LegacyDashboardRoute version={12} />} />
            <Route path="/v13-dashboard" element={<LegacyDashboardRoute version={13} />} />
            <Route path="/v14-dashboard" element={<LegacyDashboardRoute version={14} />} />
            <Route path="/v15-dashboard" element={<LegacyDashboardRoute version={15} />} />
            <Route path="/v16-dashboard" element={<LegacyDashboardRoute version={16} />} />
            <Route path="/v17-dashboard" element={<LegacyDashboardRoute version={17} />} />
            <Route path="/v18-dashboard" element={<LegacyDashboardRoute version={18} />} />
            <Route path="/v19-dashboard" element={<LegacyDashboardRoute version={19} />} />
            <Route path="/v20-dashboard" element={<LegacyDashboardRoute version={20} />} />
            <Route path="/v21-dashboard" element={<LegacyDashboardRoute version={21} />} />
            <Route path="/v22-dashboard" element={<LegacyDashboardRoute version={22} />} />
            <Route path="/v23-dashboard" element={<LegacyDashboardRoute version={23} />} />
            <Route path="/v24-dashboard" element={<LegacyDashboardRoute version={24} />} />
            <Route path="/v25-dashboard" element={<LegacyDashboardRoute version={25} />} />
            <Route path="/v26-dashboard" element={<LegacyDashboardRoute version={26} />} />
            <Route path="/v27-dashboard" element={<LegacyDashboardRoute version={27} />} />
            <Route path="/v28-dashboard" element={<LegacyDashboardRoute version={28} />} />
            <Route path="/v29-dashboard" element={<LegacyDashboardRoute version={29} />} />
            <Route path="/v30-dashboard" element={<LegacyDashboardRoute version={30} />} />
            <Route path="/v31-dashboard" element={<LegacyDashboardRoute version={31} />} />
            <Route path="/v32-dashboard" element={<LegacyDashboardRoute version={32} />} />
            <Route path="/v33-dashboard" element={<LegacyDashboardRoute version={33} />} />
            <Route path="/v37-dashboard" element={<LegacyDashboardRoute version={37} />} />
            <Route path="/v38-dashboard" element={<LegacyDashboardRoute version={38} />} />
            <Route path="/v39-dashboard" element={<LegacyDashboardRoute version={39} />} />
            <Route path="/v40-dashboard" element={<LegacyDashboardRoute version={40} />} />
            <Route path="/v41-dashboard" element={<LegacyDashboardRoute version={41} />} />
            <Route path="/v42-dashboard" element={<LegacyDashboardRoute version={42} />} />
            <Route path="/v43-dashboard" element={<LegacyDashboardRoute version={43} />} />
            <Route path="/v44-dashboard" element={<LegacyDashboardRoute version={44} />} />
            <Route path="/v45-dashboard" element={<LegacyDashboardRoute version={45} />} />
            <Route path="/v46-dashboard" element={<LegacyDashboardRoute version={46} />} />
            <Route path="/v47-dashboard" element={<LegacyDashboardRoute version={47} />} />
            <Route path="/v48-dashboard" element={<LegacyDashboardRoute version={48} />} />
            <Route path="/v49-dashboard" element={<LegacyDashboardRoute version={49} />} />
            <Route path="/v50-dashboard" element={<LegacyDashboardRoute version={50} />} />
            <Route path="/v51-dashboard" element={<LegacyDashboardRoute version={51} />} />
            <Route path="/v52-dashboard" element={<LegacyDashboardRoute version={52} />} />
            <Route path="/v53-dashboard" element={<LegacyDashboardRoute version={53} />} />
            <Route path="/v54-dashboard" element={<LegacyDashboardRoute version={54} />} />
            <Route path="/v55-dashboard" element={<LegacyDashboardRoute version={55} />} />
            <Route path="/v56-dashboard" element={<LegacyDashboardRoute version={56} />} />
            <Route path="/v57-dashboard" element={<LegacyDashboardRoute version={57} />} />
            <Route path="/v58-dashboard" element={<LegacyDashboardRoute version={58} />} />
            <Route path="/v59-dashboard" element={<LegacyDashboardRoute version={59} />} />
            <Route path="/v60-dashboard" element={<LegacyDashboardRoute version={60} />} />
            <Route path="/v61-dashboard" element={<LegacyDashboardRoute version={61} />} />
            <Route path="/v62-dashboard" element={<LegacyDashboardRoute version={62} />} />
            <Route path="/v63-dashboard" element={<LegacyDashboardRoute version={63} />} />
            <Route path="/v64-dashboard" element={<LegacyDashboardRoute version={64} />} />
            <Route path="/v65-dashboard" element={<LegacyDashboardRoute version={65} />} />
            <Route path="/v66-dashboard" element={<LegacyDashboardRoute version={66} />} />
            <Route path="/v67-dashboard" element={<LegacyDashboardRoute version={67} />} />
            <Route path="/v68-dashboard" element={<LegacyDashboardRoute version={68} />} />
            <Route path="/v69-dashboard" element={<LegacyDashboardRoute version={69} />} />
            <Route path="/v70-dashboard" element={<LegacyDashboardRoute version={70} />} />
            <Route path="/v71-dashboard" element={<LegacyDashboardRoute version={71} />} />
            <Route path="/v72-dashboard" element={<LegacyDashboardRoute version={72} />} />
            <Route path="/v73-dashboard" element={<LegacyDashboardRoute version={73} />} />
            <Route path="/v74-dashboard" element={<LegacyDashboardRoute version={74} />} />
            <Route path="/v75-dashboard" element={<LegacyDashboardRoute version={75} />} />
            <Route path="/v76-dashboard" element={<LegacyDashboardRoute version={76} />} />
            <Route path="/v77-dashboard" element={<LegacyDashboardRoute version={77} />} />
            <Route path="/v78-dashboard" element={<LegacyDashboardRoute version={78} />} />
            <Route path="/v79-dashboard" element={<LegacyDashboardRoute version={79} />} />
            <Route path="/v80-dashboard" element={<LegacyDashboardRoute version={80} />} />
            <Route path="/v81-dashboard" element={<LegacyDashboardRoute version={81} />} />
            <Route path="/v82-dashboard" element={<LegacyDashboardRoute version={82} />} />
            <Route path="/v83-dashboard" element={<LegacyDashboardRoute version={83} />} />
            <Route path="/v84-dashboard" element={<LegacyDashboardRoute version={84} />} />
            <Route path="/v85-dashboard" element={<LegacyDashboardRoute version={85} />} />
            <Route path="/v86-dashboard" element={<LegacyDashboardRoute version={86} />} />
            <Route path="/v87-dashboard" element={<LegacyDashboardRoute version={87} />} />
            <Route path="/v88-dashboard" element={<LegacyDashboardRoute version={88} />} />
            <Route path="/v89-dashboard" element={<LegacyDashboardRoute version={89} />} />
            <Route path="/v90-dashboard" element={<LegacyDashboardRoute version={90} />} />
            <Route path="/v91-dashboard" element={<LegacyDashboardRoute version={91} />} />
            <Route path="/v92-dashboard" element={<LegacyDashboardRoute version={92} />} />
            <Route path="/v93-dashboard" element={<LegacyDashboardRoute version={93} />} />
            <Route path="/v94-dashboard" element={<LegacyDashboardRoute version={94} />} />
            <Route path="/v95-dashboard" element={<LegacyDashboardRoute version={95} />} />
            <Route path="/v96-dashboard" element={<LegacyDashboardRoute version={96} />} />
            <Route path="/v97-dashboard" element={<LegacyDashboardRoute version={97} />} />
            <Route path="/v98-dashboard" element={<LegacyDashboardRoute version={98} />} />
            <Route path="/v99-dashboard" element={<LegacyDashboardRoute version={99} />} />
            <Route path="/v100-dashboard" element={<LegacyDashboardRoute version={100} />} />
            <Route path="/v101-dashboard" element={<LegacyDashboardRoute version={101} />} />
            <Route path="/v102-dashboard" element={<LegacyDashboardRoute version={102} />} />
            <Route path="/v103-dashboard" element={<LegacyDashboardRoute version={103} />} />
            <Route path="/v104-dashboard" element={<LegacyDashboardRoute version={104} />} />
            <Route path="/v105-dashboard" element={<LegacyDashboardRoute version={105} />} />
            <Route path="/v106-dashboard" element={<LegacyDashboardRoute version={106} />} />
            <Route path="/v107-dashboard" element={<LegacyDashboardRoute version={107} />} />
            <Route path="/v108-dashboard" element={<LegacyDashboardRoute version={108} />} />
            <Route path="/v109-dashboard" element={<LegacyDashboardRoute version={109} />} />
            <Route path="/v110-dashboard" element={<LegacyDashboardRoute version={110} />} />
            <Route path="/v111-dashboard" element={<LegacyDashboardRoute version={111} />} />
            <Route path="/v112-dashboard" element={<LegacyDashboardRoute version={112} />} />
            <Route path="/v113-dashboard" element={<LegacyDashboardRoute version={113} />} />
            <Route path="/v114-dashboard" element={<LegacyDashboardRoute version={114} />} />
            <Route path="/v115-dashboard" element={<LegacyDashboardRoute version={115} />} />
            <Route path="/v116-dashboard" element={<LegacyDashboardRoute version={116} />} />
            <Route path="/v117-dashboard" element={<LegacyDashboardRoute version={117} />} />
            <Route path="/v118-dashboard" element={<LegacyDashboardRoute version={118} />} />
            <Route path="/v119-dashboard" element={<LegacyDashboardRoute version={119} />} />
            <Route path="/v120-dashboard" element={<LegacyDashboardRoute version={120} />} />
            <Route path="/v121-dashboard" element={<LegacyDashboardRoute version={121} />} />
            <Route path="/v122-dashboard" element={<LegacyDashboardRoute version={122} />} />
            <Route path="/v123-dashboard" element={<LegacyDashboardRoute version={123} />} />
            <Route path="/v124-dashboard" element={<LegacyDashboardRoute version={124} />} />
            <Route path="/v125-dashboard" element={<LegacyDashboardRoute version={125} />} />
            <Route path="/v126-dashboard" element={<LegacyDashboardRoute version={126} />} />
            <Route path="/v127-dashboard" element={<LegacyDashboardRoute version={127} />} />
            <Route path="/v128-dashboard" element={<LegacyDashboardRoute version={128} />} />
            <Route path="/v129-dashboard" element={<LegacyDashboardRoute version={129} />} />
            <Route path="/v130-dashboard" element={<LegacyDashboardRoute version={130} />} />
            <Route path="/v131-dashboard" element={<LegacyDashboardRoute version={131} />} />
            <Route path="/v132-dashboard" element={<LegacyDashboardRoute version={132} />} />
            <Route path="/v133-dashboard" element={<LegacyDashboardRoute version={133} />} />
            <Route path="/v134-dashboard" element={<LegacyDashboardRoute version={134} />} />
            <Route path="/v135-dashboard" element={<LegacyDashboardRoute version={135} />} />
            <Route path="/v136-dashboard" element={<LegacyDashboardRoute version={136} />} />
            <Route path="/v137-dashboard" element={<LegacyDashboardRoute version={137} />} />
            <Route path="/v138-dashboard" element={<LegacyDashboardRoute version={138} />} />
            <Route path="/v139-dashboard" element={<LegacyDashboardRoute version={139} />} />
            <Route path="/v140-dashboard" element={<LegacyDashboardRoute version={140} />} />
            <Route path="/v141-dashboard" element={<LegacyDashboardRoute version={141} />} />
            <Route path="/v142-dashboard" element={<LegacyDashboardRoute version={142} />} />
            <Route path="/v143-dashboard" element={<LegacyDashboardRoute version={143} />} />
            <Route path="/v144-dashboard" element={<LegacyDashboardRoute version={144} />} />
            <Route path="/v145-dashboard" element={<LegacyDashboardRoute version={145} />} />
            <Route path="/v146-dashboard" element={<LegacyDashboardRoute version={146} />} />
            <Route path="/v147-dashboard" element={<LegacyDashboardRoute version={147} />} />
            <Route path="/v148-dashboard" element={<LegacyDashboardRoute version={148} />} />
            <Route path="/v149-dashboard" element={<LegacyDashboardRoute version={149} />} />
            <Route path="/v150-dashboard" element={<LegacyDashboardRoute version={150} />} />
            <Route path="/v151-dashboard" element={<LegacyDashboardRoute version={151} />} />
            <Route path="/v152-dashboard" element={<LegacyDashboardRoute version={152} />} />
            <Route path="/v153-dashboard" element={<LegacyDashboardRoute version={153} />} />
            <Route path="/v154-dashboard" element={<LegacyDashboardRoute version={154} />} />
            <Route path="/v155-dashboard" element={<LegacyDashboardRoute version={155} />} />
            <Route path="/v156-dashboard" element={<LegacyDashboardRoute version={156} />} />
            <Route path="/v157-dashboard" element={<LegacyDashboardRoute version={157} />} />
            <Route path="/v158-dashboard" element={<LegacyDashboardRoute version={158} />} />
            <Route path="/v159-dashboard" element={<LegacyDashboardRoute version={159} />} />
            <Route path="/v160-dashboard" element={<LegacyDashboardRoute version={160} />} />
            <Route path="/v161-dashboard" element={<LegacyDashboardRoute version={161} />} />
            <Route path="/v162-dashboard" element={<LegacyDashboardRoute version={162} />} />
            <Route path="/v163-dashboard" element={<LegacyDashboardRoute version={163} />} />
            <Route path="/v164-dashboard" element={<LegacyDashboardRoute version={164} />} />
            <Route path="/v165-dashboard" element={<LegacyDashboardRoute version={165} />} />
            <Route path="/v166-dashboard" element={<LegacyDashboardRoute version={166} />} />
            <Route path="/v167-dashboard" element={<LegacyDashboardRoute version={167} />} />
            <Route path="/v168-dashboard" element={<LegacyDashboardRoute version={168} />} />
            <Route path="/v169-dashboard" element={<LegacyDashboardRoute version={169} />} />
            <Route path="/v170-dashboard" element={<LegacyDashboardRoute version={170} />} />
            <Route path="/v171-dashboard" element={<LegacyDashboardRoute version={171} />} />
            <Route path="/v172-dashboard" element={<LegacyDashboardRoute version={172} />} />
            <Route path="/v173-dashboard" element={<LegacyDashboardRoute version={173} />} />
            <Route path="/v174-dashboard" element={<LegacyDashboardRoute version={174} />} />
            <Route path="/v175-dashboard" element={<LegacyDashboardRoute version={175} />} />
            <Route path="/v176-dashboard" element={<LegacyDashboardRoute version={176} />} />
            <Route path="/v177-dashboard" element={<LegacyDashboardRoute version={177} />} />
            <Route path="/v178-dashboard" element={<LegacyDashboardRoute version={178} />} />
            <Route path="/v179-dashboard" element={<LegacyDashboardRoute version={179} />} />
            <Route path="/v180-dashboard" element={<LegacyDashboardRoute version={180} />} />
            <Route path="/v181-dashboard" element={<LegacyDashboardRoute version={181} />} />
            <Route path="/v182-dashboard" element={<LegacyDashboardRoute version={182} />} />
            <Route path="/v183-dashboard" element={<LegacyDashboardRoute version={183} />} />
            <Route path="/v184-dashboard" element={<LegacyDashboardRoute version={184} />} />
            <Route path="/v185-dashboard" element={<LegacyDashboardRoute version={185} />} />
            <Route path="/v186-dashboard" element={<LegacyDashboardRoute version={186} />} />
            <Route path="/v187-dashboard" element={<LegacyDashboardRoute version={187} />} />
            <Route path="/v188-dashboard" element={<LegacyDashboardRoute version={188} />} />
            <Route path="/v189-dashboard" element={<LegacyDashboardRoute version={189} />} />
            <Route path="/v190-dashboard" element={<LegacyDashboardRoute version={190} />} />
            <Route path="/v191-dashboard" element={<LegacyDashboardRoute version={191} />} />
            <Route path="/v192-dashboard" element={<LegacyDashboardRoute version={192} />} />
            <Route path="/v193-dashboard" element={<LegacyDashboardRoute version={193} />} />
            <Route path="/v194-dashboard" element={<LegacyDashboardRoute version={194} />} />
            <Route path="/v195-dashboard" element={<LegacyDashboardRoute version={195} />} />
            <Route path="/v196-dashboard" element={<LegacyDashboardRoute version={196} />} />
            <Route path="/v197-dashboard" element={<LegacyDashboardRoute version={197} />} />
            <Route path="/v198-dashboard" element={<LegacyDashboardRoute version={198} />} />
            <Route path="/v199-dashboard" element={<LegacyDashboardRoute version={199} />} />
            <Route path="/v200-dashboard" element={<LegacyDashboardRoute version={200} />} />
            <Route path="/v201-dashboard" element={<LegacyDashboardRoute version={201} />} />
            <Route path="/v202-dashboard" element={<LegacyDashboardRoute version={202} />} />
            <Route path="/v203-dashboard" element={<LegacyDashboardRoute version={203} />} />
            <Route path="/v204-dashboard" element={<LegacyDashboardRoute version={204} />} />
            <Route path="/v205-dashboard" element={<LegacyDashboardRoute version={205} />} />
            <Route path="/v206-dashboard" element={<LegacyDashboardRoute version={206} />} />
            <Route path="/v207-dashboard" element={<LegacyDashboardRoute version={207} />} />
            <Route path="/v208-dashboard" element={<LegacyDashboardRoute version={208} />} />
            <Route path="/v209-dashboard" element={<LegacyDashboardRoute version={209} />} />
            <Route path="/v210-dashboard" element={<LegacyDashboardRoute version={210} />} />
            <Route path="/v211-dashboard" element={<LegacyDashboardRoute version={211} />} />
            <Route path="/v212-dashboard" element={<LegacyDashboardRoute version={212} />} />
            <Route path="/v213-dashboard" element={<LegacyDashboardRoute version={213} />} />
            <Route path="/v214-dashboard" element={<LegacyDashboardRoute version={214} />} />
            <Route path="/v215-dashboard" element={<LegacyDashboardRoute version={215} />} />
            <Route path="/v216-dashboard" element={<LegacyDashboardRoute version={216} />} />
            <Route path="/v217-dashboard" element={<LegacyDashboardRoute version={217} />} />
            <Route path="/v218-dashboard" element={<LegacyDashboardRoute version={218} />} />
            <Route path="/v219-dashboard" element={<LegacyDashboardRoute version={219} />} />
            <Route path="/v220-dashboard" element={<LegacyDashboardRoute version={220} />} />
            <Route path="/v221-dashboard" element={<LegacyDashboardRoute version={221} />} />
            <Route path="/v222-dashboard" element={<LegacyDashboardRoute version={222} />} />
            <Route path="/v223-dashboard" element={<LegacyDashboardRoute version={223} />} />
            <Route path="/v224-dashboard" element={<LegacyDashboardRoute version={224} />} />
            <Route path="/v225-dashboard" element={<LegacyDashboardRoute version={225} />} />
            <Route path="/v226-dashboard" element={<LegacyDashboardRoute version={226} />} />
            <Route path="/v227-dashboard" element={<LegacyDashboardRoute version={227} />} />
            <Route path="/v228-dashboard" element={<LegacyDashboardRoute version={228} />} />
            <Route path="/v229-dashboard" element={<LegacyDashboardRoute version={229} />} />
            <Route path="/v230-dashboard" element={<LegacyDashboardRoute version={230} />} />
            <Route path="/v231-dashboard" element={<LegacyDashboardRoute version={231} />} />
            <Route path="/v232-dashboard" element={<LegacyDashboardRoute version={232} />} />
            <Route path="/v233-dashboard" element={<LegacyDashboardRoute version={233} />} />
            <Route path="/v234-dashboard" element={<LegacyDashboardRoute version={234} />} />
            <Route path="/v235-dashboard" element={<LegacyDashboardRoute version={235} />} />
            <Route path="/v236-dashboard" element={<LegacyDashboardRoute version={236} />} />
            <Route path="/v237-dashboard" element={<LegacyDashboardRoute version={237} />} />
            <Route path="/v238-dashboard" element={<LegacyDashboardRoute version={238} />} />
            <Route path="/v239-dashboard" element={<LegacyDashboardRoute version={239} />} />
            <Route path="/v240-dashboard" element={<LegacyDashboardRoute version={240} />} />
            <Route path="/v241-dashboard" element={<LegacyDashboardRoute version={241} />} />
            <Route path="/v242-dashboard" element={<LegacyDashboardRoute version={242} />} />
            <Route path="/v243-dashboard" element={<LegacyDashboardRoute version={243} />} />
            <Route path="/v244-dashboard" element={<LegacyDashboardRoute version={244} />} />
            <Route path="/v245-dashboard" element={<LegacyDashboardRoute version={245} />} />
            <Route path="/v246-dashboard" element={<LegacyDashboardRoute version={246} />} />
            <Route path="/v247-dashboard" element={<LegacyDashboardRoute version={247} />} />
            <Route path="/v248-dashboard" element={<LegacyDashboardRoute version={248} />} />
            <Route path="/v249-dashboard" element={<LegacyDashboardRoute version={249} />} />
            <Route path="/v250-dashboard" element={<LegacyDashboardRoute version={250} />} />
            <Route path="/v251-dashboard" element={<LegacyDashboardRoute version={251} />} />
            <Route path="/v252-dashboard" element={<LegacyDashboardRoute version={252} />} />
            <Route path="/v253-dashboard" element={<LegacyDashboardRoute version={253} />} />
            <Route path="/v254-dashboard" element={<LegacyDashboardRoute version={254} />} />
            <Route path="/v255-dashboard" element={<LegacyDashboardRoute version={255} />} />
            <Route path="/v256-dashboard" element={<LegacyDashboardRoute version={256} />} />
            <Route path="/v257-dashboard" element={<LegacyDashboardRoute version={257} />} />
            <Route path="/v258-dashboard" element={<LegacyDashboardRoute version={258} />} />
            <Route path="/v259-dashboard" element={<LegacyDashboardRoute version={259} />} />
            <Route path="/v260-dashboard" element={<LegacyDashboardRoute version={260} />} />
            <Route path="/v261-dashboard" element={<LegacyDashboardRoute version={261} />} />
            <Route path="/v262-dashboard" element={<LegacyDashboardRoute version={262} />} />
            <Route path="/v263-dashboard" element={<LegacyDashboardRoute version={263} />} />
            <Route path="/v264-dashboard" element={<LegacyDashboardRoute version={264} />} />
            <Route path="/v265-dashboard" element={<LegacyDashboardRoute version={265} />} />
            <Route path="/v266-dashboard" element={<LegacyDashboardRoute version={266} />} />
            <Route path="/v267-dashboard" element={<LegacyDashboardRoute version={267} />} />
            <Route path="/v268-dashboard" element={<LegacyDashboardRoute version={268} />} />
            <Route path="/v269-dashboard" element={<LegacyDashboardRoute version={269} />} />
            <Route path="/v270-dashboard" element={<LegacyDashboardRoute version={270} />} />
            <Route path="/v271-dashboard" element={<LegacyDashboardRoute version={271} />} />
            <Route path="/v272-dashboard" element={<LegacyDashboardRoute version={272} />} />
            <Route path="/v273-dashboard" element={<LegacyDashboardRoute version={273} />} />
            <Route path="/v274-dashboard" element={<LegacyDashboardRoute version={274} />} />
            <Route path="/v275-dashboard" element={<LegacyDashboardRoute version={275} />} />
            <Route path="/v276-dashboard" element={<LegacyDashboardRoute version={276} />} />
            <Route path="/v277-dashboard" element={<LegacyDashboardRoute version={277} />} />
            <Route path="/v278-dashboard" element={<LegacyDashboardRoute version={278} />} />
            <Route path="/v279-dashboard" element={<LegacyDashboardRoute version={279} />} />
            <Route path="/v280-dashboard" element={<LegacyDashboardRoute version={280} />} />
            <Route path="/v281-dashboard" element={<LegacyDashboardRoute version={281} />} />
            <Route path="/v282-dashboard" element={<LegacyDashboardRoute version={282} />} />
            <Route path="/v283-dashboard" element={<LegacyDashboardRoute version={283} />} />
            <Route path="/v284-dashboard" element={<LegacyDashboardRoute version={284} />} />
            <Route path="/v285-dashboard" element={<LegacyDashboardRoute version={285} />} />
            <Route path="/v286-dashboard" element={<LegacyDashboardRoute version={286} />} />
            <Route path="/v287-dashboard" element={<LegacyDashboardRoute version={287} />} />
            <Route path="/v288-dashboard" element={<LegacyDashboardRoute version={288} />} />
            <Route path="/v289-dashboard" element={<LegacyDashboardRoute version={289} />} />
            <Route path="/v290-dashboard" element={<LegacyDashboardRoute version={290} />} />
            <Route path="/v291-dashboard" element={<LegacyDashboardRoute version={291} />} />
            <Route path="/v292-dashboard" element={<LegacyDashboardRoute version={292} />} />
            <Route path="/v293-dashboard" element={<LegacyDashboardRoute version={293} />} />
            <Route path="/v294-dashboard" element={<LegacyDashboardRoute version={294} />} />
            <Route path="/v295-dashboard" element={<LegacyDashboardRoute version={295} />} />
            <Route path="/v296-dashboard" element={<LegacyDashboardRoute version={296} />} />
            <Route path="/v297-dashboard" element={<LegacyDashboardRoute version={297} />} />
            <Route path="/v298-dashboard" element={<LegacyDashboardRoute version={298} />} />
            <Route path="/v299-dashboard" element={<LegacyDashboardRoute version={299} />} />
            <Route path="/v300-dashboard" element={<LegacyDashboardRoute version={300} />} />
            <Route path="/v301-dashboard" element={<LegacyDashboardRoute version={301} />} />
            <Route path="/v302-dashboard" element={<LegacyDashboardRoute version={302} />} />
            <Route path="/v303-dashboard" element={<LegacyDashboardRoute version={303} />} />
            <Route path="/v304-dashboard" element={<LegacyDashboardRoute version={304} />} />
            <Route path="*" element={<NotFound />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}
