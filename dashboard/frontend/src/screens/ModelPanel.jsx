import { useEffect, useState } from 'react';
import { fetchJson } from '../hooks/useApi';
import { booleanLabel, valueOrUnknown } from '../components/TruthValue';

const EXPECTED_MODELS = [
  {
    provider_alias: 'gemini_3_6_flash',
    display_name: 'Gemini 3.6 Flash',
    model: 'google/gemini-3.6-flash',
    role: 'Primary forecasting and structured data extraction',
  },
  {
    provider_alias: 'gpt_5_6_luna',
    display_name: 'GPT-5.6 Luna',
    model: 'openai/gpt-5.6-luna',
    role: 'Rapid structured forecasting and trade-draft challenge',
  },
  {
    provider_alias: 'claude_sonnet_5',
    display_name: 'Claude Sonnet 5',
    model: 'anthropic/claude-sonnet-5',
    role: 'Strategy critique, market thesis, and reflection',
  },
  {
    provider_alias: 'glm_5_2',
    display_name: 'GLM 5.2',
    model: 'z-ai/glm-5.2',
    role: 'Risk, no-trade, and calibration critique',
  },
];

export default function ModelPanel() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let active = true;
    fetchJson('/api/read-only/model-panel')
      .then(payload => {
        if (active) setData(payload);
      })
      .catch(reason => {
        if (active) setError(reason.message);
      });
    return () => { active = false; };
  }, []);

  if (error) {
    return (
      <div className="rounded-xl border border-red-700/70 bg-red-950/40 p-5 text-red-100">
        <h1 className="text-lg font-semibold">Model Panel unavailable</h1>
        <p className="mt-1 text-sm text-red-200">{error}</p>
        <p className="mt-3 text-xs text-red-300">
          No provider call was attempted by this screen. Status remains UNKNOWN until the local read-only endpoint is available.
        </p>
      </div>
    );
  }

  if (!data) return <LoadingState />;

  const configuration = data.panel_configuration || {};
  const credential = data.openrouter_access || {};
  const smoke = data.live_smoke || {};
  const authorities = data.authorities || {};
  const reportedModels = Array.isArray(data.models) ? data.models : [];
  const models = EXPECTED_MODELS.map(expected => {
    const reported = reportedModels.find(item => (
      item?.provider_alias === expected.provider_alias
      || item?.model === expected.model
      || item?.configured_model === expected.model
    ));
    return reported ? { ...expected, ...reported } : { ...expected, configuration_match: null, smoke: null };
  });
  const unexpectedModels = reportedModels.filter(item => !EXPECTED_MODELS.some(expected => (
    item?.provider_alias === expected.provider_alias
    || item?.model === expected.model
    || item?.configured_model === expected.model
  )));

  return (
    <div className="space-y-6 pb-8">
      <header className="overflow-hidden rounded-2xl border border-cyan-800/70 bg-gradient-to-br from-cyan-950/70 via-gray-900 to-gray-900 p-5 shadow-lg shadow-black/20 md:p-6">
        <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.22em] text-cyan-300">OpenRouter intelligence layer</p>
            <h1 className="mt-2 text-2xl font-bold tracking-tight text-white md:text-3xl">Four-model panel</h1>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-gray-300">
              Configuration and stored proof only. This page makes one local GET request; it never sends a prompt,
              contacts a model provider, changes configuration, or places an order.
            </p>
          </div>
          <div className="flex flex-wrap gap-2 md:max-w-xs md:justify-end">
            <StatusPill label="Data" value={data.data_status} />
            <BooleanPill
              label="Provider contacted by page"
              value={data.provider_contacted_by_dashboard}
              goodWhen={false}
              trueLabel="YES"
              falseLabel="NO"
            />
            <BooleanPill label="Exact panel" value={configuration.exact} goodWhen />
          </div>
        </div>
        <div className="mt-5 border-t border-cyan-900/70 pt-3 text-xs text-gray-400">
          Stored witness: <span className="font-mono text-gray-300">{valueOrUnknown(data.source?.smoke)}</span>
          <span className="mx-2 text-gray-700">•</span>
          Routing: <span className="font-mono text-gray-300">{valueOrUnknown(data.source?.routing)}</span>
        </div>
      </header>

      <section aria-labelledby="panel-roster-title" className="space-y-3">
        <div className="flex flex-wrap items-end justify-between gap-2">
          <div>
            <h2 id="panel-roster-title" className="text-lg font-semibold text-white">Intelligent routing roster</h2>
            <p className="mt-1 text-sm text-gray-400">Every route must match the expected provider, model, and assigned job.</p>
          </div>
          <BooleanPill label="Configuration exact" value={configuration.exact} goodWhen />
        </div>
        <div className="grid gap-4 xl:grid-cols-2">
          {models.map((model, index) => <ModelCard key={model.provider_alias} model={model} index={index} />)}
        </div>
        {unexpectedModels.length > 0 && (
          <div className="rounded-lg border border-red-700 bg-red-950/40 p-3 text-sm text-red-200">
            {unexpectedModels.length} unexpected model route{unexpectedModels.length === 1 ? '' : 's'} reported. Exact-panel status must remain blocked.
          </div>
        )}
      </section>

      <div className="grid gap-4 lg:grid-cols-3">
        <section aria-labelledby="credential-title" className="rounded-xl border border-gray-700 bg-gray-800/70 p-5">
          <SectionHeading eyebrow="Credential resolver" title="OpenRouter access" id="credential-title" />
          <div className="mt-4 rounded-lg border border-gray-700 bg-gray-950/60 p-4">
            <div className="flex items-center justify-between gap-3">
              <span className="text-sm text-gray-400">Credential present</span>
              <BooleanPill value={credential.present} goodWhen />
            </div>
            <div className="mt-3 font-mono text-lg tracking-[0.28em] text-gray-300" aria-label="Credential value redacted">
              {credential.present === true ? '••••••••••••' : credential.present === false ? 'NOT PRESENT' : 'UNKNOWN'}
            </div>
            <div className="mt-2 text-xs text-gray-500">
              {credential.redacted === true ? 'Value intentionally redacted' : 'Secret value is never returned by this endpoint'}
            </div>
          </div>
          <DefinitionList rows={[
            ['Resolver source', credential.source],
            ['Required variable', credential.required_env_name],
            ['Redacted', booleanLabel(credential.redacted)],
          ]} />
        </section>

        <section aria-labelledby="gate-title" className="rounded-xl border border-gray-700 bg-gray-800/70 p-5 lg:col-span-2">
          <SectionHeading eyebrow="Fail-closed controls" title="Two-key paid-call gate" id="gate-title" />
          <p className="mt-2 text-sm leading-6 text-gray-400">
            A persistent configuration gate and a separate runtime opt-in must both be true before scheduled background model calls can become effective.
          </p>
          <div className="mt-4 grid gap-3 sm:grid-cols-3">
            <GateCard
              step="1"
              label="Persistent config gate"
              value={configuration.configured_gate}
              detail="Stored configuration"
            />
            <GateCard
              step="2"
              label="Runtime opt-in"
              value={configuration.runtime_opt_in}
              detail={`${valueOrUnknown(configuration.runtime_opt_in_state)} · ${valueOrUnknown(configuration.runtime_opt_in_scope)}`}
            />
            <GateCard
              step="="
              label="Two-key gate result"
              value={configuration.two_key_paid_call_gate_open}
              detail={`${valueOrUnknown(configuration.gate_status)} · panel ready ${booleanLabel(configuration.background_panel_ready)}`}
              emphasized
            />
          </div>
        </section>
      </div>

      <section aria-labelledby="smoke-title" className="rounded-xl border border-gray-700 bg-gray-800/70 p-5">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <SectionHeading eyebrow="Stored evidence" title="Live-smoke witness" id="smoke-title" />
          <div className="flex flex-wrap gap-2">
            <StatusPill label="Verdict" value={smoke.verdict || smoke.status} />
            <BooleanPill label="Fresh" value={smoke.fresh} goodWhen />
            <BooleanPill label="Exact panel" value={smoke.exact_panel} goodWhen />
          </div>
        </div>
        <p className="mt-2 text-sm text-gray-400">
          The dashboard reads a previously stored, redacted witness. It does not rerun the smoke test.
        </p>
        <div className="mt-4 grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-6">
          <Metric label="Models proven" value={fraction(smoke.models_proven, 4)} />
          <Metric label="Calls attempted" value={fraction(smoke.calls_attempted, smoke.call_cap)} />
          <Metric label="Witness age" value={formatAge(smoke.age_seconds)} />
          <Metric label="Schema valid" value={booleanLabel(smoke.schema_valid)} />
          <Metric label="All models live" value={booleanLabel(smoke.all_models_live_proven)} />
          <Metric label="Reported cost" value={formatCost(smoke.total_reported_cost_usd)} />
        </div>
        <DefinitionList rows={[
          ['Generated at', formatTimestamp(smoke.generated_at)],
          ['Stored status', smoke.status],
        ]} compact />
        <Blockers blockers={smoke.blockers} />
      </section>

      <section aria-labelledby="authority-title" className="rounded-xl border border-emerald-900/80 bg-emerald-950/20 p-5">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
          <SectionHeading eyebrow="Separation of powers" title="Authority remains disabled" id="authority-title" />
          <p className="text-xs text-emerald-300">A key or smoke PASS does not confer authority.</p>
        </div>
        <div className="mt-4 grid gap-3 md:grid-cols-3">
          <AuthorityCard
            label="Evidence authority"
            value={authorities.evidence}
            detail="Stored model output cannot promote research evidence."
          />
          <AuthorityCard
            label="Probability authority"
            value={authorities.probability}
            detail="Operational probability weight remains zero."
          />
          <AuthorityCard
            label="Order authority"
            value={authorities.order}
            detail="Broker execution remains behind the separate live firewall."
          />
        </div>
      </section>
    </div>
  );
}

