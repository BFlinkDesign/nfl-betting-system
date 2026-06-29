"""
Message Bus for Agent Communication

Handles routing and delivery of messages between agents.
Bounded history, safe concurrent subscription, and duplicate-delivery guard.
"""

import asyncio
import logging
from collections import defaultdict, deque
from typing import Deque, Dict, List, Optional, Set

from src.agents.base_agent import AgentMessage, BaseAgent

logger = logging.getLogger(__name__)

MAX_BUS_HISTORY = 50_000


class MessageBus:
    """
    Central message bus for agent communication.

    Features:
    - Targeted + type-based + broadcast routing
    - Bounded in-memory history (ring buffer)
    - Safe concurrent subscription via snapshot iteration
    """

    def __init__(self):
        self.subscribers: Dict[str, List[BaseAgent]] = defaultdict(list)
        self.message_history: Deque[AgentMessage] = deque(maxlen=MAX_BUS_HISTORY)
        self.running = False
        self.lock = asyncio.Lock()
        self._delivered: int = 0
        self._dropped: int = 0

        logger.info("Message bus initialized")

    def subscribe(self, agent: BaseAgent, message_types: Optional[List[str]] = None):
        if message_types is None:
            message_types = ["*"]
        for msg_type in message_types:
            if agent not in self.subscribers[msg_type]:
                self.subscribers[msg_type].append(agent)

    def unsubscribe(self, agent: BaseAgent):
        for subs in self.subscribers.values():
            try:
                subs.remove(agent)
            except ValueError:
                pass

    async def send(self, message: AgentMessage):
        """Route a message to its target(s) and persist to event store."""
        async with self.lock:
            self.message_history.append(message)
            delivered_to: Set[str] = set()

            try:
                from src.agents.event_store import get_event_store

                get_event_store().record(message)
            except Exception as e:
                logger.warning("Event store write failed: %s", e)

            if message.receiver_id and message.receiver_id != "*":
                receiver = self._find_agent(message.receiver_id)
                if receiver:
                    receiver.receive_message(message)
                    delivered_to.add(receiver.agent_id)
                else:
                    logger.warning("Receiver %s not found", message.receiver_id)
                    self._dropped += 1

            for msg_type in (message.message_type, "*"):
                for sub in list(self.subscribers.get(msg_type, [])):
                    if (
                        sub.agent_id != message.sender_id
                        and sub.agent_id not in delivered_to
                    ):
                        sub.receive_message(message)
                        delivered_to.add(sub.agent_id)

            self._delivered += len(delivered_to)

    async def broadcast(self, message: AgentMessage):
        message.receiver_id = "*"
        await self.send(message)

    def _find_agent(self, agent_id: str) -> Optional[BaseAgent]:
        from src.agents.base_agent import agent_registry

        return agent_registry.get(agent_id)

    def get_message_history(self, agent_id: Optional[str] = None) -> List[AgentMessage]:
        if agent_id:
            return [
                m
                for m in self.message_history
                if m.sender_id == agent_id or m.receiver_id == agent_id
            ]
        return list(self.message_history)

    def get_stats(self) -> Dict:
        return {
            "history_size": len(self.message_history),
            "delivered": self._delivered,
            "dropped": self._dropped,
            "subscriber_types": len(self.subscribers),
        }


message_bus = MessageBus()
