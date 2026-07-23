package com.dummy.operator

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.BackHandler
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import kotlin.math.abs
import kotlin.math.roundToInt

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        val repo = DummyRepository(applicationContext)
        setContent {
            DummyOperatorTheme {
                val vm: OperatorViewModel = viewModel(
                    factory = object : ViewModelProvider.Factory {
                        @Suppress("UNCHECKED_CAST")
                        override fun <T : androidx.lifecycle.ViewModel> create(c: Class<T>): T =
                            OperatorViewModel(repo) as T
                    }
                )
                OperatorApp(vm)
            }
        }
    }
}

@OptIn(androidx.compose.material3.ExperimentalMaterial3Api::class)
@Composable
fun OperatorApp(vm: OperatorViewModel) {
    val state by vm.state.collectAsStateWithLifecycle()
    val refreshing by vm.refreshing.collectAsStateWithLifecycle()
    val guide by vm.guide.collectAsStateWithLifecycle()
    var showSettings by remember { mutableStateOf(false) }

    // A guide drill-down takes over the screen; back returns to the board.
    if (guide !is GuideState.Idle) {
        BackHandler { vm.closeGuide() }
        GuideScreen(guide, onBack = { vm.closeGuide() }, onReload = { vm.reloadGuide(it) })
        return
    }

    Scaffold(
        containerColor = PhosphorBg,
        topBar = {
            TopAppBar(
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = PhosphorPanel,
                    titleContentColor = PhosphorGreen,
                    actionIconContentColor = PhosphorDim,
                ),
                title = {
                    Column {
                        Text("DUMMY OPERATOR", fontWeight = FontWeight.Bold, letterSpacing = 2.sp)
                        ConnectionLine(state)
                    }
                },
                actions = {
                    IconButton(onClick = { vm.refresh() }) {
                        Icon(Icons.Filled.Refresh, contentDescription = "Refresh")
                    }
                    IconButton(onClick = { showSettings = true }) {
                        Icon(Icons.Filled.Settings, contentDescription = "Settings")
                    }
                },
            )
        },
    ) { pad ->
        Box(
            Modifier
                .padding(pad)
                .fillMaxSize()
                .background(PhosphorBg)
        ) {
            when (val s = state) {
                is LoadState.Loading -> CenterNote("connecting to Dummy…", refreshing = true)
                is LoadState.Error -> ErrorView(s.message, vm.baseUrl) { showSettings = true }
                is LoadState.Ok -> OperatorBoard(s.snapshot, refreshing) { vm.openGuide(it) }
            }
        }
    }

    if (showSettings) {
        SettingsDialog(vm.baseUrl, onDismiss = { showSettings = false }) {
            vm.setBaseUrl(it); showSettings = false
        }
    }
}

@Composable
private fun ConnectionLine(state: LoadState) {
    val (dot, label) = when (state) {
        is LoadState.Ok -> {
            val age = state.snapshot.dataAgeSeconds?.roundToInt()
            val fresh = (state.snapshot.dataStatus ?: "").lowercase().contains("fresh") ||
                (age != null && age < 900)
            (if (fresh) PhosphorGreen else PhosphorAmber) to
                ("live · " + (age?.let { agoText(it) } ?: (state.snapshot.dataStatus ?: "connected")))
        }
        is LoadState.Error -> PhosphorRed to "offline — tap ⚙ to set the URL"
        LoadState.Loading -> PhosphorAmber to "connecting…"
    }
    Row(verticalAlignment = Alignment.CenterVertically) {
        Box(Modifier.size(8.dp).clip(RoundedCornerShape(4.dp)).background(dot))
        Spacer(Modifier.width(6.dp))
        Text(label, color = PhosphorDim, fontSize = 11.sp)
    }
}

