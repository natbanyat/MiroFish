"""
配置管理
统一从项目根目录的 .env 文件加载配置
"""

import os
from dotenv import load_dotenv

# 加载项目根目录的 .env 文件
# 路径: MiroFish/.env (相对于 backend/app/config.py)
project_root_env = os.path.join(os.path.dirname(__file__), '../../.env')

if os.path.exists(project_root_env):
    load_dotenv(project_root_env, override=True)
else:
    # 如果根目录没有 .env，尝试加载环境变量（用于生产环境）
    load_dotenv(override=True)


def _real_key(val):
    """Return None if val is a placeholder like 'your_xxx_here'."""
    if not val:
        return None
    if val.startswith('your_') or val.endswith('_here'):
        return None
    return val


class Config:
    """Flask配置类"""

    # Flask配置
    SECRET_KEY = os.environ.get('SECRET_KEY', 'mirofish-secret-key')
    DEBUG = os.environ.get('FLASK_DEBUG', 'True').lower() == 'true'

    # JSON配置 - 禁用ASCII转义，让中文直接显示（而不是 \uXXXX 格式）
    JSON_AS_ASCII = False

    # LLM配置 — LLM_API_KEY falls back to OPENAI_API_KEY; placeholders are ignored
    LLM_API_KEY = _real_key(os.environ.get('LLM_API_KEY')) or _real_key(os.environ.get('OPENAI_API_KEY'))
    LLM_BASE_URL = os.environ.get('LLM_BASE_URL', 'https://api.openai.com/v1')
    LLM_MODEL_NAME = os.environ.get('LLM_MODEL_NAME', 'gpt-5.4-mini')

    # Boost LLM — used for high-quality synthesis tasks (report content, ontology generation).
    # Falls back to primary LLM if not set.
    LLM_BOOST_API_KEY = os.environ.get('LLM_BOOST_API_KEY')
    LLM_BOOST_BASE_URL = os.environ.get('LLM_BOOST_BASE_URL')
    LLM_BOOST_MODEL_NAME = os.environ.get('LLM_BOOST_MODEL_NAME')
    
    # 文件上传配置
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50MB
    UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), '../uploads')
    ALLOWED_EXTENSIONS = {'pdf', 'md', 'txt', 'markdown'}
    
    # 文本处理配置
    DEFAULT_CHUNK_SIZE = 500  # 默认切块大小
    DEFAULT_CHUNK_OVERLAP = 50  # 默认重叠大小
    
    # OASIS模拟配置
    OASIS_DEFAULT_MAX_ROUNDS = int(os.environ.get('OASIS_DEFAULT_MAX_ROUNDS', '10'))
    OASIS_SIMULATION_DATA_DIR = os.path.join(os.path.dirname(__file__), '../uploads/simulations')
    
    # OASIS平台可用动作配置
    OASIS_TWITTER_ACTIONS = [
        'CREATE_POST', 'LIKE_POST', 'REPOST', 'FOLLOW', 'DO_NOTHING', 'QUOTE_POST'
    ]
    OASIS_REDDIT_ACTIONS = [
        'LIKE_POST', 'DISLIKE_POST', 'CREATE_POST', 'CREATE_COMMENT',
        'LIKE_COMMENT', 'DISLIKE_COMMENT', 'SEARCH_POSTS', 'SEARCH_USER',
        'TREND', 'REFRESH', 'DO_NOTHING', 'FOLLOW', 'MUTE'
    ]
    
    # Report Agent配置
    REPORT_AGENT_MAX_TOOL_CALLS = int(os.environ.get('REPORT_AGENT_MAX_TOOL_CALLS', '5'))
    REPORT_AGENT_MAX_REFLECTION_ROUNDS = int(os.environ.get('REPORT_AGENT_MAX_REFLECTION_ROUNDS', '2'))
    REPORT_AGENT_TEMPERATURE = float(os.environ.get('REPORT_AGENT_TEMPERATURE', '0.5'))

    # ── Token Budget ──
    TOKEN_BUDGET_MAX = int(os.environ.get('TOKEN_BUDGET_MAX', '500000'))

    # ── Multi-Provider API Keys ──
    # Configure all providers you have access to. Unused providers can be left blank.
    OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY') or LLM_API_KEY
    OPENAI_BASE_URL = os.environ.get('OPENAI_BASE_URL', 'https://api.openai.com/v1')
    ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY')
    ANTHROPIC_BASE_URL = os.environ.get('ANTHROPIC_BASE_URL', 'https://api.anthropic.com/v1/')
    GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
    GEMINI_BASE_URL = os.environ.get('GEMINI_BASE_URL', 'https://generativelanguage.googleapis.com/v1beta/openai/')

    # ── Cost Tier ──
    # "cheap", "medium", or "expensive" — controls model selection and failover order.
    # Can be changed at runtime via POST /api/settings/cost-tier.
    COST_TIER = os.environ.get('COST_TIER', 'cheap').lower()

    # ── Cost Tier Presets ──
    # Each tier defines boost (quality) and cheap (bulk) model chains.
    # Each chain is a list of (provider, model) tuples tried in order as failover.
    _TIER_PRESETS = {
        "cheap": {
            "boost_chain": [
                ("openai",    "gpt-5.4-mini"),           # $0.75/$4.50
                ("gemini",    "gemini-3.0-flash"),        # $0.50/$3.00
                ("anthropic", "claude-haiku-4-5"),        # $1/$5
            ],
            "cheap_chain": [
                ("openai",    "gpt-5.4-nano"),            # $0.20/$1.25
                ("gemini",    "gemini-3.1-flash-lite-preview"),  # $0.25/$1.50
                ("openai",    "gpt-5.4-mini"),            # $0.75/$4.50
            ],
            "est_cost": "$0.05-0.15",
        },
        "medium": {
            "boost_chain": [
                ("anthropic", "claude-sonnet-4-6"),       # $3/$15
                ("openai",    "gpt-5.4"),                 # $5/$25
                ("gemini",    "gemini-3.0-flash"),        # $0.50/$3
            ],
            "cheap_chain": [
                ("openai",    "gpt-5.4-nano"),            # $0.20/$1.25
                ("gemini",    "gemini-3.1-flash-lite-preview"),  # $0.25/$1.50
                ("anthropic", "claude-haiku-4-5"),        # $1/$5
            ],
            "est_cost": "$0.30-0.80",
        },
        "expensive": {
            "boost_chain": [
                ("anthropic", "claude-sonnet-4-6"),       # $3/$15
                ("openai",    "gpt-5.4"),                 # $5/$25
                ("anthropic", "claude-haiku-4-5"),        # $1/$5
            ],
            "cheap_chain": [
                ("openai",    "gpt-5.4-mini"),            # $0.75/$4.50
                ("gemini",    "gemini-3.0-flash"),        # $0.50/$3
                ("anthropic", "claude-haiku-4-5"),        # $1/$5
            ],
            "est_cost": "$0.50-1.50",
        },
    }

    # ── Per-Task Model Routing ──
    # Runtime-mutable dict: task_name -> {"provider": "openai", "model": "gpt-5.4-mini"}
    # When set, overrides tier presets for that specific task.
    # Changed via POST /api/settings/model-routing
    TASK_TYPES = {
        "ontology":       {"label": "Ontology Generation",   "default_role": "boost",  "desc": "Entity/relation type design from documents"},
        "profiles":       {"label": "Profile Generation",    "default_role": "cheap",  "desc": "Agent persona creation (1 call per entity)"},
        "sim_config":     {"label": "Simulation Config",     "default_role": "cheap",  "desc": "Time/event/agent activity configuration"},
        "report_plan":    {"label": "Report Planning",       "default_role": "boost",  "desc": "Report outline and section design"},
        "report_section": {"label": "Report Sections",       "default_role": "boost",  "desc": "ReACT loop for each report chapter"},
        "sub_queries":    {"label": "Search Sub-queries",    "default_role": "cheap",  "desc": "Question decomposition for graph search"},
        "seed_gen":       {"label": "Reality Seed Gen",      "default_role": "boost",  "desc": "Background document generation"},
        "scenario_gen":   {"label": "Scenario Gen",          "default_role": "boost",  "desc": "Structured scenario from description"},
    }

    # Available models per provider
    AVAILABLE_MODELS = {
        "openai": [
            {"id": "gpt-5.4-nano",  "cost": "$0.20/$1.25",  "tier": "cheap"},
            {"id": "gpt-5.4-mini",  "cost": "$0.75/$4.50",  "tier": "mid"},
            {"id": "gpt-5.4",       "cost": "$5/$25",       "tier": "quality"},
        ],
        "anthropic": [
            {"id": "claude-haiku-4-5",   "cost": "$1/$5",    "tier": "cheap"},
            {"id": "claude-sonnet-4-6",  "cost": "$3/$15",   "tier": "mid"},
        ],
        "gemini": [
            {"id": "gemini-3.1-flash-lite-preview", "cost": "$0.25/$1.50", "tier": "cheap"},
            {"id": "gemini-3.0-flash",              "cost": "$0.50/$3",    "tier": "mid"},
        ],
    }

    # Recommended defaults per task
    _TASK_DEFAULTS = {
        "ontology":       {"provider": "openai",    "model": "gpt-5.4-mini"},
        "profiles":       {"provider": "openai",    "model": "gpt-5.4-nano"},
        "sim_config":     {"provider": "openai",    "model": "gpt-5.4-nano"},
        "report_plan":    {"provider": "openai",    "model": "gpt-5.4-mini"},
        "report_section": {"provider": "anthropic", "model": "claude-sonnet-4-6"},
        "sub_queries":    {"provider": "openai",    "model": "gpt-5.4-nano"},
        "seed_gen":       {"provider": "openai",    "model": "gpt-5.4-mini"},
        "scenario_gen":   {"provider": "openai",    "model": "gpt-5.4-mini"},
    }

    # Runtime overrides — populated via API
    _task_model_overrides = {}

    @classmethod
    def get_task_model(cls, task_name: str):
        """Return (provider, model) for a specific task, respecting overrides."""
        if task_name in cls._task_model_overrides:
            o = cls._task_model_overrides[task_name]
            return o["provider"], o["model"]
        if task_name in cls._TASK_DEFAULTS:
            d = cls._TASK_DEFAULTS[task_name]
            return d["provider"], d["model"]
        # Fallback to tier-based
        role = cls.TASK_TYPES.get(task_name, {}).get("default_role", "boost")
        chain = cls.get_boost_chain() if role == "boost" else cls.get_cheap_chain()
        if chain:
            _, base_url, model = chain[0]
            provider = "openai"
            if "anthropic" in base_url:
                provider = "anthropic"
            elif "google" in base_url:
                provider = "gemini"
            return provider, model
        return "openai", cls.LLM_MODEL_NAME

    @classmethod
    def get_task_chain(cls, task_name: str):
        """Return full failover chain for a task: [(api_key, base_url, model), ...]"""
        provider, model = cls.get_task_model(task_name)
        api_key, base_url = cls._provider_config(provider)

        # Primary
        chain = []
        if api_key:
            chain.append((api_key, base_url, model))

        # Add fallbacks from the other providers
        role = cls.TASK_TYPES.get(task_name, {}).get("default_role", "boost")
        tier_chain = cls.get_boost_chain() if role == "boost" else cls.get_cheap_chain()
        for entry in tier_chain:
            if entry not in chain:
                chain.append(entry)

        if not chain:
            chain.append((cls.LLM_API_KEY, cls.LLM_BASE_URL, cls.LLM_MODEL_NAME))
        return chain

    @classmethod
    def get_model_routing_info(cls):
        """Return full model routing config for the UI."""
        tasks = {}
        for task_name, meta in cls.TASK_TYPES.items():
            provider, model = cls.get_task_model(task_name)
            is_overridden = task_name in cls._task_model_overrides
            tasks[task_name] = {
                **meta,
                "provider": provider,
                "model": model,
                "overridden": is_overridden,
            }

        providers = {}
        for pname, models in cls.AVAILABLE_MODELS.items():
            api_key, _ = cls._provider_config(pname)
            providers[pname] = {
                "connected": bool(api_key),
                "models": models,
            }

        return {
            "tasks": tasks,
            "providers": providers,
            "defaults": cls._TASK_DEFAULTS,
        }

    # ── Legacy Model Routing (still supported, overrides tier presets) ──
    LLM_CHEAP_API_KEY = os.environ.get('LLM_CHEAP_API_KEY')
    LLM_CHEAP_BASE_URL = os.environ.get('LLM_CHEAP_BASE_URL')
    LLM_CHEAP_MODEL_NAME = os.environ.get('LLM_CHEAP_MODEL_NAME')

    @classmethod
    def _provider_config(cls, provider: str):
        """Return (api_key, base_url) for a provider name."""
        if provider == "openai":
            return cls.OPENAI_API_KEY, cls.OPENAI_BASE_URL
        elif provider == "anthropic":
            return cls.ANTHROPIC_API_KEY, cls.ANTHROPIC_BASE_URL
        elif provider == "gemini":
            return cls.GEMINI_API_KEY, cls.GEMINI_BASE_URL
        return cls.LLM_API_KEY, cls.LLM_BASE_URL

    @classmethod
    def get_boost_chain(cls):
        """Return list of (api_key, base_url, model) for boost tasks in failover order."""
        # Legacy override
        if cls.LLM_BOOST_API_KEY or cls.LLM_BOOST_MODEL_NAME:
            return [(
                cls.LLM_BOOST_API_KEY or cls.LLM_API_KEY,
                cls.LLM_BOOST_BASE_URL or cls.LLM_BASE_URL,
                cls.LLM_BOOST_MODEL_NAME or cls.LLM_MODEL_NAME,
            )]
        preset = cls._TIER_PRESETS.get(cls.COST_TIER, cls._TIER_PRESETS["cheap"])
        chain = []
        for provider, model in preset["boost_chain"]:
            api_key, base_url = cls._provider_config(provider)
            if api_key:
                chain.append((api_key, base_url, model))
        # Always include primary LLM as last resort
        if not chain:
            chain.append((cls.LLM_API_KEY, cls.LLM_BASE_URL, cls.LLM_MODEL_NAME))
        return chain

    @classmethod
    def get_cheap_chain(cls):
        """Return list of (api_key, base_url, model) for cheap tasks in failover order."""
        # Legacy override
        if cls.LLM_CHEAP_API_KEY or cls.LLM_CHEAP_MODEL_NAME:
            return [(
                cls.LLM_CHEAP_API_KEY or cls.LLM_API_KEY,
                cls.LLM_CHEAP_BASE_URL or cls.LLM_BASE_URL,
                cls.LLM_CHEAP_MODEL_NAME or cls.LLM_MODEL_NAME,
            )]
        preset = cls._TIER_PRESETS.get(cls.COST_TIER, cls._TIER_PRESETS["cheap"])
        chain = []
        for provider, model in preset["cheap_chain"]:
            api_key, base_url = cls._provider_config(provider)
            if api_key:
                chain.append((api_key, base_url, model))
        if not chain:
            chain.append((cls.LLM_API_KEY, cls.LLM_BASE_URL, cls.LLM_MODEL_NAME))
        return chain

    # Keep legacy methods for backward compat
    @classmethod
    def get_boost_config(cls):
        """Return (api_key, base_url, model) — first entry in boost chain."""
        return cls.get_boost_chain()[0]

    @classmethod
    def get_cheap_config(cls):
        """Return (api_key, base_url, model) — first entry in cheap chain."""
        return cls.get_cheap_chain()[0]

    @classmethod
    def get_tier_info(cls):
        """Return current tier config for the UI."""
        preset = cls._TIER_PRESETS.get(cls.COST_TIER, cls._TIER_PRESETS["cheap"])
        boost_chain = cls.get_boost_chain()
        cheap_chain = cls.get_cheap_chain()
        return {
            "current_tier": cls.COST_TIER,
            "est_cost": preset.get("est_cost", "unknown"),
            "boost_models": [m[2] for m in boost_chain],
            "cheap_models": [m[2] for m in cheap_chain],
            "available_tiers": {
                k: {"est_cost": v["est_cost"]}
                for k, v in cls._TIER_PRESETS.items()
            },
            "providers_configured": {
                "openai": bool(cls.OPENAI_API_KEY),
                "anthropic": bool(cls.ANTHROPIC_API_KEY),
                "gemini": bool(cls.GEMINI_API_KEY),
            },
        }

    @classmethod
    def validate(cls):
        """验证必要配置"""
        errors = []
        if not cls.LLM_API_KEY:
            errors.append("LLM_API_KEY 未配置")
        return errors

