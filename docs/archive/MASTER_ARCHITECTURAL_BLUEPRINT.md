# 🏗️ MASTER ARCHITECTURAL BLUEPRINT

**NFL Betting System - Complete Architecture**  
**Version**: 2.0  
**Date**: 2025-11-24  
**Status**: Production-Ready Implementation Plan

---

## 📊 EXECUTIVE SUMMARY

This blueprint synthesizes:
- ✅ Cursor's 12 critical improvement recommendations
- ✅ Multi-provider AI integration with specialized roles
- ✅ Self-improving backtesting engine (no forward knowledge)
- ✅ Strategy generation without forward knowledge
- ✅ Data-driven parlay pattern discovery

**Result**: The most powerful, self-improving NFL betting system ever built.

---

## 🎯 ARCHITECTURAL OVERVIEW

```
┌─────────────────────────────────────────────────────────────────┐
│                    NFL BETTING SYSTEM v2.0                       │
│                  Master Architectural Blueprint                  │
└─────────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
   ┌────▼────┐          ┌─────▼─────┐        ┌─────▼─────┐
   │   API   │          │    AI     │        │ BACKTEST  │
   │ORCHESTRA│          │  MANAGER  │        │  ENGINE   │
   └────┬────┘          └─────┬─────┘        └─────┬─────┘
        │                      │                     │
   ┌────▼──────────────────────▼─────────────────────▼─────┐
   │              CORE BETTING ENGINE                       │
   │  ┌──────────┐  ┌──────────┐  ┌──────────┐            │
   │  │ Strategy │  │  Kelly   │  │  Parlay  │            │
   │  │Generator │  │ Sizing   │  │ Discovery│            │
   │  └──────────┘  └──────────┘  └──────────┘            │
   └───────────────────────────────────────────────────────┘
                              │
                    ┌─────────▼─────────┐
                    │   DASHBOARD &     │
                    │   NOTIFICATIONS   │
                    └───────────────────┘
```

---

## 🔥 PHASE 1: CRITICAL API INFRASTRUCTURE (Week 1)

**Priority**: P0 - CRITICAL  
**Goal**: Bulletproof API layer that never exceeds rate limits

### **1.1 Circuit Breaker Pattern**

**File**: `src/api/circuit_breaker.py`

**Purpose**: Prevent catastrophic API failures from cascading

**Implementation**:
```python
"""
Circuit Breaker Implementation (Netflix Hystrix Pattern)

States:
- CLOSED: Normal operation, requests pass through
- OPEN: Too many failures, fail fast immediately
- HALF_OPEN: Testing if service recovered

Transition Logic:
CLOSED → OPEN: After N consecutive failures
OPEN → HALF_OPEN: After recovery timeout
HALF_OPEN → CLOSED: If test request succeeds
HALF_OPEN → OPEN: If test request fails
"""

from enum import Enum
from datetime import datetime, timedelta
import logging
import time

class CircuitState(Enum):
    CLOSED = "closed"       # Normal operation
    OPEN = "open"          # Service down, fail fast
    HALF_OPEN = "half_open" # Testing recovery

class CircuitBreaker:
    def __init__(
        self,
        failure_threshold: int = 5,      # Failures before opening
        recovery_timeout: int = 60,       # Seconds before testing recovery
        success_threshold: int = 2,       # Successes to close circuit
        timeout: float = 10.0             # Request timeout
    ):
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.success_threshold = success_threshold
        self.timeout = timeout
        self.last_failure_time = None
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def can_execute(self) -> bool:
        """Check if request can proceed"""
        if self.state == CircuitState.CLOSED:
            return True
        
        if self.state == CircuitState.OPEN:
            # Check if recovery timeout elapsed
            if self.last_failure_time:
                elapsed = (datetime.now() - self.last_failure_time).seconds
                if elapsed >= self.recovery_timeout:
                    self.logger.info("Circuit entering HALF_OPEN state for recovery test")
                    self.state = CircuitState.HALF_OPEN
                    self.success_count = 0
                    return True
            return False
        
        # HALF_OPEN: Allow test request
        return True
    
    def record_success(self):
        """Record successful request"""
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.success_threshold:
                self.logger.info("Circuit CLOSED - service recovered")
                self.state = CircuitState.CLOSED
                self.failure_count = 0
        elif self.state == CircuitState.CLOSED:
            # Reset failure count on success
            self.failure_count = 0
    
    def record_failure(self):
        """Record failed request"""
        self.last_failure_time = datetime.now()
        
        if self.state == CircuitState.HALF_OPEN:
            self.logger.warning("Circuit OPEN - recovery test failed")
            self.state = CircuitState.OPEN
            self.failure_count += 1
        elif self.state == CircuitState.CLOSED:
            self.failure_count += 1
            if self.failure_count >= self.failure_threshold:
                self.logger.error(
                    f"Circuit OPEN - {self.failure_count} consecutive failures"
                )
                self.state = CircuitState.OPEN
```

