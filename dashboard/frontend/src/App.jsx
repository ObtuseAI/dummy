import { BrowserRouter, Routes, Route, Link } from 'react-router-dom';
import Home from './screens/Home';
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
import V6Dashboard from './screens/V6Dashboard';
import V7Dashboard from './screens/V7Dashboard';
import V8Dashboard from './V8Dashboard';
import V10Dashboard from './V10Dashboard';
import V11Dashboard from './V11Dashboard';
import V12Dashboard from './V12Dashboard';
import V13Dashboard from './V13Dashboard';
import V14Dashboard from './V14Dashboard';
import V15Dashboard from './V15Dashboard';
import V16Dashboard from './V16Dashboard';
import V17Dashboard from './V17Dashboard';
import V18Dashboard from './V18Dashboard';
import V19Dashboard from './V19Dashboard';
import V20Dashboard from './V20Dashboard';
import V21Dashboard from './V21Dashboard';
import V22Dashboard from './V22Dashboard';
import V23Dashboard from './V23Dashboard';
import V24Dashboard from './V24Dashboard';
import V25Dashboard from './V25Dashboard';
import V26Dashboard from './V26Dashboard';
import V27Dashboard from './V27Dashboard';
import V28Dashboard from './V28Dashboard';
import V29Dashboard from './V29Dashboard';
import V30Dashboard from './V30Dashboard';
import V31Dashboard from './V31Dashboard';
import V32Dashboard from './V32Dashboard';
import V33Dashboard from './V33Dashboard';
import V37Dashboard from './V37Dashboard';
import V38Dashboard from './V38Dashboard';
import V39Dashboard from './V39Dashboard';
import V40Dashboard from './V40Dashboard';
import V41Dashboard from './V41Dashboard';
import V42Dashboard from './V42Dashboard';
import V43Dashboard from './V43Dashboard';
import V44Dashboard from './V44Dashboard';
import V45Dashboard from './V45Dashboard';
import V46Dashboard from './V46Dashboard';
import V47Dashboard from './V47Dashboard';
import V48Dashboard from './V48Dashboard';
import V49Dashboard from './V49Dashboard';
import V50Dashboard from './V50Dashboard';
import V51Dashboard from './V51Dashboard';
import V52Dashboard from './V52Dashboard';
import V53Dashboard from './V53Dashboard';
import V54Dashboard from './V54Dashboard';
import V55Dashboard from './V55Dashboard';
import V56Dashboard from './V56Dashboard';
import V57Dashboard from './V57Dashboard';
import V58Dashboard from './V58Dashboard';
import V59Dashboard from './V59Dashboard';
import V60Dashboard from './V60Dashboard';
import V61Dashboard from './V61Dashboard';
import V62Dashboard from './V62Dashboard';
import V63Dashboard from './V63Dashboard';
import V64Dashboard from './V64Dashboard';
import V65Dashboard from './V65Dashboard';
import V66Dashboard from './V66Dashboard';
import V67Dashboard from './V67Dashboard';
import V68Dashboard from './V68Dashboard';
import V69Dashboard from './V69Dashboard';
import V70Dashboard from './V70Dashboard';
import V71Dashboard from './V71Dashboard';
import V72Dashboard from './V72Dashboard';
import V73Dashboard from './V73Dashboard';
import V74Dashboard from './V74Dashboard';
import V75Dashboard from './V75Dashboard';
import V76Dashboard from './V76Dashboard';
import V77Dashboard from './V77Dashboard';
import V78Dashboard from './V78Dashboard';
import V79Dashboard from './V79Dashboard';
import V80Dashboard from './V80Dashboard';
import V81Dashboard from './V81Dashboard';
import V82Dashboard from './V82Dashboard';
import V83Dashboard from './V83Dashboard';
import V84Dashboard from './V84Dashboard';
import V85Dashboard from './V85Dashboard';
import V86Dashboard from './V86Dashboard';
import V87Dashboard from './V87Dashboard';
import V88Dashboard from './V88Dashboard';
import V89Dashboard from './V89Dashboard';
import V90Dashboard from './V90Dashboard';
import V91Dashboard from './V91Dashboard';
import V92Dashboard from './V92Dashboard';
import V93Dashboard from './V93Dashboard';
import V94Dashboard from './V94Dashboard';
import V95Dashboard from './V95Dashboard';
import V96Dashboard from './V96Dashboard';
import V97Dashboard from './V97Dashboard';
import V98Dashboard from './V98Dashboard';
import V99Dashboard from './V99Dashboard';
import V100Dashboard from './V100Dashboard';
import V101Dashboard from './V101Dashboard';
import V102Dashboard from './V102Dashboard';
import V103Dashboard from './V103Dashboard';
import V104Dashboard from './V104Dashboard';
import V105Dashboard from './V105Dashboard';
import V106Dashboard from './V106Dashboard';
import V107Dashboard from './V107Dashboard';
import V108Dashboard from './V108Dashboard';
import V109Dashboard from './V109Dashboard';
import V110Dashboard from './V110Dashboard';
import V111Dashboard from './V111Dashboard';
import V112Dashboard from './V112Dashboard';
import V113Dashboard from './V113Dashboard';
import V114Dashboard from './V114Dashboard';
import V115Dashboard from './V115Dashboard';
import V116Dashboard from './V116Dashboard';
import V117Dashboard from './V117Dashboard';
import V118Dashboard from './V118Dashboard';
import V119Dashboard from './V119Dashboard';
import V120Dashboard from './V120Dashboard';
import V121Dashboard from './V121Dashboard';
import V122Dashboard from './V122Dashboard';
import V123Dashboard from './V123Dashboard';
import V124Dashboard from './V124Dashboard';
import V125Dashboard from './V125Dashboard';
import V126Dashboard from './V126Dashboard';
import V127Dashboard from './V127Dashboard';
import V128Dashboard from './V128Dashboard';
import V129Dashboard from './V129Dashboard';
import V130Dashboard from './V130Dashboard';
import V131Dashboard from './V131Dashboard';
import V132Dashboard from './V132Dashboard';
import V133Dashboard from './V133Dashboard';
import V134Dashboard from './V134Dashboard';
import V135Dashboard from './V135Dashboard';
import V136Dashboard from './V136Dashboard';
import V137Dashboard from './V137Dashboard';
import V138Dashboard from './V138Dashboard';
import V139Dashboard from './V139Dashboard';
import V140Dashboard from './V140Dashboard';
import V141Dashboard from './V141Dashboard';
import V142Dashboard from './V142Dashboard';
import V143Dashboard from './V143Dashboard';
import V144Dashboard from './V144Dashboard';
import V145Dashboard from './V145Dashboard';
import V146Dashboard from './V146Dashboard';
import V147Dashboard from './V147Dashboard';
import V148Dashboard from './V148Dashboard';
import V149Dashboard from './V149Dashboard';
import V150Dashboard from './V150Dashboard';
import V151Dashboard from './V151Dashboard';
import V152Dashboard from './V152Dashboard';
import V153Dashboard from './V153Dashboard';
import V154Dashboard from './V154Dashboard';
import V155Dashboard from './V155Dashboard';
import V156Dashboard from './V156Dashboard';
import V157Dashboard from './V157Dashboard';
import V158Dashboard from './V158Dashboard';
import V159Dashboard from './V159Dashboard';
import V160Dashboard from './V160Dashboard';
import V161Dashboard from './V161Dashboard';
import V162Dashboard from './V162Dashboard';
import V163Dashboard from './V163Dashboard';
import V164Dashboard from './V164Dashboard';
import V165Dashboard from './V165Dashboard';
import V166Dashboard from './V166Dashboard';
import V167Dashboard from './V167Dashboard';
import V168Dashboard from './V168Dashboard';
import V169Dashboard from './V169Dashboard';
import V170Dashboard from './V170Dashboard';
import V171Dashboard from './V171Dashboard';
import V172Dashboard from './V172Dashboard';
import V173Dashboard from './V173Dashboard';
import V174Dashboard from './V174Dashboard';
import V175Dashboard from './V175Dashboard';
import V176Dashboard from './V176Dashboard';
import V177Dashboard from './V177Dashboard';
import V178Dashboard from './V178Dashboard';
import V179Dashboard from './V179Dashboard';
import V180Dashboard from './V180Dashboard';
import V181Dashboard from './V181Dashboard';
import V182Dashboard from './V182Dashboard';
import V183Dashboard from './V183Dashboard';
import V184Dashboard from './V184Dashboard';
import V185Dashboard from './V185Dashboard';
import V186Dashboard from './V186Dashboard';
import V187Dashboard from './V187Dashboard';
import V188Dashboard from './V188Dashboard';
import V189Dashboard from './V189Dashboard';
import V190Dashboard from './V190Dashboard';
import V191Dashboard from './V191Dashboard';
import V192Dashboard from './V192Dashboard';
import V193Dashboard from './V193Dashboard';
import V194Dashboard from './V194Dashboard';
import V195Dashboard from './V195Dashboard';
import V196Dashboard from './V196Dashboard';
import V197Dashboard from './V197Dashboard';
import V198Dashboard from './V198Dashboard';
import V199Dashboard from './V199Dashboard';
import V200Dashboard from './V200Dashboard';
import V201Dashboard from './V201Dashboard';
import V202Dashboard from './V202Dashboard';
import V203Dashboard from './V203Dashboard';
import V204Dashboard from './V204Dashboard';
import V205Dashboard from './V205Dashboard';
import V206Dashboard from './V206Dashboard';
import V207Dashboard from './V207Dashboard';
import V208Dashboard from './V208Dashboard';
import V209Dashboard from './V209Dashboard';
import V210Dashboard from './V210Dashboard';
import V211Dashboard from './V211Dashboard';
import V212Dashboard from './V212Dashboard';
import V213Dashboard from './V213Dashboard';
import V214Dashboard from './V214Dashboard';
import V215Dashboard from './V215Dashboard';
import V216Dashboard from './V216Dashboard';
import V217Dashboard from './V217Dashboard';
import V218Dashboard from './V218Dashboard';
import V219Dashboard from './V219Dashboard';
import V220Dashboard from './V220Dashboard';
import V221Dashboard from './V221Dashboard';
import V222Dashboard from './V222Dashboard';
import V223Dashboard from './V223Dashboard';
import V224Dashboard from './V224Dashboard';
import V225Dashboard from './V225Dashboard';
import V226Dashboard from './V226Dashboard';
import V227Dashboard from './V227Dashboard';
import V228Dashboard from './V228Dashboard';
import V229Dashboard from './V229Dashboard';
import V230Dashboard from './V230Dashboard';
import V231Dashboard from './V231Dashboard';
import V232Dashboard from './V232Dashboard';
import V233Dashboard from './V233Dashboard';
import V234Dashboard from './V234Dashboard';
import V235Dashboard from './V235Dashboard';
import V236Dashboard from './V236Dashboard';
import V237Dashboard from './V237Dashboard';
import V238Dashboard from './V238Dashboard';
import V239Dashboard from './V239Dashboard';
import V240Dashboard from './V240Dashboard';
import V241Dashboard from './V241Dashboard';
import V242Dashboard from './V242Dashboard';
import V243Dashboard from './V243Dashboard';
import V244Dashboard from './V244Dashboard';
import V245Dashboard from './V245Dashboard';
import V246Dashboard from './V246Dashboard';
import V247Dashboard from './V247Dashboard';
import V248Dashboard from './V248Dashboard';
import V249Dashboard from './V249Dashboard';
import V250Dashboard from './V250Dashboard';
import V251Dashboard from './V251Dashboard';
import V252Dashboard from './V252Dashboard';
import V253Dashboard from './V253Dashboard';
import V254Dashboard from './V254Dashboard';
import V255Dashboard from './V255Dashboard';
import V256Dashboard from './V256Dashboard';
import V257Dashboard from './V257Dashboard';
import V258Dashboard from './V258Dashboard';
import V259Dashboard from './V259Dashboard';
import V260Dashboard from './V260Dashboard';
import V261Dashboard from './V261Dashboard';
import V262Dashboard from './V262Dashboard';
import V263Dashboard from './V263Dashboard';
import V264Dashboard from './V264Dashboard';
import V265Dashboard from './V265Dashboard';
import V266Dashboard from './V266Dashboard';
import V267Dashboard from './V267Dashboard';
import V268Dashboard from './V268Dashboard';
import V269Dashboard from './V269Dashboard';
import V270Dashboard from './V270Dashboard';
import V271Dashboard from './V271Dashboard';
import V272Dashboard from './V272Dashboard';
import V273Dashboard from './V273Dashboard';
import V274Dashboard from './V274Dashboard';
import V275Dashboard from './V275Dashboard';
import V276Dashboard from './V276Dashboard';
import V277Dashboard from './V277Dashboard';
import V278Dashboard from './V278Dashboard';
import V279Dashboard from './V279Dashboard';
import V280Dashboard from './V280Dashboard';
import V281Dashboard from './V281Dashboard';
import V282Dashboard from './V282Dashboard';
import V283Dashboard from './V283Dashboard';
import V284Dashboard from './V284Dashboard';
import V285Dashboard from './V285Dashboard';
import V286Dashboard from './V286Dashboard';
import V287Dashboard from './V287Dashboard';
import V288Dashboard from './V288Dashboard';
import V289Dashboard from './V289Dashboard';
import V290Dashboard from './V290Dashboard';
import V291Dashboard from './V291Dashboard';
import V292Dashboard from './V292Dashboard';
import V293Dashboard from './V293Dashboard';
import V294Dashboard from './V294Dashboard';
import V295Dashboard from './V295Dashboard';
import V296Dashboard from './V296Dashboard';
import V297Dashboard from './V297Dashboard';
import V298Dashboard from './V298Dashboard';
import V299Dashboard from './V299Dashboard';
import V300Dashboard from './V300Dashboard';
import V301Dashboard from './V301Dashboard';
import V302Dashboard from './V302Dashboard';
import V303Dashboard from './V303Dashboard';
import V304Dashboard from './V304Dashboard';
import VNextObservatory from './VNextObservatory';

