package com.dummy.operator

import android.content.Context
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL

/** Read-only snapshot of Dummy's operator state, parsed defensively. */
data class ScopeAccuracy(
    val name: String,
    val brier: Double?,
    val brierEdge: Double?,
    val hitRate: Double?,
    val n: Int,
    val contestedN: Int,
    val trend: String?,
)

data class VerticalView(
    val name: String,
    val brier: Double?,
    val brierEdge: Double?,
    val hitRate: Double?,
    val n: Int,
    val openPicks: Int,
    val scopes: List<ScopeAccuracy>,
)

data class OperatorSnapshot(
    val balanceCents: Long?,
    val fills: Int?,
    val orders: Int?,
    val executionAuthority: Boolean,
    val paperResultsStatus: String?,
    val activeSources: Int?,
    val dataStatus: String?,
    val dataAgeSeconds: Double?,
    val httpProofValid: Boolean?,
    val verticals: List<VerticalView>,
    val fetchedAtMillis: Long,
)

data class LeaguePick(
    val matchup: String,
    val market: String,
    val tier: String?,
    val pick: String?,
    val recommendation: String?,
    val edge: Double?,
    val probability: Double?,
    val marketProbability: Double?,
    val gameDate: String?,
    // ISO calendar date (YYYY-MM-DD) for reliable soonest-first ordering.
    val eventDate: String?,
    val why: String?,
    // Wave-78: the independent model view -- our own model's both-sides call,
    // surfaced even when the promotion ladder keeps it out of the traded number.
    val modelProbability: Double?,
    val modelEdge: Double?,
    val modelRecommendation: String?,
    val hasIndependentModel: Boolean,
)

data class LeagueGuide(
    val league: String,
    val coverageDate: String?,
    val picks: List<LeaguePick>,
    // Markets with no tradeable tier where our independent model still leans
    // hard against the market -- the model's strongest both-sides reads.
    val modelLeans: List<LeaguePick>,
    val marketCount: Int,
)

sealed interface LoadState {
    data object Loading : LoadState
    data class Ok(val snapshot: OperatorSnapshot) : LoadState
    data class Error(val message: String) : LoadState
}

class DummyRepository(context: Context) {

    private val prefs = context.getSharedPreferences("dummy_operator", Context.MODE_PRIVATE)

    var baseUrl: String
        get() = prefs.getString("base_url", DEFAULT_BASE_URL) ?: DEFAULT_BASE_URL
        set(value) { prefs.edit().putString("base_url", value.trim().trimEnd('/')).apply() }

    private fun getJson(path: String, timeoutMs: Int): JSONObject {
        val url = URL("$baseUrl$path")
        val conn = (url.openConnection() as HttpURLConnection).apply {
            connectTimeout = timeoutMs
            readTimeout = timeoutMs
            requestMethod = "GET"
            setRequestProperty("Accept", "application/json")
        }
        try {
            val code = conn.responseCode
            val stream = if (code in 200..299) conn.inputStream else conn.errorStream
            val body = stream?.bufferedReader()?.use { it.readText() } ?: ""
            if (code !in 200..299) error("HTTP $code")
            return JSONObject(body)
        } finally {
            conn.disconnect()
        }
    }

    fun fetch(): OperatorSnapshot {
        val overview = getJson("/api/overview", 8000)
        val la = overview.optJSONObject("live_account")
        val proof = la?.optJSONObject("http_proof")

        val verticals = mutableListOf<VerticalView>()
        try {
            val scopes = getJson("/api/scopes", 9000)
            val vs = scopes.optJSONObject("verticals")
            vs?.keys()?.forEach { vName ->
                val v = vs.optJSONObject(vName) ?: return@forEach
                val summary = v.optJSONObject("summary")
                val scopeList = mutableListOf<ScopeAccuracy>()
                val sc = v.optJSONObject("scopes")
                sc?.keys()?.forEach { sName ->
                    val s = sc.optJSONObject(sName) ?: return@forEach
                    // Roll the scope's bet-types into one headline row.
                    val bts = s.optJSONObject("bet_types")
                    var bestN = -1
                    var best: JSONObject? = null
                    var trend: String? = null
                    bts?.keys()?.forEach { bt ->
                        val b = bts.optJSONObject(bt) ?: return@forEach
                        val bsum = b.optJSONObject("summary")
                        val n = bsum?.optInt("n", 0) ?: 0
                        if (n > bestN) {
                            bestN = n
                            best = bsum
                            trend = b.optJSONObject("improvement")?.optString("trend")
                        }
                    }
                    if (best != null) {
                        scopeList += ScopeAccuracy(
                            name = sName,
                            brier = best!!.optDoubleOrNull("brier"),
                            brierEdge = best!!.optDoubleOrNull("brier_edge"),
                            hitRate = best!!.optDoubleOrNull("hit_rate"),
                            n = best!!.optInt("n", 0),
                            contestedN = best!!.optInt("contested_n", 0),
                            trend = trend,
                        )
                    }
                }
                scopeList.sortByDescending { it.n }
                verticals += VerticalView(
                    name = vName,
                    brier = summary?.optDoubleOrNull("brier"),
                    brierEdge = summary?.optDoubleOrNull("brier_edge"),
                    hitRate = summary?.optDoubleOrNull("hit_rate"),
                    n = summary?.optInt("n", 0) ?: 0,
                    openPicks = v.optInt("open_picks", 0),
                    scopes = scopeList,
                )
            }
        } catch (_: Exception) {
            // Scopes are optional enrichment; the overview card still renders.
        }

        return OperatorSnapshot(
            balanceCents = la?.optLongOrNull("balance_cents"),
            fills = la?.optIntOrNull("historical_fills_count"),
            orders = la?.optIntOrNull("historical_orders_count"),
            executionAuthority = la?.optBoolean("execution_authority", false) ?: false,
            paperResultsStatus = overview.optString("paper_results_status").ifBlank { null },
            activeSources = overview.optIntOrNull("active_sources"),
            dataStatus = overview.optString("data_status").ifBlank { null },
            dataAgeSeconds = overview.optDoubleOrNull("data_age_seconds"),
            httpProofValid = proof?.optBooleanOrNull("audit_valid"),
            verticals = verticals.sortedBy { it.name },
            fetchedAtMillis = System.currentTimeMillis(),
        )
    }