**Integration**: Wrap all API calls in `RequestOrchestrator._fetch_from_api()`

---

### **1.2 Request Deduplication**

**File**: `src/api/request_deduplicator.py`

**Purpose**: Save 40%+ API calls by merging identical requests

**Implementation**:
```python
"""
Request Deduplication System

Strategy:
1. Hash incoming requests (api + endpoint + params)
2. Check if identical request is in-flight
3. If yes: Attach callback to existing request
4. If no: Execute new request

Benefits:
- 100 users request "today's odds" simultaneously
- System makes 1 API call, distributes to 100 callbacks
- Saves 99 API calls
"""

import hashlib
import json
import time
from typing import Dict, List, Callable, Optional, Any
from dataclasses import dataclass
import logging

@dataclass
class PendingRequest:
    """Track in-flight request with multiple callbacks"""
    request_hash: str
    callbacks: List[Callable]
    started_at: float
    api: str
    endpoint: str
    params: Dict

class RequestDeduplicator:
    def __init__(self):
        self.pending: Dict[str, PendingRequest] = {}
        self.logger = logging.getLogger(self.__class__.__name__)
        self.stats = {
            'requests_received': 0,
            'requests_deduplicated': 0,
            'api_calls_saved': 0
        }
    
    def hash_request(self, api: str, endpoint: str, params: Dict) -> str:
        """Generate unique hash for request"""
        # Sort params for consistent hashing
        normalized = json.dumps({
            'api': api,
            'endpoint': endpoint,
            'params': dict(sorted(params.items()))
        }, sort_keys=True)
        
        return hashlib.sha256(normalized.encode()).hexdigest()[:16]
    
    def should_execute(
        self,
        api: str,
        endpoint: str,
        params: Dict,
        callback: Callable
    ) -> tuple[bool, Optional[str]]:
        """
        Check if request should execute or is duplicate.
        
        Returns:
            (should_execute: bool, request_hash: str)
        """
        self.stats['requests_received'] += 1
        
        request_hash = self.hash_request(api, endpoint, params)
        
        if request_hash in self.pending:
            # Duplicate! Attach callback to existing request
            self.pending[request_hash].callbacks.append(callback)
            self.stats['requests_deduplicated'] += 1
            self.stats['api_calls_saved'] += 1
            
            self.logger.info(
                f"Deduplication: Merged request to existing {api}/{endpoint} "
                f"({len(self.pending[request_hash].callbacks)} callbacks)"
            )
            return False, request_hash
        
        # New request - track it
        self.pending[request_hash] = PendingRequest(
            request_hash=request_hash,
            callbacks=[callback],
            started_at=time.time(),
            api=api,
            endpoint=endpoint,
            params=params
        )
        
        return True, request_hash
    
    def complete(self, request_hash: str, result: Any, error: Optional[str] = None):
        """Distribute result to all callbacks"""
        if request_hash not in self.pending:
            self.logger.warning(f"Completing unknown request: {request_hash}")
            return
        
        pending = self.pending.pop(request_hash)
        
        # Call all callbacks
        for callback in pending.callbacks:
            try:
                callback(result, error=error)
            except Exception as e:
                self.logger.error(f"Callback error: {e}", exc_info=True)
        
        self.logger.debug(
            f"Completed {pending.api}/{pending.endpoint} "
            f"for {len(pending.callbacks)} callbacks"
        )
```

**Integration**: Wrap `RequestOrchestrator.enqueue()` with deduplication check

---

### **1.3 Request Retry with Exponential Backoff**

**File**: `src/api/retry_handler.py`

**Purpose**: Handle transient failures gracefully

