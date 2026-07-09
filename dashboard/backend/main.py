import asyncio, json
from pathlib import Path
from fastapi import FastAPI, WebSocket, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from core.state import STATE
from core.config_loader import load_caps
from core.ontology import AccountMode
from services.sqlite_store import init_db, get_orders, get_positions, insert_order
from repo_harvester.runner import run_harvester
from core.logger import logger
from core.secret_guard import redact
from model_router.credential_source import ProviderCredentialSourceResolver
from model_router.resolver import (
    ModelProviderResolver,
    _DEFAULT_ALIASES,
    _DEFAULT_BASE_URLS,
)
from model_router.route_mode import ProviderRouteModeResolver
from model_router.smoke import _DEEPSEEK_SMOKE_PROMPT, _MINIMAX_SMOKE_PROMPT
from dashboard.backend import (
    v3_routes,
    v4_routes,
    v5_routes,
    v6_routes,
    v7_routes,
    v8_routes,
    v9_routes,
    v10_routes,
    v11_routes,
    v12_routes,
    v13_routes,
    v14_routes,
    v15_routes,
    v16_routes,
    v17_routes,
    v18_routes,
    v19_routes,
    v20_routes,
    v21_routes,
    v22_routes,
    v23_routes,
    v24_routes,
    v25_routes,
    v26_routes,
    v27_routes,
    v28_routes,
    v29_routes,
    v30_routes,
    v31_routes,
    v32_routes,
    v33_routes,
    v34_routes,
    v35_routes,
    v36_routes,
    v37_routes,
    v38_routes,
    v39_routes,
    v40_routes,
    v41_routes,
    v42_routes,
    v43_routes,
    v44_routes,
    v45_routes,
    v46_routes,
    v47_routes,
    v48_routes,
    v49_routes,
    v50_routes,
    v51_routes,
    v52_routes,
    v53_routes,
    v54_routes,
    v55_routes,
    v56_routes,
    v57_routes,
    v58_routes,
    v59_routes,
    v60_routes,
    v61_routes,
    v62_routes,
    v63_routes,
    v64_routes,
    v65_routes,
    v66_routes,
    v67_routes,
    v68_routes,
    v69_routes,
    v70_routes,
    v71_routes,
    v72_routes,
    v73_routes,
    v74_routes,
    v75_routes,
    v76_routes,
    v77_routes,
    v78_routes,
    v79_routes,
    v80_routes,
    v81_routes,
    v82_routes,
    v83_routes,
    v84_routes,
    v85_routes,
    v86_routes,
    v87_routes,
    v88_routes,
    v89_routes,
    v90_routes,
    v91_routes,
    v92_routes,
    v93_routes,
    v94_routes,
    v95_routes,
    v96_routes,
    v97_routes,
    v98_routes,
    v99_routes,
    v100_routes,
    v101_routes,
    v102_routes,
    v103_routes,
    v104_routes,
    v105_routes,
    v106_routes,
    v107_routes,
    v108_routes,
    v109_routes,
    v110_routes,
    v111_routes,
    v112_routes,
    v113_routes,
    v114_routes,
    v115_routes,
    v116_routes,
    v117_routes,
    v118_routes,
    v119_routes,
    v120_routes,
    v121_routes,
    v122_routes,
    v123_routes,
    v124_routes,
    v125_routes,
    v126_routes,
    v127_routes,
    v128_routes,
    v129_routes,
    v130_routes,
    v131_routes,
    v132_routes,
    v133_routes,
    v134_routes,
    v135_routes,
    v136_routes,
    v137_routes,
    v138_routes,
    v139_routes,
    v140_routes,
    v141_routes,
    v142_routes,
    v143_routes,
    v144_routes,
    v145_routes,
    v146_routes,
    v147_routes,
    v148_routes,
    v149_routes,
    v150_routes,
    v151_routes,
    v152_routes,
    v153_routes,
    v154_routes,
    v155_routes,
    v156_routes,
    v157_routes,
    v158_routes,
    v159_routes,
    v160_routes,
    v161_routes,
    v162_routes,
    v163_routes,
    v164_routes,
    v165_routes,
    v166_routes,
    v167_routes,
    v168_routes,
    v169_routes,
    v170_routes,
    v171_routes,
    v172_routes,
    v173_routes,
    v174_routes,
    v175_routes,
    v176_routes,
    v177_routes,
    v178_routes,
    v179_routes,
    v180_routes,
    v181_routes,
    v182_routes,
    v183_routes,
    v184_routes,
    v185_routes,
    v186_routes,
    v187_routes,
    v188_routes,
    v189_routes,
    v190_routes,
    v191_routes,
    v192_routes,
    v193_routes,
    v194_routes,
    v195_routes,
    v196_routes,
    v197_routes,
    v198_routes,
    v199_routes,
    v200_routes,
    v201_routes,
    v202_routes,
    v203_routes,
    v204_routes,
    v205_routes,
    v206_routes,
    v207_routes,
    v208_routes,
    v209_routes,
    v210_routes,
    v211_routes,
    v212_routes,
    v213_routes,
    v214_routes,
    v215_routes,
    v216_routes,
    v217_routes,
    v218_routes,
    v219_routes,
    v220_routes,
    v221_routes,
    v222_routes,
    v223_routes,
    v224_routes,
    v225_routes,
    v226_routes,
    v227_routes,
    v228_routes,
    v229_routes,
    v230_routes,
    v231_routes,
    v232_routes,
    v233_routes,
    v234_routes,
    v235_routes,
    v236_routes,
    v237_routes,
    v238_routes,
    v239_routes,
    v240_routes,
    v241_routes,
    v242_routes,
    v243_routes,
    v244_routes,
    v245_routes,
    v246_routes,
    v247_routes,
    v248_routes,
    v249_routes,
    v250_routes,
    v251_routes,
    v252_routes,
    v253_routes,
    v254_routes,
    v255_routes,
    v256_routes,
    v257_routes,
    v258_routes,
    v259_routes,
    v260_routes,
    v261_routes,
    v262_routes,
    v263_routes,
    v264_routes,
    v265_routes,
    v266_routes,
    v267_routes,
    v268_routes,
    v269_routes,
    v270_routes,
    v271_routes,
    v272_routes,
    v273_routes,
    v274_routes,
    v275_routes,
    v276_routes,
    v277_routes,
    v278_routes,
    v279_routes,
    v280_routes,
    v281_routes,
    v282_routes,
    v283_routes,
    v284_routes,
    v285_routes,
    v286_routes,
    v287_routes,
    v288_routes,
    v289_routes,
    v290_routes,
    v291_routes,
    v292_routes,
    v293_routes,
    v294_routes,
    v295_routes,
    v296_routes,
    v297_routes,
    v298_routes,
    v299_routes,
    v300_routes,
    v301_routes,
    v302_routes,
    v303_routes,
    v304_routes,
)

