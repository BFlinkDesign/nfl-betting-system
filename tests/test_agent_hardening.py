"""Tests for hardened agent framework — message bus, lifecycle, event store."""

import asyncio

import pytest

from src.agents.base_agent import (
    AgentCapability,
    AgentMessage,
    AgentRegistry,
    AgentStatus,
    BaseAgent,
)
from src.agents.event_store import EventStore
from src.agents.message_bus import MessageBus


class DummyAgent(BaseAgent):
    """Minimal agent for testing."""

    def __init__(self, agent_id="test_001", agent_name="Test Agent"):
        super().__init__(agent_id, agent_name, [AgentCapability.REASONING])
        self.received: list = []

    async def run(self):
        while self.running:
            await asyncio.sleep(0.1)

    async def handle_message(self, message):
        self.received.append(message)


class TestBaseAgentLifecycle:
    def test_initial_status(self):
        agent = DummyAgent()
        assert agent.status == AgentStatus.INITIALIZING
        assert agent.error_count == 0

    @pytest.mark.asyncio
    async def test_start_and_stop(self):
        agent = DummyAgent()
        task = asyncio.create_task(agent.start())
        await asyncio.sleep(0.2)
        assert agent.status == AgentStatus.RUNNING

        await agent.stop()
        assert agent.status == AgentStatus.SHUTDOWN
        assert not agent.running
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    def test_receive_message_queue_full(self):
        agent = DummyAgent()
        agent.message_queue = asyncio.Queue(maxsize=1)
        m1 = AgentMessage(message_type="test", content={"n": 1})
        m2 = AgentMessage(message_type="test", content={"n": 2})
        agent.receive_message(m1)
        agent.receive_message(m2)
        assert agent.message_queue.qsize() == 1


class TestAgentRegistry:
    def test_duplicate_id_rejected(self):
        registry = AgentRegistry()
        a1 = DummyAgent("dup_001", "Agent A")
        a2 = DummyAgent("dup_001", "Agent B")
        registry.register(a1)
        with pytest.raises(ValueError, match="already registered"):
            registry.register(a2)


class TestMessageBus:
    @pytest.mark.asyncio
    async def test_targeted_send(self):
        bus = MessageBus()
        from src.agents.base_agent import agent_registry

        agent = DummyAgent("bus_test_001")
        agent_registry.agents["bus_test_001"] = agent
        bus.subscribe(agent)

        msg = AgentMessage(
            sender_id="other",
            receiver_id="bus_test_001",
            message_type="request",
        )
        await bus.send(msg)
        assert agent.message_queue.qsize() == 1

        agent_registry.agents.pop("bus_test_001", None)

    @pytest.mark.asyncio
    async def test_no_self_delivery(self):
        bus = MessageBus()
        agent = DummyAgent("self_001")
        bus.subscribe(agent)

        msg = AgentMessage(sender_id="self_001", message_type="request")
        await bus.send(msg)
        assert agent.message_queue.qsize() == 0

    @pytest.mark.asyncio
    async def test_no_duplicate_delivery(self):
        bus = MessageBus()
        from src.agents.base_agent import agent_registry

        agent = DummyAgent("dedup_001")
        agent_registry.agents["dedup_001"] = agent
        bus.subscribe(agent, ["request"])
        bus.subscribe(agent, ["*"])

        msg = AgentMessage(
            sender_id="other",
            receiver_id="dedup_001",
            message_type="request",
        )
        await bus.send(msg)
        assert agent.message_queue.qsize() == 1

        agent_registry.agents.pop("dedup_001", None)

    def test_stats(self):
        bus = MessageBus()
        stats = bus.get_stats()
        assert "delivered" in stats
        assert "dropped" in stats


class TestEventStore:
    def test_record_and_query(self, tmp_path):
        store = EventStore(db_path=str(tmp_path / "test_events.db"))
        msg = AgentMessage(
            sender_id="agent_a",
            receiver_id="agent_b",
            message_type="request",
            content={"action": "bet"},
        )
        store.record(msg)
        assert store.count() == 1

        results = store.query(sender_id="agent_a")
        assert len(results) == 1
        assert results[0]["sender_id"] == "agent_a"
        store.close()

    def test_duplicate_message_ignored(self, tmp_path):
        store = EventStore(db_path=str(tmp_path / "test_events2.db"))
        msg = AgentMessage(
            sender_id="a",
            receiver_id="b",
            message_type="test",
        )
        store.record(msg)
        store.record(msg)
        assert store.count() == 1
        store.close()