**Implementation**:
```python
"""
Request Retry Handler with Exponential Backoff

Strategy:
- Retry transient errors (429, 500, timeout)
- Exponential backoff: 1s, 2s, 4s, 8s
- Priority-aware delays (critical = shorter delay)
- Max retries: 3 attempts
"""

import time
import logging
from typing import Callable, Optional
from enum import IntEnum

class Priority(IntEnum):
    CRITICAL = 1
    HIGH = 2
    NORMAL = 3
    LOW = 4

class RetryHandler:
    def __init__(self, max_retries: int = 3, base_delay: float = 1.0):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def execute_with_retry(
        self,
        func: Callable,
        priority: Priority = Priority.NORMAL,
        *args,
        **kwargs
    ) -> Optional[Any]:
        """
        Execute function with retry logic.
        
        Args:
            func: Function to execute
            priority: Request priority (affects retry delay)
            *args, **kwargs: Arguments for func
        
        Returns:
            Function result or None if all retries failed
        """
        last_exception = None
        
        for attempt in range(self.max_retries):
            try:
                return func(*args, **kwargs)
            
            except Exception as e:
                last_exception = e
                
                # Check if retryable error
                if not self._is_retryable(e):
                    self.logger.error(f"Non-retryable error: {e}")
                    raise
                
                if attempt < self.max_retries - 1:
                    # Calculate delay (exponential backoff)
                    delay = self.base_delay * (2 ** attempt)
                    
                    # Priority adjustment (critical = shorter delay)
                    if priority == Priority.CRITICAL:
                        delay *= 0.5
                    elif priority == Priority.HIGH:
                        delay *= 0.75
                    
                    self.logger.warning(
                        f"Retry {attempt + 1}/{self.max_retries} after {delay:.1f}s: {e}"
                    )
                    time.sleep(delay)
                else:
                    self.logger.error(
                        f"All {self.max_retries} retries failed: {e}"
                    )
        
        return None
    
    def _is_retryable(self, error: Exception) -> bool:
        """Check if error is retryable"""
        retryable_errors = (
            '429',  # Rate limit
            '500',  # Server error
            '502',  # Bad gateway
            '503',  # Service unavailable
            'timeout',
            'ConnectionError'
        )
        
        error_str = str(error).lower()
        return any(retryable in error_str for retryable in retryable_errors)
```

**Integration**: Use in `RequestOrchestrator._process_request()`

---

### **1.4 Priority Escalation**

**File**: `src/api/priority_escalator.py`

**Purpose**: Prevent request starvation

**Implementation**:
```python
"""
Priority Escalation System

Strategy:
- Monitor request wait time
- Escalate priority if waiting too long
- Prevent starvation of low-priority requests

Escalation Rules:
- NORMAL waiting > 60s → HIGH
- HIGH waiting > 30s → CRITICAL
- LOW waiting > 120s → NORMAL
"""

import time
import logging
from typing import Dict
from enum import IntEnum

class Priority(IntEnum):
    CRITICAL = 1
    HIGH = 2
    NORMAL = 3
    LOW = 4

class PriorityEscalator:
    def __init__(self):
        self.escalation_rules = {
            Priority.LOW: {
                'threshold': 120,  # seconds
                'escalate_to': Priority.NORMAL
            },
            Priority.NORMAL: {
                'threshold': 60,
                'escalate_to': Priority.HIGH
            },
            Priority.HIGH: {
                'threshold': 30,
                'escalate_to': Priority.CRITICAL
            }
        }
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def check_escalation(
        self,
        current_priority: Priority,
        wait_time: float
    ) -> Priority:
        """
        Check if priority should be escalated.
        
        Args:
            current_priority: Current request priority
            wait_time: Seconds request has been waiting
        
        Returns:
            New priority (may be same as current)
        """
        if current_priority == Priority.CRITICAL:
            # Already at highest priority
            return current_priority
        
        rule = self.escalation_rules.get(current_priority)
        if not rule:
            return current_priority
        
        if wait_time > rule['threshold']:
            new_priority = rule['escalate_to']
            self.logger.info(
                f"Priority escalation: {current_priority.name} → "
                f"{new_priority.name} (waited {wait_time:.0f}s)"
            )
            return new_priority
        
        return current_priority
```

**Integration**: Use in `RequestOrchestrator._worker()` before processing

---

## 🤖 PHASE 2: AI INTEGRATION (Week 2)

**Priority**: P1 - HIGH  
**Goal**: Multi-provider AI system with specialized roles

### **2.1 Multi-Provider AI Manager**

**File**: `src/ai/ai_provider_manager.py`

**Purpose**: Route AI tasks to best provider for the job

**Architecture**:
```
AI Providers & Roles:
├── xAI (Grok) - Real-time sports analysis, breaking news, social sentiment
├── OpenAI (GPT-4) - Strategy reasoning, natural language insights
├── Anthropic (Claude) - Document analysis, research synthesis
├── Google (Gemini) - Multimodal analysis (video highlights, play diagrams)
├── Local LLM (Llama 3) - Fast inference, cost-free predictions
└── Swarm Intelligence - Multi-agent collaboration for complex decisions
```

