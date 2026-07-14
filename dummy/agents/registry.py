"""Dependency-safe, deterministic registry for versioned agent contracts."""

from __future__ import annotations

from collections import defaultdict

from dummy.agents.contract import AgentContract


class RegistryError(ValueError):
    """The registry contains a duplicate, missing, or cyclic dependency."""


class AgentRegistry:
    def __init__(self) -> None:
        self._contracts: dict[str, AgentContract] = {}
        self._sealed = False
        self._dependency_order: tuple[str, ...] = ()

    @property
    def sealed(self) -> bool:
        return self._sealed

    def register(self, contract: AgentContract) -> None:
        if self._sealed:
            raise RegistryError("sealed registry cannot be modified")
        if contract.agent_id in self._contracts:
            raise RegistryError(f"duplicate agent_id: {contract.agent_id}")
        self._contracts[contract.agent_id] = contract

    def get(self, agent_id: str) -> AgentContract:
        try:
            return self._contracts[agent_id]
        except KeyError as exc:
            raise RegistryError(f"unknown agent_id: {agent_id}") from exc

    def contracts(self) -> tuple[AgentContract, ...]:
        return tuple(self._contracts[key] for key in sorted(self._contracts))

    def by_source_family(self) -> dict[str, tuple[str, ...]]:
        grouped: dict[str, list[str]] = defaultdict(list)
        for contract in self.contracts():
            grouped[contract.source_family].append(contract.agent_id)
        return {
            family: tuple(agent_ids)
            for family, agent_ids in sorted(grouped.items())
        }

    def by_calibration_identity(self) -> dict[str, tuple[str, ...]]:
        grouped: dict[str, list[str]] = defaultdict(list)
        for contract in self.contracts():
            grouped[contract.calibration_identity].append(contract.agent_id)
        return {
            identity: tuple(agent_ids)
            for identity, agent_ids in sorted(grouped.items())
        }

    def seal(self) -> tuple[str, ...]:
        if self._sealed:
            return self._dependency_order
        missing = {
            dependency
            for contract in self._contracts.values()
            for dependency in contract.dependencies
            if dependency not in self._contracts
        }
        if missing:
            raise RegistryError(f"missing dependencies: {sorted(missing)}")

        indegree = {agent_id: 0 for agent_id in self._contracts}
        children: dict[str, set[str]] = defaultdict(set)
        for contract in self._contracts.values():
            for dependency in contract.dependencies:
                indegree[contract.agent_id] += 1
                children[dependency].add(contract.agent_id)

        ready = sorted(agent_id for agent_id, degree in indegree.items() if degree == 0)
        order: list[str] = []
        while ready:
            agent_id = ready.pop(0)
            order.append(agent_id)
            for child in sorted(children[agent_id]):
                indegree[child] -= 1
                if indegree[child] == 0:
                    ready.append(child)
                    ready.sort()
        if len(order) != len(self._contracts):
            cycle = sorted(agent_id for agent_id, degree in indegree.items() if degree)
            raise RegistryError(f"cyclic agent dependencies: {cycle}")

        self._dependency_order = tuple(order)
        self._sealed = True
        return self._dependency_order

    @property
    def dependency_order(self) -> tuple[str, ...]:
        if not self._sealed:
            raise RegistryError("registry must be sealed first")
        return self._dependency_order