function LoadingState() {
  return (
    <div className="space-y-4" aria-live="polite" aria-busy="true">
      <div className="h-44 animate-pulse rounded-2xl bg-gray-800" />
      <div className="grid gap-4 xl:grid-cols-2">
        {[0, 1, 2, 3].map(item => <div key={item} className="h-52 animate-pulse rounded-xl bg-gray-800" />)}
      </div>
      <span className="sr-only">Loading model panel status</span>
    </div>
  );
}

function ModelCard({ model, index }) {
  const smoke = model.smoke || {};
  const fallbackRole = EXPECTED_MODELS[index]?.role;
  const role = model.role || fallbackRole;
  return (
    <article className="rounded-xl border border-gray-700 bg-gray-800/70 p-4 transition-colors hover:border-gray-600">
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-cyan-950 text-xs font-bold text-cyan-300">
              {index + 1}
            </span>
            <h3 className="truncate font-semibold text-white">{valueOrUnknown(model.display_name)}</h3>
          </div>
          <div className="mt-2 break-all font-mono text-xs text-cyan-300">{valueOrUnknown(model.model)}</div>
        </div>
        <BooleanPill label="Route match" value={model.configuration_match} goodWhen />
      </div>
      <p className="mt-4 min-h-10 text-sm leading-5 text-gray-300">{valueOrUnknown(role)}</p>
      <p className="mt-1 text-xs text-gray-500">Task: <span className="font-mono">{valueOrUnknown(model.task)}</span></p>
      <div className="mt-4 grid grid-cols-2 gap-x-4 gap-y-2 border-t border-gray-700 pt-3 text-xs">
        <Fact label="Alias" value={model.provider_alias} mono />
        <Fact label="Route" value={model.route_mode} />
        <Fact label="Reasoning" value={model.reasoning_effort} />
        <Fact label="Configured slug" value={model.configured_model} mono />
      </div>
      <div className="mt-4 flex flex-wrap items-center gap-2 rounded-lg bg-gray-950/50 p-3">
        <StatusPill label="Smoke" value={smoke.status} />
        <BooleanPill label="Identity" value={smoke.identity_ok} goodWhen />
        <BooleanPill label="Schema" value={smoke.schema_ok} goodWhen />
        <span className="ml-auto text-xs text-gray-400">
          {formatLatency(smoke.latency_ms)} · HTTP {valueOrUnknown(smoke.http_status)}
        </span>
      </div>
    </article>
  );
}