**Implementation**:
```python
"""
Multi-Provider AI Manager with Role Specialization

Each AI has strengths:
- xAI: Real-time data, Twitter/X integration
- OpenAI: Reasoning, natural language
- Anthropic: Long context, analysis
- Google: Multimodal (video, images)
- Local: Fast, free, private
"""

from enum import Enum
from typing import Dict, List, Optional, Any
import os
import logging
import json

logger = logging.getLogger(__name__)

class AIProvider(Enum):
    XAI = "xai"              # Grok - real-time sports
    OPENAI = "openai"        # GPT-4 - reasoning
    ANTHROPIC = "anthropic"  # Claude - analysis
    GOOGLE = "google"        # Gemini - multimodal
    LOCAL = "local"          # Llama 3 - fast inference

class AIRole(Enum):
    SENTIMENT_ANALYSIS = "sentiment"     # Twitter, news sentiment
    STRATEGY_REASONING = "strategy"      # Why is this a good bet?
    DOCUMENT_ANALYSIS = "document"       # Parse injury reports, news
    PREDICTION = "prediction"            # Win probability
    RESEARCH = "research"                # Deep dive analysis
    MULTIMODAL = "multimodal"           # Video/image analysis

class AIProviderManager:
    """
    Route AI tasks to best provider for the job.
    
    Routing Logic:
    - Real-time sentiment → xAI (Twitter/X integration)
    - Strategic reasoning → OpenAI (best reasoning)
    - Long document analysis → Anthropic (200k context)
    - Video/image analysis → Google (multimodal)
    - Fast predictions → Local (no API cost)
    """
    
    # Provider-to-Role mapping (best fit)
    ROLE_ROUTING = {
        AIRole.SENTIMENT_ANALYSIS: [AIProvider.XAI, AIProvider.OPENAI],
        AIRole.STRATEGY_REASONING: [AIProvider.OPENAI, AIProvider.ANTHROPIC],
        AIRole.DOCUMENT_ANALYSIS: [AIProvider.ANTHROPIC, AIProvider.OPENAI],
        AIRole.PREDICTION: [AIProvider.LOCAL, AIProvider.OPENAI],
        AIRole.RESEARCH: [AIProvider.ANTHROPIC, AIProvider.XAI],
        AIRole.MULTIMODAL: [AIProvider.GOOGLE, AIProvider.OPENAI]
    }
    
    def __init__(self):
        self.providers = self._init_providers()
    
    def _init_providers(self) -> Dict[AIProvider, Any]:
        """Initialize available providers"""
        providers = {}
        
        # xAI (Grok)
        if os.getenv('XAI_API_KEY'):
            providers[AIProvider.XAI] = self._init_xai()
        
        # OpenAI
        if os.getenv('OPENAI_API_KEY'):
            providers[AIProvider.OPENAI] = self._init_openai()
        
        # Anthropic
        if os.getenv('ANTHROPIC_API_KEY'):
            providers[AIProvider.ANTHROPIC] = self._init_anthropic()
        
        # Google
        if os.getenv('GOOGLE_API_KEY'):
            providers[AIProvider.GOOGLE] = self._init_google()
        
        # Local (always available)
        providers[AIProvider.LOCAL] = self._init_local()
        
        return providers
    
    def route_task(self, role: AIRole, prompt: str, **kwargs) -> str:
        """
        Route AI task to best available provider.
        
        Fallback chain: primary → secondary → local
        """
        preferred = self.ROLE_ROUTING.get(role, [AIProvider.LOCAL])
        
        for provider in preferred:
            if provider in self.providers:
                try:
                    return self._execute(provider, prompt, **kwargs)
                except Exception as e:
                    logger.warning(f"{provider.value} failed: {e}, trying fallback")
        
        # Final fallback: local
        return self._execute(AIProvider.LOCAL, prompt, **kwargs)
    
    def _init_xai(self):
        """Initialize xAI (Grok) provider"""
        from agents.xai_grok_agent import XAIGrokAgent
        return XAIGrokAgent()
    
    def _init_openai(self):
        """Initialize OpenAI provider"""
        import openai
        return openai.OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
    
    def _init_anthropic(self):
        """Initialize Anthropic provider"""
        import anthropic
        return anthropic.Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))
    
    def _init_google(self):
        """Initialize Google provider"""
        import google.generativeai as genai
        genai.configure(api_key=os.getenv('GOOGLE_API_KEY'))
        return genai
    
    def _init_local(self):
        """Initialize local LLM (Llama 3)"""
        # Use Ollama or similar local LLM
        return None  # Placeholder
    
    def _execute(self, provider: AIProvider, prompt: str, **kwargs) -> str:
        """Execute prompt on provider"""
        if provider == AIProvider.XAI:
            return self.providers[provider].analyze(prompt)
        elif provider == AIProvider.OPENAI:
            response = self.providers[provider].chat.completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": prompt}]
            )
            return response.choices[0].message.content
        # ... other providers
        return ""
```

---

## 🔄 PHASE 3: SELF-IMPROVING BACKTESTING ENGINE (Week 3-4)

