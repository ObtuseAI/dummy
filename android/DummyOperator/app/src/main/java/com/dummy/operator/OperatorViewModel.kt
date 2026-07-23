package com.dummy.operator

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

class OperatorViewModel(private val repo: DummyRepository) : ViewModel() {

    private val _state = MutableStateFlow<LoadState>(LoadState.Loading)
    val state: StateFlow<LoadState> = _state.asStateFlow()

    private val _refreshing = MutableStateFlow(false)
    val refreshing: StateFlow<Boolean> = _refreshing.asStateFlow()

    val baseUrl: String get() = repo.baseUrl

    init {
        viewModelScope.launch {
            // Auto-poll every 20s; the dashboard snapshot updates on its own cadence.
            while (isActive) {
                refresh()
                delay(20_000)
            }
        }
    }

    fun refresh() {
        viewModelScope.launch {
            _refreshing.value = true
            val next = withContext(Dispatchers.IO) {
                try {
                    LoadState.Ok(repo.fetch())
                } catch (e: Exception) {
                    LoadState.Error(e.message ?: e.javaClass.simpleName)
                }
            }
            // Keep the last good snapshot visible if a poll fails transiently.
            if (next is LoadState.Ok || _state.value !is LoadState.Ok) {
                _state.value = next
            }
            _refreshing.value = false
        }
    }

    fun setBaseUrl(url: String) {
        repo.baseUrl = url
        _state.value = LoadState.Loading
        refresh()
    }

    // ---- league betting-guide drill-down ------------------------------------
    private val _guide = MutableStateFlow<GuideState>(GuideState.Idle)
    val guide: StateFlow<GuideState> = _guide.asStateFlow()

    fun openGuide(group: String) {
        _guide.value = GuideState.Loading(group)
        loadGuide(group)
    }

    fun reloadGuide(group: String) = loadGuide(group)

    private fun loadGuide(group: String) {
        viewModelScope.launch {
            val next = withContext(Dispatchers.IO) {
                try {
                    GuideState.Ok(repo.fetchLeagueGuide(group))
                } catch (e: Exception) {
                    GuideState.Error(group, e.message ?: e.javaClass.simpleName)
                }
            }
            _guide.value = next
        }
    }

    fun closeGuide() { _guide.value = GuideState.Idle }
}

sealed interface GuideState {
    data object Idle : GuideState
    data class Loading(val group: String) : GuideState
    data class Ok(val guide: LeagueGuide) : GuideState
    data class Error(val group: String, val message: String) : GuideState
}
