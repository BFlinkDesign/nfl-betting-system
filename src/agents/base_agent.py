"""
Base Agent Framework

Foundation for all agents in the autonomous system.
Provides lifecycle management, message routing via the global message bus,
heartbeat tracking, bounded history, and cooperative shutdown.
"""

import asyncio
import logging
import threading
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Deque, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)

MAX_MESSAGE_HISTORY = 10_000


class AgentStatus(Enum):
    """Agent status states."""

    INITIALIZING = "initializing"
    READY = "ready"
    RUNNING = "running"
    PAUSED = "paused"
    ERROR = "error"
    SHUTDOWN = "shutdown"


class AgentCapability(Enum):
    """Agent capabilities."""

    REASONING = "reasoning"
    MEMORY = "memory"
    TOOLS = "tools"
    COMMUNICATION = "communication"
    LEARNING = "learning"


@dataclass
class AgentMessage:
    """Message between agents."""

    message_id: str = field(default_factory=lambda: str(uuid4()))
    sender_id: str = ""
    receiver_id: str = ""
    message_type: str = (
        "request"  # request, response, alert, command, proposal, vote, heartbeat
    )
    content: Dict[str, Any] = field(default_factory=dict)
    priority: int = 3  # 1=critical, 2=high, 3=normal, 4=low
    timestamp: datetime = field(default_factory=datetime.now)
    parent_id: Optional[str] = None  # For threading conversations
    requires_response: bool = False