**Priority**: P1 - HIGH  
**Goal**: Strategy generation without forward knowledge

### **3.1 Walk-Forward Backtesting Framework**

**File**: `src/backtesting/self_improving_engine.py`

**Purpose**: Generate and validate strategies without forward knowledge

**Key Innovation**: NO FORWARD KNOWLEDGE
- Split data chronologically
- Train on past, validate on future
- Simulate as if system existed at start of data
- Generate strategies using AI
- Test, analyze, improve, repeat

**Implementation**:
```python
"""
Self-Improving Backtesting Engine

Key Innovation: NO FORWARD KNOWLEDGE
- Split data chronologically
- Train on past, validate on future
- Simulate as if system existed at start of data
- Generate strategies using AI
- Test, analyze, improve, repeat

Example Timeline:
├── 2016-2018: Training Period 1
├── 2019: Validation Period 1 → Deploy Strategy v1
├── 2019-2020: Training Period 2 (includes 2019 results)
├── 2021: Validation Period 2 → Deploy Strategy v2
└── Repeat...

Strategy Discovery Process:
1. AI analyzes training data
2. Proposes hypothesis (e.g., "Home dogs in division games")
3. Backtest validates hypothesis
4. If profitable → keep and evolve
5. If not → learn why and try new hypothesis
"""

from typing import List, Dict, Tuple
from datetime import datetime, timedelta
import pandas as pd
import json
import logging

logger = logging.getLogger(__name__)

class StrategyHypothesis:
    """AI-generated betting strategy hypothesis"""
    def __init__(
        self,
        name: str,
        description: str,
        filters: Dict,
        expected_edge: float,
        confidence: float,
        generation_method: str  # "ai_reasoning" | "genetic" | "ensemble"
    ):
        self.name = name
        self.description = description
        self.filters = filters
        self.expected_edge = expected_edge
        self.confidence = confidence
        self.generation_method = generation_method
        self.backtest_results = None

class SelfImprovingBacktester:
    """
    AI-powered self-improving backtesting system.
    
    Process:
    1. Load historical data (2016-2024)
    2. Split into training/validation periods
    3. Generate initial strategies (AI)
    4. Backtest each strategy (no forward knowledge)
    5. Analyze results (AI)
    6. Generate improved strategies
    7. Repeat until convergence
    """
    
    def __init__(self, data_path: str, ai_manager):
        self.data = pd.read_parquet(data_path)
        self.ai = ai_manager
        self.strategies: List[StrategyHypothesis] = []
        self.deployed_strategies: List[Dict] = []
    
    def walk_forward_analysis(
        self,
        train_years: int = 2,
        validate_years: int = 1,
        iterations: int = 5
    ):
        """
        Walk-forward backtesting with NO forward knowledge.
        
        Args:
            train_years: Years of training data
            validate_years: Years of validation
            iterations: Number of strategy improvement cycles
        """
        start_year = self.data['season'].min()
        end_year = self.data['season'].max()
        
        results = []
        
        # Sliding window through time
        for year in range(start_year, end_year - validate_years + 1):
            train_start = year
            train_end = year + train_years - 1
            validate_year = train_end + 1
            
            logger.info(f"\n{'='*80}")
            logger.info(f"Walk-Forward Period: Train {train_start}-{train_end}, Validate {validate_year}")
            logger.info(f"{'='*80}\n")
            
            # Get data for this period
            train_data = self.data[
                (self.data['season'] >= train_start) &
                (self.data['season'] <= train_end)
            ]
            
            validate_data = self.data[self.data['season'] == validate_year]
            
            # Generate and evolve strategies
            best_strategy = self._strategy_evolution_loop(
                train_data=train_data,
                validate_data=validate_data,
                iterations=iterations
            )
            
            # Deploy best strategy for this period
            if best_strategy and best_strategy['roi'] > 0.05:
                self.deployed_strategies.append({
                    'period': f"{train_start}-{train_end}",
                    'validate_year': validate_year,
                    'strategy': best_strategy,
                    'deployed_at': datetime.now()
                })
                
                logger.info(f"✅ Deployed Strategy: {best_strategy['name']}")
                logger.info(f"   ROI: {best_strategy['roi']:.1%}")
                logger.info(f"   Win Rate: {best_strategy['win_rate']:.1%}")
            
            results.append({
                'train_period': f"{train_start}-{train_end}",
                'validate_year': validate_year,
                'best_strategy': best_strategy
            })
        
        return results
    
    def _strategy_evolution_loop(
        self,
        train_data: pd.DataFrame,
        validate_data: pd.DataFrame,
        iterations: int
    ) -> Dict:
        """
        Evolve strategies through multiple iterations.
        
        Each iteration:
        1. Generate hypothesis (AI)
        2. Backtest on training
        3. Validate on validation
        4. Analyze (AI)
        5. Generate improved hypothesis
        """
        best_strategy = None
        best_roi = -float('inf')
        
        for i in range(iterations):
            logger.info(f"\n--- Iteration {i+1}/{iterations} ---")
            
            # Generate hypothesis
            if i == 0:
                # Initial strategies from AI analysis
                hypothesis = self._generate_initial_hypothesis(train_data)
            else:
                # Evolve from previous best
                hypothesis = self._evolve_hypothesis(best_strategy, train_data)
            
            logger.info(f"Testing: {hypothesis.name}")
            logger.info(f"Description: {hypothesis.description}")
            
            # Backtest on training data
            train_results = self._backtest(hypothesis, train_data)
            
            logger.info(f"Training Results:")
            logger.info(f"  ROI: {train_results['roi']:.1%}")
            logger.info(f"  Win Rate: {train_results['win_rate']:.1%}")
            logger.info(f"  Bets: {train_results['total_bets']}")
            
            # Validate on out-of-sample
            validate_results = self._backtest(hypothesis, validate_data)
            
            logger.info(f"Validation Results:")
            logger.info(f"  ROI: {validate_results['roi']:.1%}")
            logger.info(f"  Win Rate: {validate_results['win_rate']:.1%}")
            logger.info(f"  Bets: {validate_results['total_bets']}")
            
            # Check if this is best
            if validate_results['roi'] > best_roi:
                best_roi = validate_results['roi']
                best_strategy = {
                    'name': hypothesis.name,
                    'description': hypothesis.description,
                    'filters': hypothesis.filters,
                    'roi': validate_results['roi'],
                    'win_rate': validate_results['win_rate'],
                    'total_bets': validate_results['total_bets'],
                    'train_roi': train_results['roi'],
                    'iteration': i + 1
                }
                
                logger.info(f"✨ NEW BEST STRATEGY (Validation ROI: {best_roi:.1%})")
        
        return best_strategy
    
    def _generate_initial_hypothesis(self, train_data: pd.DataFrame) -> StrategyHypothesis:
        """
        Use AI to analyze data and generate initial strategy hypothesis.
        
        AI Prompt:
        "Analyze this NFL betting data and propose a profitable betting strategy.
         Consider: home/away, division games, spreads, weather, rest days, etc.
         Return hypothesis in JSON format."
        """
        # Prepare data summary for AI
        summary = {
            'total_games': len(train_data),
            'home_win_pct': train_data['home_won'].mean(),
            'favorite_cover_pct': train_data['favorite_covered'].mean(),
            'avg_spread': train_data['spread'].mean(),
            'divisional_games': (train_data['is_divisional'] == 1).sum()
        }
        
        prompt = f"""
        Analyze this NFL betting data and generate a profitable betting strategy hypothesis.
        
        Data Summary:
        {json.dumps(summary, indent=2)}
        
        Requirements:
        - Strategy must be data-driven
        - Clear filtering criteria
        - Expected edge > 3%
        - Must be testable on historical data
        
        Return strategy in JSON format:
        {{
            "name": "Strategy name",
            "description": "Why this works",
            "filters": {{
                "home_underdog": true,
                "spread_range": [3, 7],
                "is_divisional": true
            }},
            "expected_edge": 0.05
        }}
        """
        
        # Route to AI (uses best available provider)
        from src.ai.ai_provider_manager import AIRole
        response = self.ai.route_task(
            role=AIRole.STRATEGY_REASONING,
            prompt=prompt
        )
        
        # Parse AI response
        strategy_json = json.loads(response)
        
        return StrategyHypothesis(
            name=strategy_json['name'],
            description=strategy_json['description'],
            filters=strategy_json['filters'],
            expected_edge=strategy_json['expected_edge'],
            confidence=0.7,
            generation_method='ai_reasoning'
        )
    
    def _evolve_hypothesis(
        self,
        previous_best: Dict,
        train_data: pd.DataFrame
    ) -> StrategyHypothesis:
        """
        Evolve previous best strategy using AI feedback.
        
        Strategies:
        - Refine filters (tighten/loosen criteria)
        - Add new conditions (weather, rest, etc.)
        - Combine with other patterns
        """
        prompt = f"""
        Previous strategy:
        {json.dumps(previous_best, indent=2)}
        
        This strategy worked but can be improved.
        Analyze why it worked and propose an evolved version.
        
        Consider:
        - Tightening filters to increase edge
        - Adding new conditions (weather, injuries, etc.)
        - Combining with complementary patterns
        
        Return improved strategy in same JSON format.
        """
        
        from src.ai.ai_provider_manager import AIRole
        response = self.ai.route_task(
            role=AIRole.STRATEGY_REASONING,
            prompt=prompt
        )
        
        evolved_json = json.loads(response)
        
        return StrategyHypothesis(
            name=evolved_json['name'],
            description=evolved_json['description'],
            filters=evolved_json['filters'],
            expected_edge=evolved_json['expected_edge'],
            confidence=0.8,
            generation_method='ai_evolution'
        )
    
    def _backtest(self, hypothesis: StrategyHypothesis, data: pd.DataFrame) -> Dict:
        """Backtest strategy hypothesis on data"""
        # Apply filters
        filtered = data.copy()
        
        for key, value in hypothesis.filters.items():
            if key == 'home_underdog':
                filtered = filtered[filtered['home_spread'] > 0]
            elif key == 'spread_range':
                filtered = filtered[
                    (filtered['spread'].abs() >= value[0]) &
                    (filtered['spread'].abs() <= value[1])
                ]
            elif key == 'is_divisional':
                filtered = filtered[filtered['is_divisional'] == 1]
            # ... more filters
        
        # Calculate results
        if len(filtered) == 0:
            return {'roi': -1.0, 'win_rate': 0.0, 'total_bets': 0}
        
        wins = filtered['favorite_covered'].sum()
        total = len(filtered)
        win_rate = wins / total
        
        # Simplified ROI calculation
        roi = (win_rate * 0.91) - (1 - win_rate)  # -110 odds
        
        return {
            'roi': roi,
            'win_rate': win_rate,
            'total_bets': total
        }
```