@Composable
private fun OperatorBoard(
    snap: OperatorSnapshot, refreshing: Boolean, onOpenGuide: (String) -> Unit,
) {
    Column(
        Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(12.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        AccountCard(snap)
        snap.verticals.forEach { VerticalCard(it, onOpenGuide) }
        Text(
            "tap any scope for its daily betting guide · read-only · execution " +
                (if (snap.executionAuthority) "GRANTED" else "LOCKED") + " · $0 auto-capital",
            color = PhosphorDim, fontSize = 10.sp,
            modifier = Modifier.fillMaxWidth().padding(top = 4.dp),
        )
        Spacer(Modifier.height(24.dp))
    }
}

@Composable
private fun AccountCard(snap: OperatorSnapshot) {
    Panel {
        Text("PAPER ACCOUNT", color = PhosphorDim, fontSize = 11.sp, letterSpacing = 2.sp)
        Spacer(Modifier.height(6.dp))
        Row(verticalAlignment = Alignment.Bottom) {
            Text(
                snap.balanceCents?.let { "$" + "%.2f".format(it / 100.0) } ?: "—",
                color = PhosphorGreen, fontSize = 34.sp, fontWeight = FontWeight.Bold,
            )
            Spacer(Modifier.width(10.dp))
            Text("Kalshi paper", color = PhosphorDim, fontSize = 12.sp,
                modifier = Modifier.padding(bottom = 6.dp))
        }
        Spacer(Modifier.height(10.dp))
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Stat("FILLS", snap.fills?.toString() ?: "—", Modifier.weight(1f))
            Stat("ORDERS", snap.orders?.toString() ?: "—", Modifier.weight(1f))
            Stat("SOURCES", snap.activeSources?.toString() ?: "—", Modifier.weight(1f))
        }
        Spacer(Modifier.height(8.dp))
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Badge(
                if (snap.executionAuthority) "EXEC: GRANTED" else "EXEC: LOCKED",
                if (snap.executionAuthority) PhosphorRed else PhosphorGreen,
            )
            snap.httpProofValid?.let {
                Badge(if (it) "PROOF: VALID" else "PROOF: —", if (it) PhosphorGreen else PhosphorAmber)
            }
        }
        snap.paperResultsStatus?.let {
            Spacer(Modifier.height(6.dp))
            Text(it.replace('_', ' ').lowercase(), color = PhosphorDim, fontSize = 10.sp)
        }
    }
}

@Composable
private fun VerticalCard(v: VerticalView, onOpenGuide: (String) -> Unit) {
    Panel {
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
            Text(v.name, color = PhosphorGreen, fontSize = 15.sp,
                fontWeight = FontWeight.Bold, letterSpacing = 2.sp)
            Text("${v.openPicks} open · ${v.n} graded", color = PhosphorDim, fontSize = 11.sp)
        }
        Spacer(Modifier.height(8.dp))
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Stat("HIT RATE", pct(v.hitRate), Modifier.weight(1f))
            Stat("BRIER", num(v.brier, 4), Modifier.weight(1f))
            EdgeStat("EDGE vs MKT", v.brierEdge, Modifier.weight(1f))
        }
        if (v.scopes.isNotEmpty()) {
            Spacer(Modifier.height(10.dp))
            v.scopes.take(12).forEach { ScopeRow(it) { onOpenGuide(it.name) } }
        }
    }
}

@Composable
private fun ScopeRow(s: ScopeAccuracy, onClick: () -> Unit) {
    Row(
        Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(6.dp))
            .clickable(onClick = onClick)
            .padding(vertical = 5.dp, horizontal = 4.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(s.name, color = PhosphorText, fontSize = 12.sp, fontWeight = FontWeight.Bold,
            modifier = Modifier.width(72.dp), maxLines = 1, overflow = TextOverflow.Ellipsis)
        Text(pct(s.hitRate), color = PhosphorDim, fontSize = 12.sp, modifier = Modifier.width(58.dp))
        Text(num(s.brier, 3), color = PhosphorDim, fontSize = 12.sp, modifier = Modifier.width(58.dp))
        val edgeColor = when {
            s.brierEdge == null -> PhosphorDim
            s.brierEdge > 0 -> PhosphorGreen
            else -> PhosphorRed
        }
        Text(signed(s.brierEdge, 4), color = edgeColor, fontSize = 12.sp,
            modifier = Modifier.weight(1f))
        s.trend?.let {
            val (t, c) = when (it) {
                "improving" -> "▲" to PhosphorGreen
                "declining" -> "▼" to PhosphorRed
                else -> "•" to PhosphorDim
            }
            Text(t, color = c, fontSize = 12.sp)
        }
        Spacer(Modifier.width(6.dp))
        Text("›", color = PhosphorDim, fontSize = 16.sp)
    }
}

