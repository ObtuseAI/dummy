import { useEffect, useState } from 'react';
import { fetchJson, postJson } from '../hooks/useApi';

const MODE_ACK = '1';
const PROOF_ACK = 'FULL_AUTHORITY_OPERATOR_APPROVED_LIVE_PROOF_ONLY';
const TYPED_CONFIRM =
  'I understand this can place one real limit order only through LiveBrokerFirewall after all Dummy gates pass';

const ADAPTER_TYPED_CONFIRM =
  'I confirm this is a real credentialed LiveBrokerFirewall adapter, not a stub, and it supports limit orders only';
const LIVE_SUBMIT_TYPED_CONFIRM =
  'I confirm live-submit is enabled for one controlled proof only and Dummy must still pass all gates before any order';
const CAPS_TYPED_CONFIRM =
  'I confirm these caps are strict, limit-only, kill-switch protected, and for one controlled proof only';

const SECOND_PROOF_CONFIRM =
  'I confirm a second controlled real broker proof attempt using the validated V3 candidate, limit order only, count 1, no market orders, no scale, no autonomy, and Dummy must still pass every gate before any order';

function Out({ result }) {
  if (!result) return null;
  return (
    <pre className="mt-3 bg-gray-950 p-3 rounded text-xs overflow-x-auto whitespace-pre-wrap">
      {result.refused ? `REFUSED: ${result.reason}\n${result.hint || ''}\n` : ''}
      {result.command ? `$ ${result.command}\n\n` : ''}
      {result.stdout || ''}
      {result.stderr ? `\n[stderr]\n${result.stderr}` : ''}
      {result.safety_notes?.length ? `\n[safety] ${result.safety_notes.join(' · ')}` : ''}
      {result.live_submit_config ? `\n[live_submit.json] ${JSON.stringify(result.live_submit_config)}` : ''}
      {result.approvals ? `\n[approvals] ${result.approvals.count} file(s) at ${result.approvals.path}` : ''}
      {result.proposed ? `\n[proposed] ${JSON.stringify(result.proposed, null, 2)}` : ''}
      {result.hash_before !== undefined ? `\n[hash] before=${result.hash_before || 'none'} after=${result.hash_after || 'none'}` : ''}
      {result.backup_path ? `\n[backup] ${result.backup_path}` : ''}
      {result.blockers?.length ? `\n[blockers]\n${result.blockers.join('\n')}` : ''}
    </pre>
  );
}

function Pill({ children, color }) {
  const map = {
    green: 'bg-green-900 text-green-200',
    red: 'bg-red-900 text-red-200',
    yellow: 'bg-yellow-900 text-yellow-200',
    gray: 'bg-gray-700 text-gray-200',
    blue: 'bg-blue-900 text-blue-200',
  };
  return <span className={`text-xs px-2 py-0.5 rounded ${map[color] || map.gray}`}>{children}</span>;
}

function StatusPill({ status, field, good = 'valid', bad = 'blocked' }) {
  if (!status) return <Pill color="gray">unknown</Pill>;
  const value = status[field];
  if (field === 'exists' && value) return <Pill color="blue">staged</Pill>;
  if (field === 'exists' && !value) return <Pill color="red">missing</Pill>;
  if (field === 'staged' && value) return <Pill color="blue">staged</Pill>;
  if (field === 'enabled' && value) return <Pill color="green">enabled</Pill>;
  if (field === 'enabled' && !value) return <Pill color="red">disabled</Pill>;
  if (field === 'strict' && value) return <Pill color="green">strict</Pill>;
  if (field === 'strict' && !value) return <Pill color="red">not strict</Pill>;
  if (field === 'valid' && value) return <Pill color="green">{good}</Pill>;
  if (field === 'valid' && !value) return <Pill color="red">{bad}</Pill>;
  return <Pill color="gray">{String(value)}</Pill>;
}