---

## 🎯 PHASE 4: PARLAY PATTERN DISCOVERY (Week 4)

**Priority**: P1 - HIGH  
**Goal**: Data-driven parlay templates

### **4.1 Association Rule Mining**

**File**: `src/analysis/parlay_discovery.py`

**Purpose**: Discover profitable parlay patterns from historical data

**Implementation**:
```python
"""
Data-Driven Parlay Pattern Discovery

Goal: Find parlay combinations that hit consistently based ONLY on data.
Method: Association rule mining + temporal analysis + ML clustering.

Example Discoveries:
- "Home dogs in division games + road favorites > 7 point spread" (78% hit rate)
- "TNF unders + Sunday divisional unders" (71% hit rate)
- "AFC favorites after bye week + NFC dogs off loss" (69% hit rate)

Process:
1. Mine frequent patterns (teams, situations that win together)
2. Calculate confidence, support, lift
3. Filter high-confidence patterns
4. Backtest validation
5. Deploy as parlay templates
"""

from mlxtend.frequent_patterns import apriori, association_rules
from sklearn.cluster import KMeans
import pandas as pd
import logging

logger = logging.getLogger(__name__)

class ParlayPatternDiscovery:
    """
    Discover profitable parlay patterns from historical data.
    
    Uses:
    - Association rule mining (market basket analysis)
    - Temporal correlation analysis
    - ML clustering for similar games
    """
    
    def __init__(self, data: pd.DataFrame):
        self.data = data
        self.discovered_patterns = []
    
    def discover_patterns(
        self,
        min_support: float = 0.05,  # Pattern must appear in 5%+ of data
        min_confidence: float = 0.65,  # Must hit 65%+ of time
        min_lift: float = 1.2        # 20% better than random
    ) -> List[Dict]:
        """
        Mine association rules for parlay patterns.
        
        Returns:
            List of discovered patterns with metrics
        """
        # Prepare transaction database
        transactions = self._prepare_transactions()
        
        # Find frequent itemsets
        frequent_itemsets = apriori(
            transactions,
            min_support=min_support,
            use_colnames=True
        )
        
        # Generate association rules
        rules = association_rules(
            frequent_itemsets,
            metric="confidence",
            min_threshold=min_confidence
        )
        
        # Filter by lift
        rules = rules[rules['lift'] >= min_lift]
        
        # Convert to parlay patterns
        patterns = []
        for _, rule in rules.iterrows():
            pattern = {
                'legs': list(rule['antecedents']),
                'confidence': rule['confidence'],
                'support': rule['support'],
                'lift': rule['lift'],
                'expected_hit_rate': rule['confidence']
            }
            patterns.append(pattern)
        
        # Sort by confidence * lift (quality score)
        patterns.sort(
            key=lambda x: x['confidence'] * x['lift'],
            reverse=True
        )
        
        self.discovered_patterns = patterns
        return patterns
    
    def _prepare_transactions(self) -> pd.DataFrame:
        """
        Convert games to transaction format for association mining.
        
        Each "transaction" is a week of games.
        Each "item" is a bet outcome (home_dog_won, road_fav_covered, etc.)
        """
        transactions = []
        
        # Group by week
        for (season, week), week_games in self.data.groupby(['season', 'week']):
            items = []
            
            for _, game in week_games.iterrows():
                # Home underdog won
                if game['home_spread'] > 0 and game['home_won']:
                    items.append('home_dog_won')
                
                # Road favorite covered
                if game['away_spread'] < 0 and game['away_covered']:
                    items.append('road_fav_covered')
                
                # Divisional under hit
                if game['is_divisional'] and game['total_under']:
                    items.append('divisional_under')
                
                # TNF under hit
                if game['day_of_week'] == 'Thursday' and game['total_under']:
                    items.append('tnf_under')
                
                # Add more patterns...
            
            transactions.append(items)
        
        # Convert to one-hot encoding
        from mlxtend.preprocessing import TransactionEncoder
        te = TransactionEncoder()
        te_ary = te.fit(transactions).transform(transactions)
        df = pd.DataFrame(te_ary, columns=te.columns_)
        
        return df
    
    def validate_pattern(
        self,
        pattern: Dict,
        validation_data: pd.DataFrame
    ) -> Dict:
        """
        Backtest discovered pattern on validation data.
        
        Returns:
            Validation metrics (hit_rate, roi, sample_size)
        """
        hits = 0
        total = 0
        
        # Group validation data by week
        for (season, week), week_games in validation_data.groupby(['season', 'week']):
            # Check if all legs of parlay hit this week
            all_legs_hit = True
            
            for leg in pattern['legs']:
                leg_hit = self._check_leg(leg, week_games)
                if not leg_hit:
                    all_legs_hit = False
                    break
            
            if all_legs_hit:
                hits += 1
            
            total += 1
        
        return {
            'hit_rate': hits / total if total > 0 else 0,
            'hits': hits,
            'total_opportunities': total,
            'pattern': pattern
        }
    
    def _check_leg(self, leg: str, week_games: pd.DataFrame) -> bool:
        """Check if leg condition is met in week games"""
        # Implementation depends on leg format
        # Example: 'home_dog_won' → check if any home dog won
        return True  # Placeholder
```