function GateCard({ step, label, value, detail, emphasized = false }) {
  return (
    <div className={`rounded-lg border p-4 ${emphasized ? 'border-cyan-800 bg-cyan-950/30' : 'border-gray-700 bg-gray-950/40'}`}>
      <div className="flex items-start justify-between gap-2">
        <span className="flex h-6 min-w-6 items-center justify-center rounded-full bg-gray-800 px-1 text-xs font-bold text-gray-300">{step}</span>
        <BooleanPill value={value} goodWhen />
      </div>
      <div className="mt-3 text-sm font-semibold text-white">{label}</div>
      <div className="mt-1 break-words text-xs text-gray-400">{valueOrUnknown(detail)}</div>
    </div>
  );
}

function AuthorityCard({ label, value, detail }) {
  const safe = value === false;
  const unknown = value !== true && value !== false;
  const classes = unknown
    ? 'border-amber-800 bg-amber-950/30'
    : safe
      ? 'border-emerald-800 bg-emerald-950/30'
      : 'border-red-700 bg-red-950/50';
  return (
    <div className={`rounded-lg border p-4 ${classes}`}>
      <div className="flex items-center justify-between gap-3">
        <h3 className="text-sm font-semibold text-white">{label}</h3>
        <BooleanPill value={value} goodWhen={false} trueLabel="TRUE" falseLabel="FALSE" />
      </div>
      <p className="mt-3 text-xs leading-5 text-gray-300">{detail}</p>
      <p className="mt-2 text-[11px] font-semibold uppercase tracking-wide text-gray-500">Required state: FALSE</p>
    </div>
  );
}

function SectionHeading({ eyebrow, title, id }) {
  return (
    <div>
      <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-gray-500">{eyebrow}</p>
      <h2 id={id} className="mt-1 text-lg font-semibold text-white">{title}</h2>
    </div>
  );
}