class BaseAgent(ABC):
    """
    Base class for all agents.

    Provides:
    - Lifecycle management (init, run, shutdown)
    - Message passing
    - Tool registry
    - Memory/state management
    - Status tracking
    """

    def __init__(
        self, agent_id: str, agent_name: str, capabilities: List[AgentCapability]
    ):
        """
        Initialize base agent.

        Args:
            agent_id: Unique agent identifier
            agent_name: Human-readable name
            capabilities: List of agent capabilities
        """
        self.agent_id = agent_id
        self.agent_name = agent_name
        self.capabilities = capabilities

        self.status = AgentStatus.INITIALIZING
        self.created_at = datetime.now()
        self.last_heartbeat = datetime.now()

        self.message_queue: asyncio.Queue = asyncio.Queue(maxsize=1000)
        self.message_history: Deque[AgentMessage] = deque(maxlen=MAX_MESSAGE_HISTORY)

        self.tools: Dict[str, Callable] = {}
        self.memory: Dict[str, Any] = {}

        self.running = False
        self._tasks: List[asyncio.Task] = []
        self.lock = threading.Lock()
        self.error_count = 0

        logger.info("Initialized agent: %s (%s)", agent_name, agent_id)

    def register_tool(self, name: str, tool: Callable, description: str = ""):
        """
        Register a tool for the agent.

        Args:
            name: Tool name
            tool: Tool function
            description: Tool description
        """
        self.tools[name] = tool
        self.memory[f"tool_{name}_description"] = description
        logger.debug(f"Registered tool: {name}")

    def get_tool(self, name: str) -> Optional[Callable]:
        """Get a tool by name."""
        return self.tools.get(name)

    async def send_message_async(self, message: AgentMessage):
        """Send message via the global message bus (async)."""
        from src.agents.message_bus import message_bus

        message.sender_id = self.agent_id
        await message_bus.send(message)

    def send_message(self, message: AgentMessage):
        """Send message — schedules async delivery on the running loop."""
        from src.agents.message_bus import message_bus

        message.sender_id = self.agent_id
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(message_bus.send(message))
        except RuntimeError:
            logger.warning(
                "No running event loop; message %s not delivered", message.message_id
            )

    def receive_message(self, message: AgentMessage):
        """Enqueue an inbound message for processing."""
        try:
            self.message_queue.put_nowait(message)
        except asyncio.QueueFull:
            logger.warning(
                "Agent %s queue full — dropping message %s",
                self.agent_id,
                message.message_id,
            )
            return
        self.message_history.append(message)

    async def process_messages(self):
        """Process messages from queue until stopped."""
        while self.running:
            try:
                message = await asyncio.wait_for(self.message_queue.get(), timeout=1.0)
                await asyncio.wait_for(self.handle_message(message), timeout=30.0)
                self.update_heartbeat()
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.error_count += 1
                logger.error(
                    "Agent %s message processing error (#%d): %s",
                    self.agent_id,
                    self.error_count,
                    e,
                    exc_info=True,
                )
                if self.error_count >= 10:
                    self.status = AgentStatus.ERROR
                    logger.critical(
                        "Agent %s exceeded error threshold, entering ERROR state",
                        self.agent_id,
                    )

    async def handle_message(self, message: AgentMessage):
        """
        Handle a received message (override in subclasses).

        Args:
            message: Message to handle
        """
        logger.debug(f"Agent {self.agent_id} handling message {message.message_id}")

        # Default: send heartbeat response
        if message.message_type == "heartbeat":
            response = AgentMessage(
                sender_id=self.agent_id,
                receiver_id=message.sender_id,
                message_type="response",
                content={
                    "status": self.status.value,
                    "heartbeat": datetime.now().isoformat(),
                },
                parent_id=message.message_id,
            )
            self.send_message(response)

    def update_memory(self, key: str, value: Any):
        """Update agent memory."""
        with self.lock:
            self.memory[key] = value

    def get_memory(self, key: str, default: Any = None) -> Any:
        """Get value from memory."""
        with self.lock:
            return self.memory.get(key, default)

    def update_heartbeat(self):
        """Update last heartbeat timestamp."""
        with self.lock:
            self.last_heartbeat = datetime.now()

    @abstractmethod
    async def run(self):
        """
        Main agent loop (override in subclasses).

        This is where the agent's primary logic runs.
        """
        pass

    async def start(self):
        """Start the agent and its message processing task."""
        if self.running:
            return

        self.status = AgentStatus.READY
        self.running = True
        self.error_count = 0

        logger.info("Starting agent: %s", self.agent_name)

        task = asyncio.create_task(
            self.process_messages(), name=f"{self.agent_id}_messages"
        )
        self._tasks.append(task)

        self.status = AgentStatus.RUNNING
        try:
            await self.run()
        except asyncio.CancelledError:
            logger.info("Agent %s run() cancelled", self.agent_id)
        except Exception as e:
            self.status = AgentStatus.ERROR
            logger.error("Agent %s run() failed: %s", self.agent_id, e, exc_info=True)

    async def stop(self):
        """Stop the agent and cancel all background tasks."""
        if not self.running:
            return

        logger.info("Stopping agent: %s", self.agent_name)
        self.running = False

        for task in self._tasks:
            task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()

        self.status = AgentStatus.SHUTDOWN
        logger.info("Agent %s stopped", self.agent_id)

    def get_status(self) -> Dict[str, Any]:
        """Get agent status."""
        with self.lock:
            return {
                "agent_id": self.agent_id,
                "agent_name": self.agent_name,
                "status": self.status.value,
                "capabilities": [c.value for c in self.capabilities],
                "created_at": self.created_at.isoformat(),
                "last_heartbeat": self.last_heartbeat.isoformat(),
                "tools_count": len(self.tools),
                "memory_keys": list(self.memory.keys()),
                "messages_received": len(self.message_history),
            }


class AgentRegistry:
    """Registry for all agents."""

    def __init__(self):
        """Initialize agent registry."""
        self.agents: Dict[str, BaseAgent] = {}
        self.lock = threading.Lock()

    def register(self, agent: BaseAgent):
        """Register an agent. Raises ValueError on duplicate ID."""
        with self.lock:
            if agent.agent_id in self.agents:
                raise ValueError(
                    f"Agent ID {agent.agent_id} already registered "
                    f"({self.agents[agent.agent_id].agent_name})"
                )
            self.agents[agent.agent_id] = agent
            logger.info("Registered agent: %s (%s)", agent.agent_name, agent.agent_id)

    def get(self, agent_id: str) -> Optional[BaseAgent]:
        """Get agent by ID."""
        with self.lock:
            return self.agents.get(agent_id)

    def get_all(self) -> List[BaseAgent]:
        """Get all registered agents."""
        with self.lock:
            return list(self.agents.values())

    def get_by_name(self, name: str) -> Optional[BaseAgent]:
        """Get agent by name."""
        with self.lock:
            for agent in self.agents.values():
                if agent.agent_name == name:
                    return agent
            return None


# Global registry
agent_registry = AgentRegistry()