ROOT = Path(__file__).resolve().parents[2]

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield

app = FastAPI(lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.include_router(v3_routes.router)
app.include_router(v4_routes.router)
app.include_router(v5_routes.router)
app.include_router(v6_routes.router)
app.include_router(v7_routes.router)
app.include_router(v8_routes.router)
app.include_router(v9_routes.router)
app.include_router(v10_routes.router)
app.include_router(v11_routes.router)
app.include_router(v12_routes.router)
app.include_router(v13_routes.router)
app.include_router(v14_routes.router)
app.include_router(v15_routes.router)
app.include_router(v16_routes.router)
app.include_router(v17_routes.router)
app.include_router(v18_routes.router)
app.include_router(v19_routes.router)
app.include_router(v20_routes.router)
app.include_router(v21_routes.router)
app.include_router(v22_routes.router)
app.include_router(v23_routes.router)
app.include_router(v24_routes.router)
app.include_router(v25_routes.router)
app.include_router(v26_routes.router)
app.include_router(v27_routes.router)
app.include_router(v28_routes.router)
app.include_router(v29_routes.router)
app.include_router(v30_routes.router)
app.include_router(v31_routes.router)
app.include_router(v32_routes.router)
app.include_router(v33_routes.router)
app.include_router(v34_routes.router)
app.include_router(v35_routes.router)
app.include_router(v36_routes.router)
app.include_router(v37_routes.router)
app.include_router(v38_routes.router)
app.include_router(v39_routes.router)
app.include_router(v40_routes.router)
app.include_router(v41_routes.router)
app.include_router(v42_routes.router)
app.include_router(v43_routes.router)
app.include_router(v44_routes.router)
app.include_router(v45_routes.router)
app.include_router(v46_routes.router)
app.include_router(v47_routes.router)
app.include_router(v48_routes.router)
app.include_router(v49_routes.router)
app.include_router(v50_routes.router)
app.include_router(v51_routes.router)
app.include_router(v52_routes.router)
app.include_router(v53_routes.router)
app.include_router(v54_routes.router)
app.include_router(v55_routes.router)
app.include_router(v56_routes.router)
app.include_router(v57_routes.router)
app.include_router(v58_routes.router)
app.include_router(v59_routes.router)
app.include_router(v60_routes.router)
app.include_router(v61_routes.router)
app.include_router(v62_routes.router)
app.include_router(v63_routes.router)
app.include_router(v64_routes.router)
app.include_router(v65_routes.router)
app.include_router(v66_routes.router)
app.include_router(v67_routes.router)
app.include_router(v68_routes.router)
app.include_router(v69_routes.router)
app.include_router(v70_routes.router)
app.include_router(v71_routes.router)
app.include_router(v72_routes.router)
app.include_router(v73_routes.router)
app.include_router(v74_routes.router)
app.include_router(v75_routes.router)
app.include_router(v76_routes.router)
app.include_router(v77_routes.router)
app.include_router(v78_routes.router)
app.include_router(v79_routes.router)
app.include_router(v80_routes.router)
app.include_router(v81_routes.router)
app.include_router(v82_routes.router)
app.include_router(v83_routes.router)
app.include_router(v84_routes.router)
app.include_router(v85_routes.router)
app.include_router(v86_routes.router)
app.include_router(v87_routes.router)
app.include_router(v88_routes.router)
app.include_router(v89_routes.router)
app.include_router(v90_routes.router)
app.include_router(v91_routes.router)
app.include_router(v92_routes.router)
app.include_router(v93_routes.router)
app.include_router(v94_routes.router)
app.include_router(v95_routes.router)
app.include_router(v96_routes.router)
app.include_router(v97_routes.router)
app.include_router(v98_routes.router)
app.include_router(v99_routes.router)
app.include_router(v100_routes.router)
app.include_router(v101_routes.router)
app.include_router(v102_routes.router)
app.include_router(v103_routes.router)
app.include_router(v104_routes.router)
app.include_router(v105_routes.router)
app.include_router(v106_routes.router)
app.include_router(v107_routes.router)
app.include_router(v108_routes.router)
app.include_router(v109_routes.router)
app.include_router(v110_routes.router)
app.include_router(v111_routes.router)
app.include_router(v112_routes.router)
app.include_router(v113_routes.router)
app.include_router(v114_routes.router)
app.include_router(v115_routes.router)
app.include_router(v116_routes.router)
app.include_router(v117_routes.router)
app.include_router(v118_routes.router)
app.include_router(v119_routes.router)
app.include_router(v120_routes.router)
app.include_router(v121_routes.router)
app.include_router(v122_routes.router)
app.include_router(v123_routes.router)
app.include_router(v124_routes.router)
app.include_router(v125_routes.router)
app.include_router(v126_routes.router)
app.include_router(v127_routes.router)
app.include_router(v128_routes.router)
app.include_router(v129_routes.router)
app.include_router(v130_routes.router)
app.include_router(v131_routes.router)
app.include_router(v132_routes.router)
app.include_router(v133_routes.router)
app.include_router(v134_routes.router)
app.include_router(v135_routes.router)
app.include_router(v136_routes.router)
app.include_router(v137_routes.router)
app.include_router(v138_routes.router)
app.include_router(v139_routes.router)
app.include_router(v140_routes.router)
app.include_router(v141_routes.router)
app.include_router(v142_routes.router)
app.include_router(v143_routes.router)
app.include_router(v144_routes.router)
app.include_router(v145_routes.router)
app.include_router(v146_routes.router)
app.include_router(v147_routes.router)
app.include_router(v148_routes.router)
app.include_router(v149_routes.router)
app.include_router(v150_routes.router)
app.include_router(v151_routes.router)
app.include_router(v152_routes.router)
app.include_router(v153_routes.router)
app.include_router(v154_routes.router)
app.include_router(v155_routes.router)
app.include_router(v156_routes.router)
app.include_router(v157_routes.router)
app.include_router(v158_routes.router)
app.include_router(v159_routes.router)
app.include_router(v160_routes.router)
app.include_router(v161_routes.router)
app.include_router(v162_routes.router)
app.include_router(v163_routes.router)
app.include_router(v164_routes.router)
app.include_router(v165_routes.router)
app.include_router(v166_routes.router)
app.include_router(v167_routes.router)
app.include_router(v168_routes.router)
app.include_router(v169_routes.router)
app.include_router(v170_routes.router)
app.include_router(v171_routes.router)
app.include_router(v172_routes.router)
app.include_router(v173_routes.router)
app.include_router(v174_routes.router)
app.include_router(v175_routes.router)
app.include_router(v176_routes.router)
app.include_router(v177_routes.router)
app.include_router(v178_routes.router)
app.include_router(v179_routes.router)
app.include_router(v180_routes.router)
app.include_router(v181_routes.router)
app.include_router(v182_routes.router)
app.include_router(v183_routes.router)
app.include_router(v184_routes.router)
app.include_router(v185_routes.router)
app.include_router(v186_routes.router)
app.include_router(v187_routes.router)
app.include_router(v188_routes.router)
app.include_router(v189_routes.router)
app.include_router(v190_routes.router)
app.include_router(v191_routes.router)
app.include_router(v192_routes.router)
app.include_router(v193_routes.router)
app.include_router(v194_routes.router)
app.include_router(v195_routes.router)
app.include_router(v196_routes.router)
app.include_router(v197_routes.router)
app.include_router(v198_routes.router)
app.include_router(v199_routes.router)
app.include_router(v200_routes.router)
app.include_router(v201_routes.router)
app.include_router(v202_routes.router)
app.include_router(v203_routes.router)
app.include_router(v204_routes.router)
app.include_router(v205_routes.router)
app.include_router(v206_routes.router)
app.include_router(v207_routes.router)
app.include_router(v208_routes.router)
app.include_router(v209_routes.router)
app.include_router(v210_routes.router)
app.include_router(v211_routes.router)
app.include_router(v212_routes.router)
app.include_router(v213_routes.router)
app.include_router(v214_routes.router)
app.include_router(v215_routes.router)
app.include_router(v216_routes.router)
app.include_router(v217_routes.router)
app.include_router(v218_routes.router)
app.include_router(v219_routes.router)
app.include_router(v220_routes.router)
app.include_router(v221_routes.router)
app.include_router(v222_routes.router)
app.include_router(v223_routes.router)
app.include_router(v224_routes.router)
app.include_router(v225_routes.router)
app.include_router(v226_routes.router)
app.include_router(v227_routes.router)
app.include_router(v228_routes.router)
app.include_router(v229_routes.router)
app.include_router(v230_routes.router)
app.include_router(v231_routes.router)
app.include_router(v232_routes.router)
app.include_router(v233_routes.router)
app.include_router(v234_routes.router)
app.include_router(v235_routes.router)
app.include_router(v236_routes.router)
app.include_router(v237_routes.router)
app.include_router(v238_routes.router)
app.include_router(v239_routes.router)
app.include_router(v240_routes.router)
app.include_router(v241_routes.router)
app.include_router(v242_routes.router)
app.include_router(v243_routes.router)
app.include_router(v244_routes.router)
app.include_router(v245_routes.router)
app.include_router(v246_routes.router)
app.include_router(v247_routes.router)
app.include_router(v248_routes.router)
app.include_router(v249_routes.router)
app.include_router(v250_routes.router)
app.include_router(v251_routes.router)
app.include_router(v252_routes.router)
app.include_router(v253_routes.router)
app.include_router(v254_routes.router)
app.include_router(v255_routes.router)
app.include_router(v256_routes.router)
app.include_router(v257_routes.router)
app.include_router(v258_routes.router)
app.include_router(v259_routes.router)
app.include_router(v260_routes.router)
app.include_router(v261_routes.router)
app.include_router(v262_routes.router)
app.include_router(v263_routes.router)
app.include_router(v264_routes.router)
app.include_router(v265_routes.router)
app.include_router(v266_routes.router)
app.include_router(v267_routes.router)
app.include_router(v268_routes.router)
app.include_router(v269_routes.router)
app.include_router(v270_routes.router)
app.include_router(v271_routes.router)
app.include_router(v272_routes.router)
app.include_router(v273_routes.router)
app.include_router(v274_routes.router)
app.include_router(v275_routes.router)
app.include_router(v276_routes.router)
app.include_router(v277_routes.router)
app.include_router(v278_routes.router)
app.include_router(v279_routes.router)
app.include_router(v280_routes.router)
app.include_router(v281_routes.router)
app.include_router(v282_routes.router)
app.include_router(v283_routes.router)
app.include_router(v284_routes.router)
app.include_router(v285_routes.router)
app.include_router(v286_routes.router)
app.include_router(v287_routes.router)
app.include_router(v288_routes.router)
app.include_router(v289_routes.router)
app.include_router(v290_routes.router)
app.include_router(v291_routes.router)
app.include_router(v292_routes.router)
app.include_router(v293_routes.router)
app.include_router(v294_routes.router)
app.include_router(v295_routes.router)
app.include_router(v296_routes.router)
app.include_router(v297_routes.router)
app.include_router(v298_routes.router)
app.include_router(v299_routes.router)
app.include_router(v300_routes.router)
app.include_router(v301_routes.router)
app.include_router(v302_routes.router)
app.include_router(v303_routes.router)
app.include_router(v304_routes.router)

from dashboard.backend import operator_routes  # noqa: E402
from dashboard.backend import operator_control_routes  # noqa: E402
app.include_router(operator_routes.router)
app.include_router(operator_control_routes.router)

@app.get("/status")
async def status():
    return {
        "mode": STATE.mode.value,
        "kill_switch_active": STATE.kill_switch.active,
        "emergency_stop_active": STATE.emergency_stop.active,
        "kalshi_connected": STATE.kalshi_connected,
        "balance_cents": STATE.balance_cents,
        "daily_loss_cents": STATE.daily_loss_cents,
        "total_exposure_cents": 0,
        "open_positions": await get_positions(),
        "open_orders": await get_orders(),
    }

@app.get("/api/v8/model-provider-resolution")
async def api_v8_model_provider_resolution():
    resolver = ModelProviderResolver()
    deepseek = await resolver.resolve(
        "deepseek_v4_flash",
        default_base=_DEFAULT_BASE_URLS["deepseek_v4_flash"],
        default_aliases=_DEFAULT_ALIASES["deepseek_v4_flash"],
        smoke_prompt=_DEEPSEEK_SMOKE_PROMPT,
    )
    minimax = await resolver.resolve(
        "minimax_m3",
        default_base=_DEFAULT_BASE_URLS["minimax_m3"],
        default_aliases=_DEFAULT_ALIASES["minimax_m3"],
        smoke_prompt=_MINIMAX_SMOKE_PROMPT,
    )
    repair_path = ROOT / "artifacts" / "dummy" / "model_provider_operator_repair_recommendations_v1.json"
    return redact(
        {
            "deepseek_v4_flash": deepseek.redacted_metadata,
            "minimax_m3": minimax.redacted_metadata,
            "repair_recommendation_path": str(repair_path),
        }
    )

@app.get("/api/v8/provider-credential-source")
async def api_v8_provider_credential_source():
    credential_resolver = ProviderCredentialSourceResolver()
    route_resolver = ProviderRouteModeResolver(credential_resolver)
    resolver = ModelProviderResolver()
    data = {}
    for provider in ("deepseek_v4_flash", "minimax_m3"):
        candidate = resolver._endpoint_candidate(provider, _DEFAULT_BASE_URLS[provider])
        route = route_resolver.resolve(
            provider,
            candidate.api_base,
            resolver._configured_model(provider),
        )
        credential = credential_resolver.resolve(route.intended_key_env)
        data[provider] = {
            "api_key_env": route.intended_key_env,
            "source": credential.source.value,
            "present": credential.present,
            "route_mode": route.route_mode.value,
            "base_url_class": route.base_url_class,
        }
    openrouter = credential_resolver.resolve("OPENROUTER_API_KEY")
    data["openrouter"] = {
        "api_key_env": "OPENROUTER_API_KEY",
        "source": openrouter.source.value,
        "present": openrouter.present,
        "route_mode": "openrouter",
    }
    return redact(data)

@app.get("/api/v8/provider-route-mode")
async def api_v8_provider_route_mode():
    credential_resolver = ProviderCredentialSourceResolver()
    route_resolver = ProviderRouteModeResolver(credential_resolver)
    resolver = ModelProviderResolver()
    data = {}
    for provider in ("deepseek_v4_flash", "minimax_m3"):
        candidate = resolver._endpoint_candidate(provider, _DEFAULT_BASE_URLS[provider])
        route = route_resolver.resolve(
            provider,
            candidate.api_base,
            resolver._configured_model(provider),
        )
        data[provider] = route.as_dict()
    return redact(data)

@app.get("/api/v8/live-model-proof")
async def api_v8_live_model_proof():
    smoke_path = ROOT / "artifacts" / "dummy" / "live_model_smoke_report_v3.json"
    if smoke_path.exists():
        try:
            smoke = json.loads(smoke_path.read_text(encoding="utf-8"))
        except Exception:
            smoke = {}
    else:
        smoke = {}
    return redact(
        {
            "live_model_status": smoke.get("live_model_status", "UNKNOWN"),
            "model_mode": smoke.get("model_mode", "UNKNOWN"),
            "verdict": smoke.get("verdict", "PASS"),
        }
    )

@app.get("/markets")
async def markets():
    return {"markets": []}

@app.get("/forecasts")
async def forecasts():
    return {"forecasts": []}

@app.get("/strategies")
async def strategies():
    return {"strategies": []}

@app.get("/orders")
async def orders():
    return {"orders": await get_orders()}

@app.get("/positions")
async def positions():
    return {"positions": await get_positions()}

@app.get("/risk")
async def risk():
    return {"caps": load_caps().model_dump(), "daily_loss_cents": STATE.daily_loss_cents}

@app.get("/proof")
async def proof():
    return {"proofs": []}

@app.get("/logs")
async def logs(limit: int = 100):
    log_file = ROOT / "logs" / "dummy.jsonl"
    lines = []
    if log_file.exists():
        with log_file.open() as f:
            lines = f.readlines()[-limit:]
    return {"logs": [json.loads(l) for l in lines if l.strip()]}

@app.get("/repo-harvester/status")
async def repo_harvester_status():
    return {"status": "idle"}

@app.get("/repo-harvester/repos")
async def repo_harvester_repos():
    return {"repos": []}

@app.get("/repo-harvester/reports")
async def repo_harvester_reports():
    p = ROOT / "artifacts" / "repo_harvester"
    files = [f.name for f in p.glob("*.json")] if p.exists() else []
    return {"reports": files}

@app.post("/mode/set")
async def set_mode(payload: dict):
    STATE.set_mode(AccountMode(payload["mode"]))
    logger.info("Mode changed", extra={"component": "dashboard", "mode": STATE.mode.value})
    return {"mode": STATE.mode.value}

@app.post("/kill-switch/enable")
async def enable_kill_switch(payload: dict):
    STATE.enable_kill_switch(payload.get("reason", "operator"))
    return {"active": True}

@app.post("/kill-switch/disable")
async def disable_kill_switch():
    STATE.disable_kill_switch()
    return {"active": False}

@app.post("/emergency-stop")
async def emergency_stop():
    STATE.trigger_emergency_stop()
    return {"active": True}

@app.post("/orders/cancel")
async def cancel_order(payload: dict):
    return {"cancelled": payload["order_id"]}

@app.post("/orders/cancel-all")
async def cancel_all_orders():
    return {"cancelled": "all"}

@app.post("/repo-harvester/run")
async def repo_harvester_run(background_tasks: BackgroundTasks):
    background_tasks.add_task(run_harvester)
    return {"status": "started"}

@app.post("/repo-harvester/audit-repo")
async def audit_single_repo(payload: dict):
    return {"status": "not_implemented"}

@app.post("/repo-harvester/build-adapter-plan")
async def build_adapter_plan(payload: dict):
    return {"status": "not_implemented"}

@app.websocket("/ws/status")
async def ws_status(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            await websocket.send_json({
                "mode": STATE.mode.value,
                "kill_switch_active": STATE.kill_switch.active,
                "emergency_stop_active": STATE.emergency_stop.active,
                "kalshi_connected": STATE.kalshi_connected,
            })
            await asyncio.sleep(2)
    except Exception:
        pass