    /** Today's ranked betting guide for one league/coin group (e.g. "mlb"). */
    fun fetchLeagueGuide(group: String): LeagueGuide {
        val board = getJson("/api/bet_board", 12000)
        val groups = board.optJSONObject("groups")
        val g = groups?.optJSONObject(group.lowercase())
        val picks = mutableListOf<LeaguePick>()
        val leans = mutableListOf<LeaguePick>()
        g?.keys()?.forEach { betType ->
            val arr = g.optJSONArray(betType) ?: return@forEach
            for (i in 0 until arr.length()) {
                val r = arr.optJSONObject(i) ?: continue
                val tier = r.optString("tier").ifBlank { null }
                val tradeable = tier in setOf("A", "B", "C")
                val hasModel = r.optBoolean("has_independent_model", false)
                // A row is a guide entry if the policy graded it into a tradeable
                // tier, OR our independent model has a view on it (so every market
                // with a model shows a both-sides read, not just the tradeable few).
                if (!tradeable && !hasModel) continue
                val side = r.optString("pick").ifBlank { r.optString("forecast_lean") }
                    .ifBlank { null }
                val pick = LeaguePick(
                    matchup = r.optString("matchup").ifBlank { r.optString("subject") },
                    market = r.optString("market").ifBlank { betType },
                    tier = tier,
                    pick = side,
                    recommendation = r.optString("recommendation").ifBlank {
                        side?.let { r.optString("market") + " → " + it.uppercase() }
                    },
                    edge = r.optDoubleOrNull("after_fee_edge") ?: r.optDoubleOrNull("edge"),
                    probability = r.optDoubleOrNull("probability"),
                    marketProbability = r.optDoubleOrNull("market_probability"),
                    gameDate = r.optString("game_date").ifBlank { r.optString("event_date") }
                        .ifBlank { null },
                    eventDate = r.optString("event_date").ifBlank { null },
                    why = r.optString("why").ifBlank { null },
                    modelProbability = r.optDoubleOrNull("model_probability"),
                    modelEdge = r.optDoubleOrNull("model_edge"),
                    modelRecommendation = r.optString("model_recommendation").ifBlank { null },
                    hasIndependentModel = hasModel,
                )
                if (tradeable) picks += pick
                // Model leans: no tradeable tier, but the model disagrees with
                // the market by >= 5c on either side. Capped + ranked below.
                else if (hasModel && kotlin.math.abs(pick.modelEdge ?: 0.0) >= 0.05) {
                    leans += pick
                }
            }
        }
        // Soonest-first: a daily guide should lead with the nearest slate, not
        // jump to a far-future date just because it has a strong pick. Within a
        // day, rank by tier then edge (picks) / model disagreement (leans).
        val tierRank = mapOf("A" to 0, "B" to 1, "C" to 2)
        val farFuture = "9999-99-99"
        picks.sortWith(
            compareBy(
                { it.eventDate ?: farFuture },
                { tierRank[it.tier] ?: 9 },
                { -(it.edge ?: -1.0) },
            )
        )
        leans.sortWith(
            compareBy<LeaguePick> { it.eventDate ?: farFuture }
                .thenByDescending { kotlin.math.abs(it.modelEdge ?: 0.0) }
        )
        return LeagueGuide(
            league = group.uppercase(),
            coverageDate = board.optString("coverage_date").ifBlank { null },
            picks = picks,
            modelLeans = leans.take(40),
            marketCount = board.optInt("current_market_count", 0),
        )
    }

    companion object {
        // frankenstein's Tailscale IP; the dashboard is bound to the tailnet.
        const val DEFAULT_BASE_URL = "http://100.98.141.113:8787"
    }
}

private fun JSONObject.optDoubleOrNull(key: String): Double? =
    if (has(key) && !isNull(key)) optDouble(key).takeIf { !it.isNaN() } else null
private fun JSONObject.optIntOrNull(key: String): Int? =
    if (has(key) && !isNull(key)) optInt(key) else null
private fun JSONObject.optLongOrNull(key: String): Long? =
    if (has(key) && !isNull(key)) optLong(key) else null
private fun JSONObject.optBooleanOrNull(key: String): Boolean? =
    if (has(key) && !isNull(key)) optBoolean(key) else null