@OptIn(androidx.compose.material3.ExperimentalMaterial3Api::class)
@Composable
private fun GuideScreen(
    state: GuideState, onBack: () -> Unit, onReload: (String) -> Unit,
) {
    val group = when (state) {
        is GuideState.Loading -> state.group
        is GuideState.Ok -> state.guide.league
        is GuideState.Error -> state.group
        GuideState.Idle -> ""
    }
    Scaffold(
        containerColor = PhosphorBg,
        topBar = {
            TopAppBar(
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = PhosphorPanel,
                    titleContentColor = PhosphorGreen,
                    navigationIconContentColor = PhosphorGreen,
                    actionIconContentColor = PhosphorDim,
                ),
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back")
                    }
                },
                title = {
                    Column {
                        Text("${group.uppercase()} GUIDE",
                            fontWeight = FontWeight.Bold, letterSpacing = 2.sp)
                        val sub = (state as? GuideState.Ok)?.guide?.let {
                            "${it.picks.size} tiered picks" +
                                (it.coverageDate?.let { d -> " · $d" } ?: "")
                        } ?: "today's betting guide"
                        Text(sub, color = PhosphorDim, fontSize = 11.sp)
                    }
                },
                actions = {
                    IconButton(onClick = { onReload(group) }) {
                        Icon(Icons.Filled.Refresh, contentDescription = "Refresh")
                    }
                },
            )
        },
    ) { pad ->
        Box(Modifier.padding(pad).fillMaxSize().background(PhosphorBg)) {
            when (state) {
                is GuideState.Loading -> CenterNote("loading ${group.uppercase()} guide…", true)
                is GuideState.Error -> CenterNote("couldn't load guide: ${state.message}", false)
                is GuideState.Ok -> {
                    if (state.guide.picks.isEmpty()) {
                        CenterNote("no tiered picks for ${group.uppercase()} right now", false)
                    } else {
                        Column(
                            Modifier.fillMaxSize().verticalScroll(rememberScrollState())
                                .padding(12.dp),
                            verticalArrangement = Arrangement.spacedBy(8.dp),
                        ) {
                            state.guide.picks.forEach { PickCard(it) }
                            Text("read-only · not advice · $0 auto-capital",
                                color = PhosphorDim, fontSize = 10.sp,
                                modifier = Modifier.padding(top = 4.dp))
                            Spacer(Modifier.height(24.dp))
                        }
                    }
                }
                GuideState.Idle -> {}
            }
        }
    }
}

@Composable
private fun PickCard(p: LeaguePick) {
    val tierColor = when (p.tier) {
        "A" -> PhosphorGreen
        "B" -> PhosphorAmber
        else -> PhosphorDim
    }
    Card(
        Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = PhosphorPanel),
        shape = RoundedCornerShape(8.dp),
    ) {
        Column(Modifier.padding(12.dp)) {
            Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                Box(
                    Modifier.clip(RoundedCornerShape(4.dp))
                        .background(tierColor.copy(alpha = 0.18f))
                        .padding(horizontal = 7.dp, vertical = 2.dp)
                ) { Text(p.tier ?: "?", color = tierColor, fontWeight = FontWeight.Bold, fontSize = 13.sp) }
                Spacer(Modifier.width(8.dp))
                Text(p.matchup.ifBlank { p.market }, color = PhosphorDim, fontSize = 12.sp,
                    maxLines = 1, overflow = TextOverflow.Ellipsis, modifier = Modifier.weight(1f))
                p.gameDate?.let { Text(it, color = PhosphorDim, fontSize = 11.sp) }
            }
            Spacer(Modifier.height(8.dp))
            // The recommended action, unmistakable: big "TAKE →" line.
            Row(verticalAlignment = Alignment.CenterVertically) {
                Box(
                    Modifier.clip(RoundedCornerShape(4.dp)).background(PhosphorGreen)
                        .padding(horizontal = 6.dp, vertical = 2.dp)
                ) { Text("TAKE", color = PhosphorBg, fontWeight = FontWeight.Bold, fontSize = 11.sp) }
                Spacer(Modifier.width(8.dp))
                Text(
                    p.recommendation ?: p.market,
                    color = PhosphorGreen, fontSize = 17.sp, fontWeight = FontWeight.Bold,
                    maxLines = 2, overflow = TextOverflow.Ellipsis,
                )
            }
            Spacer(Modifier.height(4.dp))
            Text(p.market, color = PhosphorDim, fontSize = 11.sp)
            Spacer(Modifier.height(8.dp))
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Stat("MODEL", pct(p.probability), Modifier.weight(1f))
                Stat("MARKET", pct(p.marketProbability), Modifier.weight(1f))
                EdgeStat("EDGE", p.edge, Modifier.weight(1f))
            }
            p.why?.takeIf { it.isNotBlank() }?.let {
                Spacer(Modifier.height(8.dp))
                Text(it, color = PhosphorDim, fontSize = 11.sp, maxLines = 3,
                    overflow = TextOverflow.Ellipsis)
            }
        }
    }
}