const links = ['Home','Operator Control','Markets','Forecasts','Strategies','Orders','Positions','Risk','Logs','Proof','Repo Harvester','Adapters','Kalshi','Kalshi Real','Strategy Candidates','Strategy Scan','Proposed Trades','Blocked Orders','Firewall','Firewall Rehearsal','Caps & Exposure','Live Submit','V6 Dashboard','V7 Dashboard','V8 Dashboard','V10 Dashboard','V11 Dashboard','V12 Dashboard','V13 Dashboard','V14 Dashboard','V15 Dashboard','V16 Dashboard','V17 Dashboard','V18 Dashboard','V19 Dashboard','V20 Dashboard','V21 Dashboard','V22 Dashboard','V23 Dashboard','V24 Dashboard','V25 Dashboard','V26 Dashboard','V27 Dashboard','V28 Dashboard','V29 Dashboard','V30 Dashboard','V31 Dashboard','V32 Dashboard','V33 Dashboard','V37 Dashboard','V38 Dashboard','V39 Dashboard','V40 Dashboard','V41 Dashboard','V42 Dashboard','V43 Dashboard','V44 Dashboard','V45 Dashboard','V46 Dashboard','V47 Dashboard','V48 Dashboard','V49 Dashboard','V50 Dashboard','V51 Dashboard','V52 Dashboard','V53 Dashboard','V54 Dashboard','V55 Dashboard','V56 Dashboard','V57 Dashboard','V58 Dashboard','V59 Dashboard','V60 Dashboard','V61 Dashboard','V62 Dashboard','V63 Dashboard','V64 Dashboard','V65 Dashboard','V66 Dashboard','V67 Dashboard','V68 Dashboard','V69 Dashboard','V70 Dashboard','V71 Dashboard','V72 Dashboard','V73 Dashboard','V74 Dashboard','V75 Dashboard','V76 Dashboard','V77 Dashboard','V78 Dashboard','V79 Dashboard','V80 Dashboard','V81 Dashboard','V82 Dashboard','V83 Dashboard','V84 Dashboard','V85 Dashboard','V86 Dashboard','V87 Dashboard','V88 Dashboard','V89 Dashboard','V90 Dashboard','V91 Dashboard','V92 Dashboard','V93 Dashboard','V94 Dashboard','V95 Dashboard','V96 Dashboard','V97 Dashboard','V98 Dashboard','V99 Dashboard','V100 Dashboard','V101 Dashboard','V102 Dashboard','V103 Dashboard','V104 Dashboard','V105 Dashboard','V106 Dashboard','V107 Dashboard','V108 Dashboard','V109 Dashboard','V110 Dashboard','V111 Dashboard','V112 Dashboard','V113 Dashboard','V114 Dashboard','V115 Dashboard','V116 Dashboard','V117 Dashboard','V118 Dashboard','V119 Dashboard','V120 Dashboard','V121 Dashboard','V122 Dashboard','V123 Dashboard','V124 Dashboard','V125 Dashboard','V126 Dashboard','V127 Dashboard','V128 Dashboard','V129 Dashboard','V130 Dashboard','V131 Dashboard','V132 Dashboard','V133 Dashboard','V134 Dashboard','V135 Dashboard','V136 Dashboard','V137 Dashboard','V138 Dashboard','V139 Dashboard','V140 Dashboard','V141 Dashboard','V142 Dashboard','V143 Dashboard','V144 Dashboard','V145 Dashboard','V146 Dashboard','V147 Dashboard','V148 Dashboard','V149 Dashboard','V150 Dashboard','V151 Dashboard','V152 Dashboard','V153 Dashboard','V154 Dashboard','V155 Dashboard','V156 Dashboard','V157 Dashboard','V158 Dashboard','V159 Dashboard','V160 Dashboard','V161 Dashboard','V162 Dashboard','V163 Dashboard','V164 Dashboard','V165 Dashboard','V166 Dashboard','V167 Dashboard','V168 Dashboard','V169 Dashboard','V170 Dashboard','V171 Dashboard','V172 Dashboard','V173 Dashboard','V174 Dashboard','V175 Dashboard','V176 Dashboard','V177 Dashboard','V178 Dashboard','V179 Dashboard','V180 Dashboard','V181 Dashboard','V182 Dashboard','V183 Dashboard','V184 Dashboard','V185 Dashboard','V186 Dashboard','V187 Dashboard','V188 Dashboard','V189 Dashboard','V190 Dashboard','V191 Dashboard','V192 Dashboard','V193 Dashboard','V194 Dashboard','V195 Dashboard','V196 Dashboard','V197 Dashboard','V198 Dashboard','V199 Dashboard','V200 Dashboard','V201 Dashboard','V202 Dashboard','V203 Dashboard','V204 Dashboard','V205 Dashboard','V206 Dashboard','V207 Dashboard','V208 Dashboard','V209 Dashboard','V210 Dashboard','V211 Dashboard','V212 Dashboard','V213 Dashboard','V214 Dashboard','V215 Dashboard','V216 Dashboard','V217 Dashboard','V218 Dashboard','V219 Dashboard','V220 Dashboard','V221 Dashboard','V222 Dashboard','V223 Dashboard','V224 Dashboard','V225 Dashboard','V226 Dashboard','V227 Dashboard','V228 Dashboard','V229 Dashboard','V230 Dashboard','V231 Dashboard','V232 Dashboard','V233 Dashboard','V234 Dashboard','V235 Dashboard','V236 Dashboard','V237 Dashboard','V238 Dashboard','V239 Dashboard','V240 Dashboard','V241 Dashboard','V242 Dashboard','V243 Dashboard','V244 Dashboard','V245 Dashboard','V246 Dashboard','V247 Dashboard','V248 Dashboard','V249 Dashboard','V250 Dashboard','V251 Dashboard','V252 Dashboard','V253 Dashboard','V254 Dashboard','V255 Dashboard','V256 Dashboard','V257 Dashboard','V258 Dashboard','V259 Dashboard','V260 Dashboard','V261 Dashboard','V262 Dashboard','V263 Dashboard','V264 Dashboard','V265 Dashboard','V266 Dashboard','V267 Dashboard','V268 Dashboard','V269 Dashboard','V270 Dashboard','V271 Dashboard','V272 Dashboard','V273 Dashboard','V274 Dashboard','V275 Dashboard','V276 Dashboard','V277 Dashboard','V278 Dashboard','V279 Dashboard','V280 Dashboard','V281 Dashboard','V282 Dashboard','V283 Dashboard','V284 Dashboard','V285 Dashboard','V286 Dashboard','V287 Dashboard','V288 Dashboard','V289 Dashboard','V290 Dashboard','V291 Dashboard','V292 Dashboard','V293 Dashboard','V294 Dashboard','V295 Dashboard','V296 Dashboard','V297 Dashboard','V298 Dashboard','V299 Dashboard','V300 Dashboard','V301 Dashboard','V302 Dashboard','V303 Dashboard','V304 Dashboard'];