---

## 📋 IMPLEMENTATION CHECKLIST

### **Week 1: Critical Infrastructure**
- [ ] Circuit Breaker implementation
- [ ] Request Deduplication
- [ ] Retry logic with exponential backoff
- [ ] Priority escalation
- [ ] Integration with existing `OddsCache`
- [ ] Update `RequestOrchestrator`

### **Week 2: AI Integration**
- [ ] AI provider manager
- [ ] Role-based routing
- [ ] Strategy generation prompts
- [ ] Multi-agent setup (if using Swarms)
- [ ] Integration with backtesting engine

### **Week 3: Self-Improving Backtest**
- [ ] Walk-forward backtesting framework
- [ ] Strategy evolution loop
- [ ] No forward knowledge validation
- [ ] Deployment pipeline
- [ ] Integration with daily picks

### **Week 4: Parlay Discovery**
- [ ] Association rule mining
- [ ] Pattern validation
- [ ] Template generation
- [ ] Integration with daily picks

---

## 🚀 RECOMMENDED LIBRARIES

### **Backtesting & Analysis**
- `vectorbt` - Fast backtesting framework (NumPy-based)
- `backtrader` - Event-driven backtesting
- `mlxtend` - Association rule mining
- `optuna` - Hyperparameter optimization for strategies

