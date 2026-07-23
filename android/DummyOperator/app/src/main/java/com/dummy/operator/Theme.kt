package com.dummy.operator

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Typography
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontFamily

// Totalizator phosphor palette — matches the Dummy web board's identity.
val PhosphorBg = Color(0xFF06100B)
val PhosphorPanel = Color(0xFF0C1A12)
val PhosphorLine = Color(0xFF16311F)
val PhosphorGreen = Color(0xFF39FF88)
val PhosphorDim = Color(0xFF6FBF8E)
val PhosphorAmber = Color(0xFFF2C14E)
val PhosphorRed = Color(0xFFE0563F)
val PhosphorText = Color(0xFFCDEFD8)

private val DummyColors = darkColorScheme(
    primary = PhosphorGreen,
    onPrimary = PhosphorBg,
    background = PhosphorBg,
    onBackground = PhosphorText,
    surface = PhosphorPanel,
    onSurface = PhosphorText,
    surfaceVariant = PhosphorLine,
    error = PhosphorRed,
)

@Composable
fun DummyOperatorTheme(content: @Composable () -> Unit) {
    @Suppress("UNUSED_EXPRESSION") isSystemInDarkTheme()   // always dark by design
    val mono = Typography(
        bodyLarge = TextStyle(fontFamily = FontFamily.Monospace),
        bodyMedium = TextStyle(fontFamily = FontFamily.Monospace),
        bodySmall = TextStyle(fontFamily = FontFamily.Monospace),
        titleLarge = TextStyle(fontFamily = FontFamily.Monospace),
        titleMedium = TextStyle(fontFamily = FontFamily.Monospace),
        labelSmall = TextStyle(fontFamily = FontFamily.Monospace),
    )
    MaterialTheme(colorScheme = DummyColors, typography = mono, content = content)
}