function Metric({ label, value }) {
  return (
    <div className="rounded-lg border border-gray-700 bg-gray-950/40 p-3">
      <div className="text-[11px] uppercase tracking-wide text-gray-500">{label}</div>
      <div className="mt-1 break-words text-base font-semibold text-white">{valueOrUnknown(value)}</div>
    </div>
  );
}

function DefinitionList({ rows, compact = false }) {
  return (
    <dl className={`${compact ? 'mt-3 grid gap-x-8 sm:grid-cols-2' : 'mt-4'} divide-y divide-gray-700/70 text-sm`}>
      {rows.map(([label, value]) => (
        <div key={label} className="flex items-start justify-between gap-4 py-2">
          <dt className="text-gray-500">{label}</dt>
          <dd className="break-all text-right font-mono text-gray-300">{String(valueOrUnknown(value))}</dd>
        </div>
      ))}
    </dl>
  );
}

function Fact({ label, value, mono = false }) {
  return (
    <div className="min-w-0">
      <div className="text-gray-500">{label}</div>
      <div className={`mt-0.5 break-all text-gray-300 ${mono ? 'font-mono' : ''}`}>{valueOrUnknown(value)}</div>
    </div>
  );
}

function Blockers({ blockers }) {
  if (!Array.isArray(blockers)) {
    return <p className="mt-3 text-xs font-semibold text-amber-300">Blocker status: UNKNOWN</p>;
  }
  if (blockers.length === 0) {
    return <p className="mt-3 text-xs text-gray-400">No smoke-evidence blockers reported.</p>;
  }
  return (
    <div className="mt-4 rounded-lg border border-amber-800 bg-amber-950/30 p-3">
      <h3 className="text-xs font-semibold uppercase tracking-wide text-amber-300">Stored witness blockers</h3>
      <ul className="mt-2 space-y-1 text-sm text-amber-100">
        {blockers.map((blocker, index) => <li key={`${index}-${blocker}`}>• {String(blocker)}</li>)}
      </ul>
    </div>
  );
}

function BooleanPill({ label, value, goodWhen = true, trueLabel = 'YES', falseLabel = 'NO' }) {
  const unknown = value !== true && value !== false;
  const good = !unknown && value === goodWhen;
  const classes = unknown
    ? 'border-amber-700/70 bg-amber-950/50 text-amber-200'
    : good
      ? 'border-emerald-700/70 bg-emerald-950/50 text-emerald-200'
      : 'border-red-700/70 bg-red-950/50 text-red-200';
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-semibold uppercase tracking-wide ${classes}`}>
      {label && <span className="font-normal normal-case tracking-normal opacity-75">{label}</span>}
      {booleanLabel(value, trueLabel, falseLabel)}
    </span>
  );
}

function StatusPill({ label, value }) {
  const normalized = typeof value === 'string' ? value.trim().toUpperCase() : '';
  const positive = ['PASS', 'SUCCESS', 'PROVEN', 'READY', 'FRESH'].some(token => normalized.includes(token));
  const negative = ['FAIL', 'ERROR', 'BLOCKED', 'STALE', 'INVALID', 'MISMATCH'].some(token => normalized.includes(token));
  const classes = positive
    ? 'border-emerald-700/70 bg-emerald-950/50 text-emerald-200'
    : negative
      ? 'border-red-700/70 bg-red-950/50 text-red-200'
      : 'border-gray-600 bg-gray-900 text-gray-300';
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-semibold uppercase tracking-wide ${classes}`}>
      {label && <span className="font-normal normal-case tracking-normal opacity-75">{label}</span>}
      {String(valueOrUnknown(value))}
    </span>
  );
}

function fraction(value, total) {
  if (value === null || value === undefined) return 'UNKNOWN';
  return total === null || total === undefined ? String(value) : `${value} / ${total}`;
}

function formatAge(seconds) {
  if (seconds === null || seconds === undefined || !Number.isFinite(Number(seconds))) return 'UNKNOWN';
  const total = Math.max(0, Number(seconds));
  if (total < 60) return `${Math.round(total)}s`;
  if (total < 3600) return `${Math.round(total / 60)}m`;
  if (total < 86400) return `${(total / 3600).toFixed(1)}h`;
  return `${(total / 86400).toFixed(1)}d`;
}

function formatTimestamp(value) {
  if (!value) return 'UNKNOWN';
  const timestamp = new Date(value);
  return Number.isNaN(timestamp.getTime()) ? String(value) : timestamp.toLocaleString();
}

function formatLatency(value) {
  if (value === null || value === undefined || !Number.isFinite(Number(value))) return 'UNKNOWN latency';
  return `${Math.round(Number(value))} ms`;
}

function formatCost(value) {
  if (value === null || value === undefined || !Number.isFinite(Number(value))) return 'UNKNOWN';
  return `$${Number(value).toFixed(6)}`;
}