@Composable
private fun Stat(label: String, value: String, modifier: Modifier = Modifier) {
    Column(modifier.clip(RoundedCornerShape(6.dp)).background(PhosphorLine).padding(8.dp)) {
        Text(label, color = PhosphorDim, fontSize = 9.sp, letterSpacing = 1.sp)
        Text(value, color = PhosphorText, fontSize = 16.sp, fontWeight = FontWeight.Bold)
    }
}

@Composable
private fun EdgeStat(label: String, edge: Double?, modifier: Modifier = Modifier) {
    val c = when {
        edge == null -> PhosphorText
        edge > 0 -> PhosphorGreen
        else -> PhosphorRed
    }
    Column(modifier.clip(RoundedCornerShape(6.dp)).background(PhosphorLine).padding(8.dp)) {
        Text(label, color = PhosphorDim, fontSize = 9.sp, letterSpacing = 1.sp)
        Text(signed(edge, 4), color = c, fontSize = 16.sp, fontWeight = FontWeight.Bold)
    }
}

@Composable
private fun Badge(text: String, color: Color) {
    Box(
        Modifier.clip(RoundedCornerShape(4.dp)).background(color.copy(alpha = 0.15f))
            .padding(horizontal = 8.dp, vertical = 4.dp)
    ) { Text(text, color = color, fontSize = 10.sp, fontWeight = FontWeight.Bold) }
}

@Composable
private fun Panel(content: @Composable androidx.compose.foundation.layout.ColumnScope.() -> Unit) {
    Card(
        Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = PhosphorPanel),
        shape = RoundedCornerShape(10.dp),
    ) { Column(Modifier.padding(14.dp), content = content) }
}

@Composable
private fun CenterNote(text: String, refreshing: Boolean) {
    Column(Modifier.fillMaxSize(), verticalArrangement = Arrangement.Center,
        horizontalAlignment = Alignment.CenterHorizontally) {
        if (refreshing) { CircularProgressIndicator(color = PhosphorGreen); Spacer(Modifier.height(12.dp)) }
        Text(text, color = PhosphorDim)
    }
}

@Composable
private fun ErrorView(message: String, url: String, onSettings: () -> Unit) {
    Column(Modifier.fillMaxSize().padding(24.dp), verticalArrangement = Arrangement.Center,
        horizontalAlignment = Alignment.CenterHorizontally) {
        Text("CAN'T REACH DUMMY", color = PhosphorRed, fontWeight = FontWeight.Bold, letterSpacing = 2.sp)
        Spacer(Modifier.height(8.dp))
        Text(message, color = PhosphorDim, fontSize = 12.sp)
        Spacer(Modifier.height(4.dp))
        Text(url, color = PhosphorDim, fontSize = 11.sp)
        Spacer(Modifier.height(16.dp))
        Text("Check Tailscale is up and DummyDashboard is bound to the tailnet.",
            color = PhosphorDim, fontSize = 11.sp)
        Spacer(Modifier.height(16.dp))
        TextButton(onClick = onSettings) { Text("Set dashboard URL", color = PhosphorGreen) }
    }
}

@Composable
private fun SettingsDialog(current: String, onDismiss: () -> Unit, onSave: (String) -> Unit) {
    var text by remember { mutableStateOf(current) }
    AlertDialog(
        containerColor = PhosphorPanel,
        onDismissRequest = onDismiss,
        title = { Text("Dashboard URL", color = PhosphorGreen) },
        text = {
            Column {
                Text("Dummy's Tailscale address, e.g. http://100.98.141.113:8787",
                    color = PhosphorDim, fontSize = 12.sp)
                Spacer(Modifier.height(8.dp))
                OutlinedTextField(value = text, onValueChange = { text = it }, singleLine = true)
            }
        },
        confirmButton = { TextButton(onClick = { onSave(text) }) { Text("Save", color = PhosphorGreen) } },
        dismissButton = { TextButton(onClick = onDismiss) { Text("Cancel", color = PhosphorDim) } },
    )
}

// ---- formatting helpers -----------------------------------------------------
private fun pct(v: Double?): String = v?.let { "%.1f%%".format(it * 100) } ?: "—"
private fun num(v: Double?, dp: Int): String = v?.let { "%.${dp}f".format(it) } ?: "—"
private fun signed(v: Double?, dp: Int): String =
    v?.let { (if (it >= 0) "+" else "") + "%.${dp}f".format(it) } ?: "—"
private fun agoText(seconds: Int): String = when {
    seconds < 60 -> "${seconds}s ago"
    seconds < 3600 -> "${seconds / 60}m ago"
    else -> "${seconds / 3600}h ago"
}
@Suppress("unused") private fun unusedAbs(x: Double) = abs(x)