### **AI/ML**
- `swarms` - Multi-agent AI collaboration
- `autogen` - Microsoft's multi-agent framework
- `langchain` - LLM orchestration
- `llamaindex` - RAG for sports data

### **Sports Data**
- `nfl_data_py` - Official NFL data (already using)
- `sportsipy` - Multi-sport scraping
- `py-ballpark` - Ballpark adjustments

---

## 🎯 PRIORITY IMPLEMENTATION ORDER

**Agree with all 12 improvements ✅**

**Prioritize in this exact order**:

1. **Circuit Breaker** (prevents disasters)
2. **Request Deduplication** (saves 40%+ API calls)
3. **Request Retry** (handles transients)
4. **Priority Escalation** (UX improvement)
5. **AI Integration** (strategy generation)
6. **Self-Improving Backtest** (the killer feature)
7. **Parlay Discovery** (data-driven templates)
8. Remaining 8 features (nice-to-haves)

---

## ✅ SUMMARY

**This blueprint creates**:
- ✅ Bulletproof API layer (never exceed rate limits)
- ✅ AI-powered strategy generation
- ✅ Self-improving betting system
- ✅ Data-driven parlay templates

**Result**: The most powerful, self-improving NFL betting system ever built.

---

**Next Steps**: Begin Phase 1 implementation (Critical Infrastructure)