export default function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen bg-gray-900 text-gray-100">
        <nav className="p-4 border-b border-gray-700 flex gap-4 flex-wrap">
          <Link to="/vnext-observatory" className="font-semibold text-cyan-300 hover:text-cyan-100">vNext Observatory</Link>
          {links.map(l => (
            <Link key={l} to={l === 'Home' ? '/' : `/${l.toLowerCase().replace(/ /g, '-')}`} className="hover:text-blue-400">{l}</Link>
          ))}
        </nav>
        <main className="p-4">
          <Routes>
            <Route path="/" element={<Home />} />
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
            <Route path="/adapters" element={<Adapters />} />
            <Route path="/kalshi" element={<Kalshi />} />
            <Route path="/kalshi-real" element={<KalshiReal />} />
            <Route path="/strategy-candidates" element={<StrategyCandidates />} />
            <Route path="/strategy-scan" element={<StrategyScan />} />
            <Route path="/proposed-trades" element={<ProposedTrades />} />
            <Route path="/blocked-orders" element={<BlockedOrders />} />
            <Route path="/firewall" element={<Firewall />} />
            <Route path="/firewall-rehearsal" element={<FirewallRehearsal />} />
            <Route path="/caps-exposure" element={<CapsExposure />} />
            <Route path="/live-submit" element={<LiveSubmit />} />
            <Route path="/vnext-observatory" element={<VNextObservatory />} />
            <Route path="/v6-dashboard" element={<V6Dashboard />} />
            <Route path="/v7-dashboard" element={<V7Dashboard />} />
            <Route path="/v8-dashboard" element={<V8Dashboard />} />
            <Route path="/v10-dashboard" element={<V10Dashboard />} />
            <Route path="/v11-dashboard" element={<V11Dashboard />} />
            <Route path="/v12-dashboard" element={<V12Dashboard />} />
            <Route path="/v13-dashboard" element={<V13Dashboard />} />
            <Route path="/v14-dashboard" element={<V14Dashboard />} />
            <Route path="/v15-dashboard" element={<V15Dashboard />} />
            <Route path="/v16-dashboard" element={<V16Dashboard />} />
            <Route path="/v17-dashboard" element={<V17Dashboard />} />
            <Route path="/v18-dashboard" element={<V18Dashboard />} />
            <Route path="/v19-dashboard" element={<V19Dashboard />} />
            <Route path="/v20-dashboard" element={<V20Dashboard />} />
            <Route path="/v21-dashboard" element={<V21Dashboard />} />
            <Route path="/v22-dashboard" element={<V22Dashboard />} />
            <Route path="/v23-dashboard" element={<V23Dashboard />} />
            <Route path="/v24-dashboard" element={<V24Dashboard />} />
            <Route path="/v25-dashboard" element={<V25Dashboard />} />
            <Route path="/v26-dashboard" element={<V26Dashboard />} />
            <Route path="/v27-dashboard" element={<V27Dashboard />} />
            <Route path="/v28-dashboard" element={<V28Dashboard />} />
            <Route path="/v29-dashboard" element={<V29Dashboard />} />
            <Route path="/v30-dashboard" element={<V30Dashboard />} />
            <Route path="/v31-dashboard" element={<V31Dashboard />} />
            <Route path="/v32-dashboard" element={<V32Dashboard />} />
            <Route path="/v33-dashboard" element={<V33Dashboard />} />
            <Route path="/v37-dashboard" element={<V37Dashboard />} />
            <Route path="/v38-dashboard" element={<V38Dashboard />} />
            <Route path="/v39-dashboard" element={<V39Dashboard />} />
            <Route path="/v40-dashboard" element={<V40Dashboard />} />
            <Route path="/v41-dashboard" element={<V41Dashboard />} />
            <Route path="/v42-dashboard" element={<V42Dashboard />} />
            <Route path="/v43-dashboard" element={<V43Dashboard />} />
            <Route path="/v44-dashboard" element={<V44Dashboard />} />
            <Route path="/v45-dashboard" element={<V45Dashboard />} />
            <Route path="/v46-dashboard" element={<V46Dashboard />} />
            <Route path="/v47-dashboard" element={<V47Dashboard />} />
            <Route path="/v48-dashboard" element={<V48Dashboard />} />
            <Route path="/v49-dashboard" element={<V49Dashboard />} />
            <Route path="/v50-dashboard" element={<V50Dashboard />} />
            <Route path="/v51-dashboard" element={<V51Dashboard />} />
            <Route path="/v52-dashboard" element={<V52Dashboard />} />
            <Route path="/v53-dashboard" element={<V53Dashboard />} />
            <Route path="/v54-dashboard" element={<V54Dashboard />} />
            <Route path="/v55-dashboard" element={<V55Dashboard />} />
            <Route path="/v56-dashboard" element={<V56Dashboard />} />
            <Route path="/v57-dashboard" element={<V57Dashboard />} />
            <Route path="/v58-dashboard" element={<V58Dashboard />} />
            <Route path="/v59-dashboard" element={<V59Dashboard />} />
            <Route path="/v60-dashboard" element={<V60Dashboard />} />
            <Route path="/v61-dashboard" element={<V61Dashboard />} />
            <Route path="/v62-dashboard" element={<V62Dashboard />} />
            <Route path="/v63-dashboard" element={<V63Dashboard />} />
            <Route path="/v64-dashboard" element={<V64Dashboard />} />
            <Route path="/v65-dashboard" element={<V65Dashboard />} />
            <Route path="/v66-dashboard" element={<V66Dashboard />} />
            <Route path="/v67-dashboard" element={<V67Dashboard />} />
            <Route path="/v68-dashboard" element={<V68Dashboard />} />
            <Route path="/v69-dashboard" element={<V69Dashboard />} />
            <Route path="/v70-dashboard" element={<V70Dashboard />} />
            <Route path="/v71-dashboard" element={<V71Dashboard />} />
            <Route path="/v72-dashboard" element={<V72Dashboard />} />
            <Route path="/v73-dashboard" element={<V73Dashboard />} />
            <Route path="/v74-dashboard" element={<V74Dashboard />} />
            <Route path="/v75-dashboard" element={<V75Dashboard />} />
            <Route path="/v76-dashboard" element={<V76Dashboard />} />
            <Route path="/v77-dashboard" element={<V77Dashboard />} />
            <Route path="/v78-dashboard" element={<V78Dashboard />} />
            <Route path="/v79-dashboard" element={<V79Dashboard />} />
            <Route path="/v80-dashboard" element={<V80Dashboard />} />
            <Route path="/v81-dashboard" element={<V81Dashboard />} />
            <Route path="/v82-dashboard" element={<V82Dashboard />} />
            <Route path="/v83-dashboard" element={<V83Dashboard />} />
            <Route path="/v84-dashboard" element={<V84Dashboard />} />
            <Route path="/v85-dashboard" element={<V85Dashboard />} />
            <Route path="/v86-dashboard" element={<V86Dashboard />} />
            <Route path="/v87-dashboard" element={<V87Dashboard />} />
            <Route path="/v88-dashboard" element={<V88Dashboard />} />
            <Route path="/v89-dashboard" element={<V89Dashboard />} />
            <Route path="/v90-dashboard" element={<V90Dashboard />} />
            <Route path="/v91-dashboard" element={<V91Dashboard />} />
            <Route path="/v92-dashboard" element={<V92Dashboard />} />
            <Route path="/v93-dashboard" element={<V93Dashboard />} />
            <Route path="/v94-dashboard" element={<V94Dashboard />} />
            <Route path="/v95-dashboard" element={<V95Dashboard />} />
            <Route path="/v96-dashboard" element={<V96Dashboard />} />
            <Route path="/v97-dashboard" element={<V97Dashboard />} />
            <Route path="/v98-dashboard" element={<V98Dashboard />} />
            <Route path="/v99-dashboard" element={<V99Dashboard />} />
            <Route path="/v100-dashboard" element={<V100Dashboard />} />
            <Route path="/v101-dashboard" element={<V101Dashboard />} />
            <Route path="/v102-dashboard" element={<V102Dashboard />} />
            <Route path="/v103-dashboard" element={<V103Dashboard />} />
            <Route path="/v104-dashboard" element={<V104Dashboard />} />
            <Route path="/v105-dashboard" element={<V105Dashboard />} />
            <Route path="/v106-dashboard" element={<V106Dashboard />} />
            <Route path="/v107-dashboard" element={<V107Dashboard />} />
            <Route path="/v108-dashboard" element={<V108Dashboard />} />
            <Route path="/v109-dashboard" element={<V109Dashboard />} />
            <Route path="/v110-dashboard" element={<V110Dashboard />} />
            <Route path="/v111-dashboard" element={<V111Dashboard />} />
            <Route path="/v112-dashboard" element={<V112Dashboard />} />
            <Route path="/v113-dashboard" element={<V113Dashboard />} />
            <Route path="/v114-dashboard" element={<V114Dashboard />} />
            <Route path="/v115-dashboard" element={<V115Dashboard />} />
            <Route path="/v116-dashboard" element={<V116Dashboard />} />
            <Route path="/v117-dashboard" element={<V117Dashboard />} />
            <Route path="/v118-dashboard" element={<V118Dashboard />} />
            <Route path="/v119-dashboard" element={<V119Dashboard />} />
            <Route path="/v120-dashboard" element={<V120Dashboard />} />
            <Route path="/v121-dashboard" element={<V121Dashboard />} />
            <Route path="/v122-dashboard" element={<V122Dashboard />} />
            <Route path="/v123-dashboard" element={<V123Dashboard />} />
            <Route path="/v124-dashboard" element={<V124Dashboard />} />
            <Route path="/v125-dashboard" element={<V125Dashboard />} />
            <Route path="/v126-dashboard" element={<V126Dashboard />} />
            <Route path="/v127-dashboard" element={<V127Dashboard />} />
            <Route path="/v128-dashboard" element={<V128Dashboard />} />
            <Route path="/v129-dashboard" element={<V129Dashboard />} />
            <Route path="/v130-dashboard" element={<V130Dashboard />} />
            <Route path="/v131-dashboard" element={<V131Dashboard />} />
            <Route path="/v132-dashboard" element={<V132Dashboard />} />
            <Route path="/v133-dashboard" element={<V133Dashboard />} />
            <Route path="/v134-dashboard" element={<V134Dashboard />} />
            <Route path="/v135-dashboard" element={<V135Dashboard />} />
            <Route path="/v136-dashboard" element={<V136Dashboard />} />
            <Route path="/v137-dashboard" element={<V137Dashboard />} />
            <Route path="/v138-dashboard" element={<V138Dashboard />} />
            <Route path="/v139-dashboard" element={<V139Dashboard />} />
            <Route path="/v140-dashboard" element={<V140Dashboard />} />
            <Route path="/v141-dashboard" element={<V141Dashboard />} />
            <Route path="/v142-dashboard" element={<V142Dashboard />} />
            <Route path="/v143-dashboard" element={<V143Dashboard />} />
            <Route path="/v144-dashboard" element={<V144Dashboard />} />
            <Route path="/v145-dashboard" element={<V145Dashboard />} />
            <Route path="/v146-dashboard" element={<V146Dashboard />} />
            <Route path="/v147-dashboard" element={<V147Dashboard />} />
            <Route path="/v148-dashboard" element={<V148Dashboard />} />
            <Route path="/v149-dashboard" element={<V149Dashboard />} />
            <Route path="/v150-dashboard" element={<V150Dashboard />} />
            <Route path="/v151-dashboard" element={<V151Dashboard />} />
            <Route path="/v152-dashboard" element={<V152Dashboard />} />
            <Route path="/v153-dashboard" element={<V153Dashboard />} />
            <Route path="/v154-dashboard" element={<V154Dashboard />} />
            <Route path="/v155-dashboard" element={<V155Dashboard />} />
            <Route path="/v156-dashboard" element={<V156Dashboard />} />
            <Route path="/v157-dashboard" element={<V157Dashboard />} />
            <Route path="/v158-dashboard" element={<V158Dashboard />} />
            <Route path="/v159-dashboard" element={<V159Dashboard />} />
            <Route path="/v160-dashboard" element={<V160Dashboard />} />
            <Route path="/v161-dashboard" element={<V161Dashboard />} />
            <Route path="/v162-dashboard" element={<V162Dashboard />} />
            <Route path="/v163-dashboard" element={<V163Dashboard />} />
            <Route path="/v164-dashboard" element={<V164Dashboard />} />
            <Route path="/v165-dashboard" element={<V165Dashboard />} />
            <Route path="/v166-dashboard" element={<V166Dashboard />} />
            <Route path="/v167-dashboard" element={<V167Dashboard />} />
            <Route path="/v168-dashboard" element={<V168Dashboard />} />
            <Route path="/v169-dashboard" element={<V169Dashboard />} />
            <Route path="/v170-dashboard" element={<V170Dashboard />} />
            <Route path="/v171-dashboard" element={<V171Dashboard />} />
            <Route path="/v172-dashboard" element={<V172Dashboard />} />
            <Route path="/v173-dashboard" element={<V173Dashboard />} />
            <Route path="/v174-dashboard" element={<V174Dashboard />} />
            <Route path="/v175-dashboard" element={<V175Dashboard />} />
            <Route path="/v176-dashboard" element={<V176Dashboard />} />
            <Route path="/v177-dashboard" element={<V177Dashboard />} />
            <Route path="/v178-dashboard" element={<V178Dashboard />} />
            <Route path="/v179-dashboard" element={<V179Dashboard />} />
            <Route path="/v180-dashboard" element={<V180Dashboard />} />
            <Route path="/v181-dashboard" element={<V181Dashboard />} />
            <Route path="/v182-dashboard" element={<V182Dashboard />} />
            <Route path="/v183-dashboard" element={<V183Dashboard />} />
            <Route path="/v184-dashboard" element={<V184Dashboard />} />
            <Route path="/v185-dashboard" element={<V185Dashboard />} />
            <Route path="/v186-dashboard" element={<V186Dashboard />} />
            <Route path="/v187-dashboard" element={<V187Dashboard />} />
            <Route path="/v188-dashboard" element={<V188Dashboard />} />
            <Route path="/v189-dashboard" element={<V189Dashboard />} />
            <Route path="/v190-dashboard" element={<V190Dashboard />} />
            <Route path="/v191-dashboard" element={<V191Dashboard />} />
            <Route path="/v192-dashboard" element={<V192Dashboard />} />
            <Route path="/v193-dashboard" element={<V193Dashboard />} />
            <Route path="/v194-dashboard" element={<V194Dashboard />} />
            <Route path="/v195-dashboard" element={<V195Dashboard />} />
            <Route path="/v196-dashboard" element={<V196Dashboard />} />
            <Route path="/v197-dashboard" element={<V197Dashboard />} />
            <Route path="/v198-dashboard" element={<V198Dashboard />} />
            <Route path="/v199-dashboard" element={<V199Dashboard />} />
            <Route path="/v200-dashboard" element={<V200Dashboard />} />
            <Route path="/v201-dashboard" element={<V201Dashboard />} />
            <Route path="/v202-dashboard" element={<V202Dashboard />} />
            <Route path="/v203-dashboard" element={<V203Dashboard />} />
            <Route path="/v204-dashboard" element={<V204Dashboard />} />
            <Route path="/v205-dashboard" element={<V205Dashboard />} />
            <Route path="/v206-dashboard" element={<V206Dashboard />} />
            <Route path="/v207-dashboard" element={<V207Dashboard />} />
            <Route path="/v208-dashboard" element={<V208Dashboard />} />
            <Route path="/v209-dashboard" element={<V209Dashboard />} />
            <Route path="/v210-dashboard" element={<V210Dashboard />} />
            <Route path="/v211-dashboard" element={<V211Dashboard />} />
            <Route path="/v212-dashboard" element={<V212Dashboard />} />
            <Route path="/v213-dashboard" element={<V213Dashboard />} />
            <Route path="/v214-dashboard" element={<V214Dashboard />} />
            <Route path="/v215-dashboard" element={<V215Dashboard />} />
            <Route path="/v216-dashboard" element={<V216Dashboard />} />
            <Route path="/v217-dashboard" element={<V217Dashboard />} />
            <Route path="/v218-dashboard" element={<V218Dashboard />} />
            <Route path="/v219-dashboard" element={<V219Dashboard />} />
            <Route path="/v220-dashboard" element={<V220Dashboard />} />
            <Route path="/v221-dashboard" element={<V221Dashboard />} />
            <Route path="/v222-dashboard" element={<V222Dashboard />} />
            <Route path="/v223-dashboard" element={<V223Dashboard />} />
            <Route path="/v224-dashboard" element={<V224Dashboard />} />
            <Route path="/v225-dashboard" element={<V225Dashboard />} />
            <Route path="/v226-dashboard" element={<V226Dashboard />} />
            <Route path="/v227-dashboard" element={<V227Dashboard />} />
            <Route path="/v228-dashboard" element={<V228Dashboard />} />
            <Route path="/v229-dashboard" element={<V229Dashboard />} />
            <Route path="/v230-dashboard" element={<V230Dashboard />} />
            <Route path="/v231-dashboard" element={<V231Dashboard />} />
            <Route path="/v232-dashboard" element={<V232Dashboard />} />
            <Route path="/v233-dashboard" element={<V233Dashboard />} />
            <Route path="/v234-dashboard" element={<V234Dashboard />} />
            <Route path="/v235-dashboard" element={<V235Dashboard />} />
            <Route path="/v236-dashboard" element={<V236Dashboard />} />
            <Route path="/v237-dashboard" element={<V237Dashboard />} />
            <Route path="/v238-dashboard" element={<V238Dashboard />} />
            <Route path="/v239-dashboard" element={<V239Dashboard />} />
            <Route path="/v240-dashboard" element={<V240Dashboard />} />
            <Route path="/v241-dashboard" element={<V241Dashboard />} />
            <Route path="/v242-dashboard" element={<V242Dashboard />} />
            <Route path="/v243-dashboard" element={<V243Dashboard />} />
            <Route path="/v244-dashboard" element={<V244Dashboard />} />
            <Route path="/v245-dashboard" element={<V245Dashboard />} />
            <Route path="/v246-dashboard" element={<V246Dashboard />} />
            <Route path="/v247-dashboard" element={<V247Dashboard />} />
            <Route path="/v248-dashboard" element={<V248Dashboard />} />
            <Route path="/v249-dashboard" element={<V249Dashboard />} />
            <Route path="/v250-dashboard" element={<V250Dashboard />} />
            <Route path="/v251-dashboard" element={<V251Dashboard />} />
            <Route path="/v252-dashboard" element={<V252Dashboard />} />
            <Route path="/v253-dashboard" element={<V253Dashboard />} />
            <Route path="/v254-dashboard" element={<V254Dashboard />} />
            <Route path="/v255-dashboard" element={<V255Dashboard />} />
            <Route path="/v256-dashboard" element={<V256Dashboard />} />
            <Route path="/v257-dashboard" element={<V257Dashboard />} />
            <Route path="/v258-dashboard" element={<V258Dashboard />} />
            <Route path="/v259-dashboard" element={<V259Dashboard />} />
            <Route path="/v260-dashboard" element={<V260Dashboard />} />
            <Route path="/v261-dashboard" element={<V261Dashboard />} />
            <Route path="/v262-dashboard" element={<V262Dashboard />} />
            <Route path="/v263-dashboard" element={<V263Dashboard />} />
            <Route path="/v264-dashboard" element={<V264Dashboard />} />
            <Route path="/v265-dashboard" element={<V265Dashboard />} />
            <Route path="/v266-dashboard" element={<V266Dashboard />} />
            <Route path="/v267-dashboard" element={<V267Dashboard />} />
            <Route path="/v268-dashboard" element={<V268Dashboard />} />
            <Route path="/v269-dashboard" element={<V269Dashboard />} />
            <Route path="/v270-dashboard" element={<V270Dashboard />} />
            <Route path="/v271-dashboard" element={<V271Dashboard />} />
            <Route path="/v272-dashboard" element={<V272Dashboard />} />
            <Route path="/v273-dashboard" element={<V273Dashboard />} />
            <Route path="/v274-dashboard" element={<V274Dashboard />} />
            <Route path="/v275-dashboard" element={<V275Dashboard />} />
            <Route path="/v276-dashboard" element={<V276Dashboard />} />
            <Route path="/v277-dashboard" element={<V277Dashboard />} />
            <Route path="/v278-dashboard" element={<V278Dashboard />} />
            <Route path="/v279-dashboard" element={<V279Dashboard />} />
            <Route path="/v280-dashboard" element={<V280Dashboard />} />
            <Route path="/v281-dashboard" element={<V281Dashboard />} />
            <Route path="/v282-dashboard" element={<V282Dashboard />} />
            <Route path="/v283-dashboard" element={<V283Dashboard />} />
            <Route path="/v284-dashboard" element={<V284Dashboard />} />
            <Route path="/v285-dashboard" element={<V285Dashboard />} />
            <Route path="/v286-dashboard" element={<V286Dashboard />} />
            <Route path="/v287-dashboard" element={<V287Dashboard />} />
            <Route path="/v288-dashboard" element={<V288Dashboard />} />
            <Route path="/v289-dashboard" element={<V289Dashboard />} />
            <Route path="/v290-dashboard" element={<V290Dashboard />} />
            <Route path="/v291-dashboard" element={<V291Dashboard />} />
            <Route path="/v292-dashboard" element={<V292Dashboard />} />
            <Route path="/v293-dashboard" element={<V293Dashboard />} />
            <Route path="/v294-dashboard" element={<V294Dashboard />} />
            <Route path="/v295-dashboard" element={<V295Dashboard />} />
            <Route path="/v296-dashboard" element={<V296Dashboard />} />
            <Route path="/v297-dashboard" element={<V297Dashboard />} />
            <Route path="/v298-dashboard" element={<V298Dashboard />} />
            <Route path="/v299-dashboard" element={<V299Dashboard />} />
            <Route path="/v300-dashboard" element={<V300Dashboard />} />
            <Route path="/v301-dashboard" element={<V301Dashboard />} />
            <Route path="/v302-dashboard" element={<V302Dashboard />} />
            <Route path="/v303-dashboard" element={<V303Dashboard />} />
            <Route path="/v304-dashboard" element={<V304Dashboard />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}
