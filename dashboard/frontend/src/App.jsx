import { BrowserRouter, Routes, Route, Link } from 'react-router-dom';
import Home from './screens/Home';
import Markets from './screens/Markets';
import Forecasts from './screens/Forecasts';
import Strategies from './screens/Strategies';
import Orders from './screens/Orders';
import Positions from './screens/Positions';
import Risk from './screens/Risk';
import Logs from './screens/Logs';
import Proof from './screens/Proof';
import RepoHarvester from './screens/RepoHarvester';

const links = ['Home','Markets','Forecasts','Strategies','Orders','Positions','Risk','Logs','Proof','Repo Harvester'];

export default function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen bg-gray-900 text-gray-100">
        <nav className="p-4 border-b border-gray-700 flex gap-4 flex-wrap">
          {links.map(l => (
            <Link key={l} to={l === 'Home' ? '/' : `/${l.toLowerCase().replace(/ /g, '-')}`} className="hover:text-blue-400">{l}</Link>
          ))}
        </nav>
        <main className="p-4">
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/markets" element={<Markets />} />
            <Route path="/forecasts" element={<Forecasts />} />
            <Route path="/strategies" element={<Strategies />} />
            <Route path="/orders" element={<Orders />} />
            <Route path="/positions" element={<Positions />} />
            <Route path="/risk" element={<Risk />} />
            <Route path="/logs" element={<Logs />} />
            <Route path="/proof" element={<Proof />} />
            <Route path="/repo-harvester" element={<RepoHarvester />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}