function NextProofCandidatePanel() {
  const [candidate, setCandidate] = useState(null);
  useEffect(() => {
    fetchJson("/api/operator-control/next-proof-candidate")
      .then(setCandidate)
      .catch(() => setCandidate(null));
  }, []);
  if (!candidate) return null;

  const v1 = candidate.v1_status || candidate;
  const v2 = candidate.v2_status || { status: "not_generated_yet" };
  const v3 = candidate.v3_status || { status: "not_generated_yet" };

  return (
    <section className="panel next-proof-candidate">
      <h2>Next Proof Candidate (Read-Only)</h2>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="rounded p-3 border border-gray-700 bg-gray-800">
          <h3 className="font-bold text-sm mb-2">V1 No-Network Candidate</h3>
          <div className="text-xs space-y-1">
            <p>Validation status: {v1.candidate_validation_status}</p>
            <p>Market validated: {v1.market_validated ? "yes" : "no"}</p>
            <p>Contract validated: {v1.contract_validated ? "yes" : "no"}</p>
            <p>Read-only metadata mode: {v1.read_only_metadata_mode}</p>
            <p>Submit allowed now: {v1.submit_allowed_now ? "true" : "false"}</p>
            <p>Requires new operator proof authority: {v1.requires_new_operator_proof_authority ? "yes" : "no"}</p>
            <p>Reason: {v1.reason_submit_not_allowed}</p>
            <p>Proof lock status: {v1.proof_lock_status}</p>
            <p>Next action: {v1.next_action}</p>
          </div>
        </div>

        <div className="rounded p-3 border border-gray-700 bg-gray-800">
          <h3 className="font-bold text-sm mb-2">V2 Read-Only Metadata Candidate</h3>
          <div className="text-xs space-y-1">
            {v2.status === "not_generated_yet" ? (
              <p>V2 candidate has not been generated yet.</p>
            ) : (
              <>
                <p>Candidate found: {v2.candidate_found ? "yes" : "no"}</p>
                <p>Market ticker: {v2.market_ticker || "—"}</p>
                <p>Contract ticker: {v2.contract_ticker || "—"}</p>
                <p>Market tradable: {v2.market_tradable ? "yes" : "no"}</p>
                <p>Contract tradable: {v2.contract_tradable ? "yes" : "no"}</p>
                <p>Price validated: {v2.price_validated ? "yes" : "no"}</p>
                <p>Price source: {v2.price_source || "unknown"}</p>
                <p>Price: {v2.price !== undefined && v2.price !== null ? v2.price : "—"}</p>
                <p>Read-only metadata contact: {v2.read_only_metadata_contact ? "yes" : "no"}</p>
                <p>Submit allowed now: {v2.submit_allowed_now ? "true" : "false"}</p>
                <p>Requires new operator proof authority: {v2.requires_new_operator_proof_authority ? "yes" : "no"}</p>
                <p>Proof lock status: {v2.proof_lock_status}</p>
                <p>Next action: {v2.next_action}</p>
                <p>Secrets redacted: {v2.secrets_redacted ? "yes" : "no"}</p>
              </>
            )}
          </div>
        </div>

        <div className="rounded p-3 border border-gray-700 bg-gray-800">
          <h3 className="font-bold text-sm mb-2">V3 Read-Only Discovery Candidate</h3>
          <div className="text-xs space-y-1">
            {v3.status === "not_generated_yet" ? (
              <p>V3 discovery candidate has not been generated yet.</p>
            ) : (
              <>
                <p>Status: {v3.status}</p>
                <p>Discovery mode: {v3.discovery_mode || "—"}</p>
                <p>Candidate found: {v3.candidate_found ? "yes" : "no"}</p>
                <p>Market ticker: {v3.market_ticker || "—"}</p>
                <p>Contract ticker: {v3.contract_ticker || "—"}</p>
                <p>Market status: {v3.market_status || "—"}</p>
                <p>Contract status: {v3.contract_status || "—"}</p>
                <p>Market tradable: {v3.market_tradable ? "yes" : "no"}</p>
                <p>Contract tradable: {v3.contract_tradable ? "yes" : "no"}</p>
                <p>Price validated: {v3.price_validated ? "yes" : "no"}</p>
                <p>Price source: {v3.price_source || "unknown"}</p>
                <p>Price: {v3.price !== undefined && v3.price !== null ? v3.price : "—"}</p>
                <p>Read-only metadata contact: {v3.read_only_metadata_contact ? "yes" : "no"}</p>
                <p>GET requests: {v3.get_request_count ?? 0}</p>
                <p>Write requests: {v3.write_request_count ?? 0}</p>
                <p>Blocked writes: {v3.blocked_write_request_count ?? 0}</p>
                <p>Response schema: {v3.response_schema_summary || "—"}</p>
                {v3.exact_blockers?.length > 0 && (
                  <p className="text-red-300">Blockers: {v3.exact_blockers.join("; ")}</p>
                )}
                <p>Submit allowed now: {v3.submit_allowed_now ? "true" : "false"}</p>
                <p>Requires new operator proof authority: {v3.requires_new_operator_proof_authority ? "yes" : "no"}</p>
                <p>Proof lock status: {v3.proof_lock_status}</p>
                <p>Next action: {v3.next_action}</p>
                <p>Secrets redacted: {v3.secrets_redacted ? "yes" : "no"}</p>
              </>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}

export default function OperatorControl() {
  const [status, setStatus] = useState(null);
  const [prereqStatus, setPrereqStatus] = useState(null);
  const [checkAll, setCheckAll] = useState(null);
  const [busy, setBusy] = useState('');
  const [out, setOut] = useState({});
  const [modeAck, setModeAck] = useState('');
  const [proofAck, setProofAck] = useState('');
  const [typedConfirm, setTypedConfirm] = useState('');
  const [armConfirmed, setArmConfirmed] = useState(false);

  const [adapter, setAdapter] = useState({
    broker: 'KALSHI',
    adapter_name: '',
    adapter_module_path: 'predator_mesh/brokers/kalshi_livebrokerfirewall_adapter.py',
    adapter_descriptor_path: '',
    limit_order_endpoint_label: '',
    credential_reference_names: 'KALSHI_API_KEY_ID,KALSHI_API_PRIVATE_KEY_PEM',
    endpoint_env_ref: 'KALSHI_API_BASE',
    operator_confirm_adapter_real: false,
    operator_confirm_not_stub: false,
    operator_confirm_limit_only: false,
    typed_confirmation: '',
  });

  const [liveSubmit, setLiveSubmit] = useState({
    enabled: true,
    operator: '',
    reason: '',
    expiry: '',
    typed_confirmation: '',
  });

  const [caps, setCaps] = useState({
    max_order_count: 1,
    max_order_size: 100,
    order_type_policy: 'LIMIT_ONLY',
    market_orders_allowed: false,
    kill_switch_enabled: true,
    max_daily_loss: 500,
    max_open_exposure: 1000,
    operator: '',
    reason: '',
    expiry: '',
    typed_confirmation: '',
  });

  const [secondProof, setSecondProof] = useState(null);
  const [spBusy, setSpBusy] = useState('');
  const [spOut, setSpOut] = useState({});
  const [spOperator, setSpOperator] = useState('');
  const [spReason, setSpReason] = useState('');
  const [spExpiry, setSpExpiry] = useState('');
  const [spConfirm, setSpConfirm] = useState('');

  const refreshSecondProof = () =>
    fetchJson('/api/operator-control/second-proof-authority')
      .then(setSecondProof)
      .catch(e => setSecondProof({ state: 'error', error: e.message }));

  const refresh = () =>
    fetchJson('/api/operator-control/status').then(setStatus).catch(e => setStatus({ error: e.message }));

  const refreshPrereqs = () => {
    fetchJson('/api/operator-control/external-prereqs/status')
      .then(setPrereqStatus)
      .catch(e => setPrereqStatus({ error: e.message }));
    fetchJson('/api/operator-control/external-prereqs/check-all')
      .then(setCheckAll)
      .catch(e => setCheckAll({ ok: false, blockers: [e.message] }));
  };

  useEffect(() => {
    refresh();
    refreshPrereqs();
    refreshSecondProof();
  }, []);

  const call = async (key, path, body) => {
    setBusy(key);
    try {
      const r = await postJson(path, body || {});
      setOut(o => ({ ...o, [key]: r }));
    } catch (e) {
      setOut(o => ({ ...o, [key]: { stderr: e.message, safety_notes: ['fetch-error'] } }));
    } finally {
      setBusy('');
      refresh();
      refreshPrereqs();
    }
  };

  const spCall = async (key, path, body) => {
    setSpBusy(key);
    try {
      const r = await postJson(path, body || {});
      setSpOut(o => ({ ...o, [key]: r }));
    } catch (e) {
      setSpOut(o => ({ ...o, [key]: { stderr: e.message, safety_notes: ['fetch-error'] } }));
    } finally {
      setSpBusy('');
      refreshSecondProof();
      refresh();
      refreshPrereqs();
    }
  };

  const parseCredentialRefs = value =>
    value
      .split(/[,\n]+/)
      .map(s => s.trim())
      .filter(Boolean);

  const looksLikeRawSecret = value => {
    if (!value || typeof value !== 'string') return false;
    // Long, space-less strings are likely keys/secrets.
    if (value.length > 64 && !value.includes(' ')) return true;
    // Known secret prefixes.
    if (value.startsWith('sk-') || value.startsWith('AKIA') || value.startsWith('ghp_') || value.startsWith('glpat-')) return true;
    // Keywords combined with length.
    const low = value.toLowerCase();
    const secretKeywords = ['api_key', 'apikey', 'api_secret', 'secret', 'private_key', 'password', 'token'];
    if (secretKeywords.some(kw => low.includes(kw)) && value.length > 32) return true;
    return false;
  };

  const adapterRefErrors = () => {
    const refs = parseCredentialRefs(adapter.credential_reference_names);
    const errors = [];
    if (refs.length === 0) errors.push('At least one credential reference is required.');
    refs.forEach(ref => {
      if (!/^[A-Z_][A-Z0-9_]*$/.test(ref)) {
        errors.push(`'${ref}' is not a valid env-var-style reference.`);
      }
      if (looksLikeRawSecret(ref)) {
        errors.push(`'${ref}' looks like a raw secret; use an env-var reference name only.`);
      }
    });
    if (adapter.endpoint_env_ref && !/^[A-Z_][A-Z0-9_]*$/.test(adapter.endpoint_env_ref)) {
      errors.push(`Endpoint env ref '${adapter.endpoint_env_ref}' is not a valid env-var-style reference.`);
    }
    if (adapter.endpoint_env_ref && looksLikeRawSecret(adapter.endpoint_env_ref)) {
      errors.push('Endpoint env ref looks like a raw secret; use a reference name only.');
    }
    return errors;
  };

  const buildAdapterDescriptor = () => {
    const refs = parseCredentialRefs(adapter.credential_reference_names);
    const descriptor = {
      broker: adapter.broker || 'KALSHI',
      adapter_name: adapter.adapter_name,
      adapter_type: 'LiveBrokerFirewall',
      order_type_policy: 'LIMIT_ONLY',
      market_orders_allowed: false,
      credential_source: 'env_ref',
      adapter_module_path: adapter.adapter_module_path || undefined,
      adapter_descriptor_path: adapter.adapter_descriptor_path || undefined,
      limit_order_endpoint_label: adapter.limit_order_endpoint_label,
      credential_reference_names: refs,
    };
    if (adapter.endpoint_env_ref?.trim()) {
      descriptor.endpoint_env_ref = adapter.endpoint_env_ref.trim();
    }
    return descriptor;
  };

  const liveEnabled = status?.live_submit_config?.enabled;
  const armOk =
    modeAck === MODE_ACK &&
    proofAck === PROOF_ACK &&
    typedConfirm === TYPED_CONFIRM &&
    armConfirmed &&
    checkAll?.ready;

  const Btn = ({ k, label, onClick, disabled, danger, small }) => (
    <button
      onClick={onClick}
      disabled={disabled || busy}
      className={`rounded font-semibold shrink-0 ${
        small ? 'px-2 py-1 text-xs' : 'px-4 py-2'
      } ${danger ? 'bg-red-600 hover:bg-red-500' : 'bg-blue-600 hover:bg-blue-500'} disabled:opacity-40 disabled:cursor-not-allowed`}
    >
      {busy === k ? '…' : label}
    </button>
  );

  const Card = ({ title, desc, children, danger }) => (
    <div className={`rounded p-4 border ${danger ? 'border-red-700 bg-red-950/30' : 'border-gray-700 bg-gray-800'}`}>
      <div className="font-bold">{title}</div>
      {desc && <div className="text-xs text-gray-400 mt-1">{desc}</div>}
      <div className="mt-3 space-y-3">{children}</div>
    </div>
  );

  const Field = ({ label, value, onChange, placeholder, type = 'text' }) => (
    <label className="block text-xs text-gray-400">
      {label}
      <input
        type={type}
        value={value}
        onChange={e => onChange(type === 'number' ? parseInt(e.target.value || '0', 10) : e.target.value)}
        placeholder={placeholder}
        className="mt-1 w-full bg-gray-950 border border-gray-700 rounded px-2 py-1 text-sm"
      />
    </label>
  );

  const Check = ({ label, checked, onChange }) => (
    <label className="flex items-center gap-2 text-xs text-gray-300">
      <input type="checkbox" checked={checked} onChange={e => onChange(e.target.checked)} />
      {label}
    </label>
  );

  return (
    <div className="space-y-5 max-w-4xl">
      <div>
        <h1 className="text-2xl font-bold">Operator Control — Dummy Live Proof</h1>
        <p className="text-sm text-gray-400 mt-1">
          Every button runs the existing operator-side appliance — nothing here bypasses the command
          seal, resolver, proof-starvation stop rule, or LiveBrokerFirewall. The final live step
          refuses unless you type the exact acknowledgements and all external prerequisites are ready.
        </p>
      </div>

      {/* status banner */}
      <div className="rounded p-4 bg-gray-800 border border-gray-700 flex gap-6 flex-wrap">
        <div>
          <div className="text-xs text-gray-400">live_submit.json</div>
          <div className={`text-xl font-bold ${liveEnabled ? 'text-green-400' : 'text-red-400'}`}>
            {liveEnabled ? 'ENABLED' : 'DISABLED'}
          </div>
        </div>
        <div>
          <div className="text-xs text-gray-400">live_orders</div>
          <div className="text-xl font-bold text-gray-100">{status?.live_orders ?? '?'}</div>
        </div>
        <div>
          <div className="text-xs text-gray-400">broker_contact</div>
          <div className="text-xl font-bold text-gray-100">{String(status?.broker_contact ?? false)}</div>
        </div>
        <div>
          <div className="text-xs text-gray-400">approvals</div>
          <div className="text-sm mt-1">{status?.approvals?.count ?? '?'} file(s)</div>
        </div>
        <div>
          <div className="text-xs text-gray-400">completion</div>
          <div className="text-sm mt-1">{status?.completion_percent ?? '—'}%</div>
        </div>
        <button
          onClick={() => { refresh(); refreshPrereqs(); }}
          className="ml-auto px-3 py-1 rounded bg-gray-700 hover:bg-gray-600 text-sm self-start"
        >
          Refresh status
        </button>
      </div>

      <NextProofCandidatePanel />

      <section className="panel second-proof-authority rounded p-4 border border-gray-700 bg-gray-800 space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="font-bold">Second Proof Authority</h2>
          <button
            onClick={refreshSecondProof}
            className="px-3 py-1 rounded bg-gray-700 hover:bg-gray-600 text-sm"
          >
            Refresh
          </button>
        </div>

        <div className="rounded p-3 border border-gray-700 bg-gray-900/30 text-xs space-y-2">
          <div className="flex items-center gap-2">
            <span className="text-gray-400">state:</span>
            <Pill color={secondProof?.state === 'active' ? 'green' : secondProof?.state === 'draft' ? 'yellow' : 'gray'}>
              {secondProof?.state || 'unknown'}
            </Pill>
          </div>
          {secondProof?.candidate_market_ticker && (
            <p>market ticker: {secondProof.candidate_market_ticker}</p>
          )}
          {secondProof?.candidate_contract_ticker && (
            <p>contract ticker: {secondProof.candidate_contract_ticker}</p>
          )}
          {secondProof?.candidate_price !== undefined && secondProof?.candidate_price !== null && (
            <p>price: {secondProof.candidate_price} count: {secondProof.candidate_count || 1} type: {secondProof.candidate_order_type || 'LIMIT'}</p>
          )}
          {secondProof?.next_action && <p>next action: {secondProof.next_action}</p>}
          {secondProof?.submit_allowed_now === false && (
            <p className="text-red-300">submit not allowed: {secondProof.reason_submit_not_allowed || secondProof.next_action}</p>
          )}
          {secondProof?.no_auto_live && (
            <p className="text-gray-500">one-shot-live remains in the existing gated path only</p>
          )}
        </div>

        {secondProof?.state === 'absent' && (
          <div>
            <Btn k="spPrepare" label="Prepare second-proof authority" onClick={() => spCall('spPrepare', '/api/operator-control/second-proof-authority/prepare')} />
          </div>
        )}

        {secondProof?.state === 'draft' && (
          <div className="rounded p-3 border border-yellow-700 bg-yellow-950/20 space-y-3">
            <div className="font-semibold text-yellow-300">Activate second-proof authority</div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
              <Field label="operator name" value={spOperator} onChange={setSpOperator} placeholder="operator name" />
              <Field label="reason" value={spReason} onChange={setSpReason} placeholder="second controlled proof" />
              <Field label="expires at (ISO-8601)" value={spExpiry} onChange={setSpExpiry} placeholder="2026-07-08T21:00:00Z" />
            </div>
            <label className="block text-xs text-gray-400">
              Exact typed confirmation
              <textarea
                value={spConfirm}
                onChange={e => setSpConfirm(e.target.value)}
                placeholder={SECOND_PROOF_CONFIRM}
                rows={4}
                className="mt-1 w-full bg-gray-950 border border-gray-700 rounded px-2 py-1 text-sm"
              />
            </label>
            <Btn
              k="spActivate"
              label="Activate second-proof authority"
              disabled={spConfirm !== SECOND_PROOF_CONFIRM}
              onClick={() =>
                spCall('spActivate', '/api/operator-control/second-proof-authority/activate', {
                  operator_name: spOperator,
                  reason: spReason,
                  expires_at: spExpiry,
                  confirm: spConfirm,
                })
              }
            />
            {spConfirm.length > 0 && spConfirm !== SECOND_PROOF_CONFIRM && (
              <div className="text-xs text-red-300">Confirmation does not match the required sentence exactly.</div>
            )}
          </div>
        )}

        {secondProof?.state === 'active' && (
          <div className="rounded p-3 border border-green-700 bg-green-900/20 text-xs text-green-200">
            Second-proof authority is active. Arm the env gate and run one-shot-live via the CLI exactly once.
            No automatic live proof is triggered from this dashboard.
          </div>
        )}

        <Out result={spOut.spPrepare} />
        <Out result={spOut.spActivate} />
      </section>

      <Card
        title="1. Status / Doctor / Proof-starvation stop rule"
        desc="Read-only diagnostics. No broker contact, no order placement."
      >
        <Out result={status} />
      </Card>

      <Card
        title="2. Dry Run (authority appliance dry-run-all)"
        desc="Builds + verifies the authority pack. No execute-once, no broker contact, no order."
      >
        <Btn k="dryrun" label="Dry Run" onClick={() => call('dryrun', '/api/operator-control/dry-run')} />
        <Out result={out.dryrun} />
      </Card>

      <Card
        title="3. Max Progress (bootstrap max-progress)"
        desc="Runs the safest max-progress path. Fails closed at the CLI env-gate; no market/scale/autonomy flags injected."
      >
        <Btn k="max" label="Max Progress / Full Auto" onClick={() => call('max', '/api/operator-control/max-progress')} />
        <Out result={out.max} />
      </Card>

      <Card
        title="4. One-Shot Check (operator_full_completion one-shot-check)"
        desc="Runs all authority checks. Reports whether the command seal is ready or blocked."
      >
        <Btn k="check" label="One-Shot Check" onClick={() => call('check', '/api/operator-control/one-shot-check')} />
        <Out result={out.check} />
      </Card>

      {/* external prerequisites section */}
      <div className="rounded p-4 border border-yellow-700 bg-yellow-950/20 space-y-4">
        <div className="flex items-center justify-between">
          <div className="font-bold text-yellow-300">5. External Prerequisites</div>
          <div className="flex gap-2">
            <Btn k="checkall" label="Check All Prereqs" small onClick={() => call('checkall', '/api/operator-control/external-prereqs/check-all')} />
            <Btn k="oscheck" label="Run One-Shot Check" small onClick={() => call('oscheck', '/api/operator-control/one-shot-check')} />
          </div>
        </div>

        {checkAll && (
          <div className={`text-xs p-2 rounded ${checkAll.ready ? 'bg-green-900/30 text-green-200' : 'bg-red-900/30 text-red-200'}`}>
            {checkAll.ready ? 'All external prerequisites report READY.' : `NOT READY — ${checkAll.blockers?.join('; ') || 'unknown blockers'}`}
          </div>
        )}

        {/* adapter card */}
        <div className="rounded p-3 border border-gray-700 bg-gray-800 space-y-3">
          <div className="flex items-center justify-between">
            <div className="font-semibold">5a. LiveBrokerFirewall Adapter</div>
            <div className="flex gap-1">
              <StatusPill status={prereqStatus?.adapter} field="staged" />
              <StatusPill status={prereqStatus?.adapter} field="valid" />
            </div>
          </div>

          {/* status display */}
          {prereqStatus?.adapter && (
            <div className="text-xs space-y-1 p-2 rounded bg-gray-900/50">
              <div className="flex items-center gap-2">
                <span className="text-gray-400">descriptor:</span>
                <StatusPill status={prereqStatus.adapter} field="staged" good="staged" bad="missing" />
              </div>
              <div className="flex items-center gap-2">
                <span className="text-gray-400">module:</span>
                {prereqStatus.adapter.module_importable ? (
                  <Pill color="green">importable</Pill>
                ) : (
                  <Pill color="yellow">not importable{prereqStatus.adapter.module_import_error ? ` — ${prereqStatus.adapter.module_import_error}` : ''}</Pill>
                )}
              </div>
              <div className="flex items-center gap-2">
                <span className="text-gray-400">broker contact:</span>
                <Pill color="gray">no contact</Pill>
              </div>
              {prereqStatus.adapter.credentials_present?.length > 0 && (
                <div className="flex flex-wrap items-center gap-1">
                  <span className="text-gray-400">credentials present:</span>
                  {prereqStatus.adapter.credentials_present.map(ref => (
                    <Pill key={ref} color="green">{ref}</Pill>
                  ))}
                </div>
              )}
              {prereqStatus.adapter.credentials_missing?.length > 0 && (
                <div className="flex flex-wrap items-center gap-1">
                  <span className="text-gray-400">credentials missing:</span>
                  {prereqStatus.adapter.credentials_missing.map(ref => (
                    <Pill key={ref} color="red">{ref}</Pill>
                  ))}
                </div>
              )}
              {prereqStatus.blockers?.some(b => b.toLowerCase().includes('adapter') || b.toLowerCase().includes('command-seal')) && (
                <div className="text-red-300">
                  blocker: {prereqStatus.blockers.find(b => b.toLowerCase().includes('adapter') || b.toLowerCase().includes('command-seal'))}
                </div>
              )}
            </div>
          )}

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
            <label className="block text-xs text-gray-400">
              broker
              <select
                value={adapter.broker}
                onChange={e => setAdapter(a => ({ ...a, broker: e.target.value }))}
                className="mt-1 w-full bg-gray-950 border border-gray-700 rounded px-2 py-1 text-sm"
              >
                <option value="KALSHI">KALSHI</option>
              </select>
            </label>
            <Field label="adapter_name" value={adapter.adapter_name} onChange={v => setAdapter(a => ({ ...a, adapter_name: v }))} placeholder="RealKalshiLimitAdapter" />
            <Field label="limit_order_endpoint_label" value={adapter.limit_order_endpoint_label} onChange={v => setAdapter(a => ({ ...a, limit_order_endpoint_label: v }))} placeholder="kalshi-limit-order" />
            <Field label="endpoint_env_ref (base URL, optional)" value={adapter.endpoint_env_ref} onChange={v => setAdapter(a => ({ ...a, endpoint_env_ref: v }))} placeholder="KALSHI_API_BASE" />
            <Field label="adapter_module_path" value={adapter.adapter_module_path} onChange={v => setAdapter(a => ({ ...a, adapter_module_path: v }))} placeholder="predator_mesh/brokers/kalshi_livebrokerfirewall_adapter.py" />
            <Field label="adapter_descriptor_path" value={adapter.adapter_descriptor_path} onChange={v => setAdapter(a => ({ ...a, adapter_descriptor_path: v }))} placeholder="operator_authority_pack/firewall_adapter_descriptor.json" />
          </div>
          <label className="block text-xs text-gray-400">
            credential_reference_names (comma-separated env var names)
            <textarea
              value={adapter.credential_reference_names}
              onChange={e => setAdapter(a => ({ ...a, credential_reference_names: e.target.value }))}
              placeholder="KALSHI_API_KEY_ID,KALSHI_API_PRIVATE_KEY_PEM"
              rows={2}
              className="mt-1 w-full bg-gray-950 border border-gray-700 rounded px-2 py-1 text-sm"
            />
            <div className="text-xs text-gray-500 mt-1">
              Env-var names only — e.g. KALSHI_API_KEY_ID, KALSHI_API_PRIVATE_KEY_PEM, KALSHI_API_PRIVATE_KEY_PEM_PATH. Raw secrets are rejected.
            </div>
          </label>
          {adapterRefErrors().length > 0 && (
            <div className="text-xs text-red-300 space-y-0.5">
              {adapterRefErrors().map((err, i) => (
                <div key={i}>• {err}</div>
              ))}
            </div>
          )}
          <div className="space-y-1">
            <Check label="I confirm this is a real credentialed adapter" checked={adapter.operator_confirm_adapter_real} onChange={v => setAdapter(a => ({ ...a, operator_confirm_adapter_real: v }))} />
            <Check label="I confirm this is not a stub or test double" checked={adapter.operator_confirm_not_stub} onChange={v => setAdapter(a => ({ ...a, operator_confirm_not_stub: v }))} />
            <Check label="I confirm this adapter supports limit orders only" checked={adapter.operator_confirm_limit_only} onChange={v => setAdapter(a => ({ ...a, operator_confirm_limit_only: v }))} />
          </div>
          <label className="block text-xs text-gray-400">
            Typed confirmation
            <input
              value={adapter.typed_confirmation}
              onChange={e => setAdapter(a => ({ ...a, typed_confirmation: e.target.value }))}
              placeholder={ADAPTER_TYPED_CONFIRM}
              className="mt-1 w-full bg-gray-950 border border-gray-700 rounded px-2 py-1 text-sm"
            />
          </label>
          <div className="flex gap-2">
            <Btn k="adapterValidate" label="Validate" small onClick={() => call('adapterValidate', '/api/operator-control/external-prereqs/adapter/validate', { descriptor: buildAdapterDescriptor() })} />
            <Btn k="adapterSmoke" label="Smoke Check" small onClick={() => call('adapterSmoke', '/api/operator-control/external-prereqs/adapter/smoke', { descriptor: buildAdapterDescriptor() })} />
            <Btn k="adapterRegister" label="Register / Stage" small disabled={adapterRefErrors().length > 0} onClick={() => call('adapterRegister', '/api/operator-control/external-prereqs/adapter/register', { descriptor: buildAdapterDescriptor(), operator_confirm_adapter_real: adapter.operator_confirm_adapter_real, operator_confirm_not_stub: adapter.operator_confirm_not_stub, operator_confirm_limit_only: adapter.operator_confirm_limit_only, typed_confirmation: adapter.typed_confirmation })} />
          </div>
          <Out result={out.adapterValidate} />
          <Out result={out.adapterSmoke} />
          <Out result={out.adapterRegister} />
        </div>

        {/* live-submit card */}
        <div className="rounded p-3 border border-gray-700 bg-gray-800 space-y-3">
          <div className="flex items-center justify-between">
            <div className="font-semibold">5b. Live-Submit Config</div>
            <div className="flex gap-1">
              <StatusPill status={prereqStatus?.live_submit} field="enabled" />
              <StatusPill status={prereqStatus?.live_submit} field="valid" />
            </div>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
            <Check label="enabled" checked={liveSubmit.enabled} onChange={v => setLiveSubmit(s => ({ ...s, enabled: v }))} />
            <Field label="operator" value={liveSubmit.operator} onChange={v => setLiveSubmit(s => ({ ...s, operator: v }))} placeholder="operator name" />
            <Field label="reason" value={liveSubmit.reason} onChange={v => setLiveSubmit(s => ({ ...s, reason: v }))} placeholder="one controlled proof" />
            <Field label="expiry (ISO-8601)" value={liveSubmit.expiry} onChange={v => setLiveSubmit(s => ({ ...s, expiry: v }))} placeholder="2026-07-08T21:00:00Z" />
          </div>
          <label className="block text-xs text-gray-400">
            Typed confirmation
            <input
              value={liveSubmit.typed_confirmation}
              onChange={e => setLiveSubmit(s => ({ ...s, typed_confirmation: e.target.value }))}
              placeholder={LIVE_SUBMIT_TYPED_CONFIRM}
              className="mt-1 w-full bg-gray-950 border border-gray-700 rounded px-2 py-1 text-sm"
            />
          </label>
          <div className="flex gap-2">
            <Btn k="liveSubmitPreview" label="Preview" small onClick={() => call('liveSubmitPreview', '/api/operator-control/external-prereqs/live-submit/preview', liveSubmit)} />
            <Btn k="liveSubmitWrite" label="Write live_submit.json" small onClick={() => call('liveSubmitWrite', '/api/operator-control/external-prereqs/live-submit/write', liveSubmit)} />
            <Btn k="liveSubmitDisable" label="Relock / Disable" danger small onClick={() => call('liveSubmitDisable', '/api/operator-control/external-prereqs/live-submit/disable')} />
          </div>
          <Out result={out.liveSubmitPreview} />
          <Out result={out.liveSubmitWrite} />
          <Out result={out.liveSubmitDisable} />
        </div>

        {/* caps card */}
        <div className="rounded p-3 border border-gray-700 bg-gray-800 space-y-3">
          <div className="flex items-center justify-between">
            <div className="font-semibold">5c. Strict Caps Config</div>
            <div className="flex gap-1">
              <StatusPill status={prereqStatus?.caps} field="strict" />
              <StatusPill status={prereqStatus?.caps} field="valid" />
            </div>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
            <Field label="max_order_count" value={caps.max_order_count} onChange={v => setCaps(c => ({ ...c, max_order_count: v }))} type="number" />
            <Field label="max_order_size (cents)" value={caps.max_order_size} onChange={v => setCaps(c => ({ ...c, max_order_size: v }))} type="number" />
            <Field label="max_daily_loss (cents)" value={caps.max_daily_loss} onChange={v => setCaps(c => ({ ...c, max_daily_loss: v }))} type="number" />
            <Field label="max_open_exposure (cents)" value={caps.max_open_exposure} onChange={v => setCaps(c => ({ ...c, max_open_exposure: v }))} type="number" />
            <Field label="operator" value={caps.operator} onChange={v => setCaps(c => ({ ...c, operator: v }))} placeholder="operator name" />
            <Field label="reason" value={caps.reason} onChange={v => setCaps(c => ({ ...c, reason: v }))} placeholder="strict one-proof caps" />
            <Field label="expiry (ISO-8601)" value={caps.expiry} onChange={v => setCaps(c => ({ ...c, expiry: v }))} placeholder="2026-07-08T21:00:00Z" />
          </div>
          <div className="space-y-1">
            <Check label="order_type_policy = LIMIT_ONLY" checked={caps.order_type_policy === 'LIMIT_ONLY'} onChange={() => {}} />
            <Check label="market_orders_allowed = false" checked={!caps.market_orders_allowed} onChange={() => {}} />
            <Check label="kill_switch_enabled = true" checked={caps.kill_switch_enabled} onChange={() => {}} />
          </div>
          <label className="block text-xs text-gray-400">
            Typed confirmation
            <input
              value={caps.typed_confirmation}
              onChange={e => setCaps(c => ({ ...c, typed_confirmation: e.target.value }))}
              placeholder={CAPS_TYPED_CONFIRM}
              className="mt-1 w-full bg-gray-950 border border-gray-700 rounded px-2 py-1 text-sm"
            />
          </label>
          <div className="flex gap-2">
            <Btn k="capsPreview" label="Preview" small onClick={() => call('capsPreview', '/api/operator-control/external-prereqs/caps/preview', caps)} />
            <Btn k="capsWrite" label="Write caps.json" small onClick={() => call('capsWrite', '/api/operator-control/external-prereqs/caps/write', caps)} />
            <Btn k="capsRelock" label="Relock Caps" danger small onClick={() => call('capsRelock', '/api/operator-control/external-prereqs/caps/relock')} />
          </div>
          <Out result={out.capsPreview} />
          <Out result={out.capsWrite} />
          <Out result={out.capsRelock} />
        </div>
      </div>

      {/* live proof — hard gated */}
      <div className="rounded p-4 border-2 border-red-700 bg-red-950/30 space-y-3">
        <div className="font-bold text-red-300">6. One-Shot Live (REAL MONEY)</div>
        <p className="text-xs text-gray-300">
          Places at most one real limit order through LiveBrokerFirewall, then auto-locks. Only fires
          if the command seal is ready, all external prerequisites report ready, AND all three confirmations match exactly. Even armed, the appliance still fails closed at the seal.
        </p>
        {checkAll && !checkAll.ready && (
          <div className="text-xs text-red-300">
            External prerequisites not ready: {checkAll.blockers?.join('; ')}
          </div>
        )}
        <label className="block text-xs text-gray-400">
          DUMMY_LIVE_PROOF_MODE
          <input
            value={modeAck}
            onChange={e => setModeAck(e.target.value)}
            placeholder="type 1"
            className="mt-1 w-full bg-gray-950 border border-gray-700 rounded px-2 py-1 text-sm"
          />
        </label>
        <label className="block text-xs text-gray-400">
          DUMMY_LIVE_PROOF_ACK
          <input
            value={proofAck}
            onChange={e => setProofAck(e.target.value)}
            placeholder={PROOF_ACK}
            className="mt-1 w-full bg-gray-950 border border-gray-700 rounded px-2 py-1 text-sm"
          />
        </label>
        <label className="block text-xs text-gray-400">
          typed confirmation
          <input
            value={typedConfirm}
            onChange={e => setTypedConfirm(e.target.value)}
            placeholder={TYPED_CONFIRM}
            className="mt-1 w-full bg-gray-950 border border-gray-700 rounded px-2 py-1 text-sm"
          />
        </label>
        <label className="flex items-center gap-2 text-xs text-gray-300">
          <input type="checkbox" checked={armConfirmed} onChange={e => setArmConfirmed(e.target.checked)} />
          {TYPED_CONFIRM}
        </label>
        <Btn
          k="live"
          label="Execute one real proof"
          danger
          disabled={!armOk}
          onClick={() =>
            call('live', '/api/operator-control/one-shot-live', {
              live_proof_mode: modeAck,
              live_proof_ack: proofAck,
              typed_confirm: typedConfirm,
            })
          }
        />
        {!armOk && (
          <div className="text-xs text-gray-500">
            Type all three acks exactly, check the box, and resolve all external prerequisites to arm.
          </div>
        )}
        <Out result={out.live} />
      </div>
    </div>
  );
}
